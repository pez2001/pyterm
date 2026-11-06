"""Process backends: everything that produces terminal output.

All backends deliver *decoded text* through ``read()`` (non-blocking) and take
text in ``write()``. Reading happens in a daemon thread so the render loop
never blocks.
"""
from __future__ import annotations

import codecs
import os
import queue
import shutil
import subprocess
import sys
import threading
import time

IS_WIN = sys.platform.startswith('win')

# Reader threads stop reading once this many chunks wait for the render loop. The shell then blocks on its
# full pty buffer instead of us buffering unbounded output (`yes`, `cat /dev/urandom`) in memory.
MAX_QUEUED = 64


class Backend:
    alive = True
    name = 'backend'

    def __init__(self, encoding='utf-8'):
        self.q: queue.Queue = queue.Queue()
        self.set_encoding(encoding)

    def set_encoding(self, enc):
        self.encoding = enc
        self.decoder = codecs.getincrementaldecoder(enc)(errors='replace')

    def _throttle(self):
        """called by reader threads before each read: wait while the consumer is behind"""
        while self.alive and self.q.qsize() >= MAX_QUEUED:
            time.sleep(0.002)

    def _push_bytes(self, b: bytes):
        t = self.decoder.decode(b)
        if t:
            self.q.put(t)

    def read(self, limit=1 << 20) -> str:
        parts, size = [], 0
        try:
            while size < limit:
                t = self.q.get_nowait()
                parts.append(t)
                size += len(t)
        except queue.Empty:
            pass
        return ''.join(parts)

    def write(self, text: str):
        pass

    def resize(self, cols, rows):
        pass

    def close(self):
        self.alive = False


# ---------------------------------------------------------------------------
def default_shell():
    if IS_WIN:
        for c in ('pwsh.exe', 'powershell.exe'):
            if shutil.which(c):
                return c
        return os.environ.get('COMSPEC', 'cmd.exe')
    return os.environ.get('SHELL') or ('/bin/bash' if os.path.exists('/bin/bash') else '/bin/sh')


def shell_problem(cmd):
    """None when `cmd` (a command line) can be started, else a short human-readable reason"""
    import shlex
    if not isinstance(cmd, str) or not cmd.strip():
        return None
    try:
        parts = shlex.split(cmd, posix=not IS_WIN)
    except ValueError as e:
        return 'cannot parse shell command %r: %s' % (cmd, e)
    if not parts:
        return None
    prog = parts[0].strip('"\'')
    found = shutil.which(prog) or (prog if os.path.isfile(prog) and os.access(prog, os.X_OK) else None)
    if found:
        return None
    if os.path.isdir(prog):
        return 'shell %r is a directory, not a program' % prog
    if os.path.exists(prog):
        return 'shell %r exists but is not executable' % prog
    return 'shell not found: %r (check -e / the "shell:" setting, or leave it out to use %s)' % (prog, default_shell())


class PosixPty(Backend):
    name = 'pty'

    def __init__(self, cmd, cols, rows, encoding='utf-8', cwd=None):
        super().__init__(encoding)
        import pty
        import shlex
        argv = shlex.split(cmd) if isinstance(cmd, str) else list(cmd)
        env = dict(os.environ)
        env.update(TERM='xterm-256color', COLORTERM='truecolor', TERM_PROGRAM='pyterm')
        pid, fd = pty.fork()
        if pid == 0:  # child
            try:
                if cwd:
                    os.chdir(cwd)
                os.execvpe(argv[0], argv, env)
            except Exception as e:  # pragma: no cover
                os.write(2, ('exec failed: %s\n' % e).encode())
                os._exit(127)
        self.pid, self.fd = pid, fd
        self.resize(cols, rows)
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self):
        while self.alive:
            self._throttle()
            try:
                b = os.read(self.fd, 65536)
            except OSError:
                break
            if not b:
                break
            self._push_bytes(b)
        self.alive = False
        self._reap(2.0)   # the shell is gone: collect it so it does not stay a zombie

    def _reap(self, timeout):
        """wait up to `timeout` s for the child to exit and collect it; True when it is gone"""
        end = time.time() + timeout
        while True:
            try:
                pid, _ = os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:   # already collected
                return True
            if pid:
                return True
            if time.time() >= end:
                return False
            time.sleep(0.01)

    def write(self, text):
        try:
            os.write(self.fd, text.encode(self.encoding if self.encoding != 'ascii' else 'utf-8', 'replace'))
        except OSError:
            self.alive = False

    def resize(self, cols, rows):
        import fcntl
        import struct
        import termios
        try:
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
        except OSError:
            pass

    def close(self):
        """end the shell for real: hang up, then terminate, then kill (the whole process group), collect the
        child and release the pty. Safe to call twice."""
        self.alive = False
        if getattr(self, 'closed', False):
            return
        self.closed = True
        import signal
        for sig, wait in ((signal.SIGHUP, 0.3), (signal.SIGTERM, 0.3), (signal.SIGKILL, 2.0)):
            try:
                os.killpg(self.pid, sig)    # pty.fork() made the child a session/group leader
            except ProcessLookupError:
                pass
            except OSError:
                try:
                    os.kill(self.pid, sig)
                except OSError:
                    pass
            if self._reap(wait):
                break
        self._thread.join(1.0)
        if not self._thread.is_alive():
            try:
                os.close(self.fd)
            except OSError:
                pass


class WinPty(Backend):
    """ConPTY via the pywinpty package (pip install pywinpty)."""
    name = 'conpty'

    def __init__(self, cmd, cols, rows, encoding='utf-8', cwd=None):
        super().__init__(encoding)
        from winpty import PtyProcess  # type: ignore
        env = dict(os.environ)
        env.update(TERM='xterm-256color', COLORTERM='truecolor', TERM_PROGRAM='pyterm')
        self.proc = PtyProcess.spawn(cmd, dimensions=(rows, cols), cwd=cwd, env=env)
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while self.alive:
            self._throttle()
            try:
                t = self.proc.read(65536)
            except EOFError:
                break
            except Exception:
                if not self.proc.isalive():
                    break
                time.sleep(0.01)
                continue
            if t:
                self.q.put(t if isinstance(t, str) else t.decode('utf-8', 'replace'))
        self.alive = False

    def write(self, text):
        try:
            self.proc.write(text)
        except Exception:
            self.alive = False

    def resize(self, cols, rows):
        try:
            self.proc.setwinsize(rows, cols)
        except Exception:
            pass

    def close(self):
        self.alive = False
        try:
            self.proc.terminate(force=True)
        except Exception:
            pass


class PipeShell(Backend):
    """Last-resort fallback without a pty (no full-screen apps, local echo)."""
    name = 'pipes'

    def __init__(self, cmd, cols, rows, encoding='utf-8', cwd=None):
        super().__init__('cp850' if IS_WIN and encoding == 'utf-8' else encoding)
        self.proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, cwd=cwd, bufsize=0)
        self.line = ''
        self.q.put('\x1b[33m[pyterm] no pty available - running in pipe mode. '
                   'Install pywinpty for a real console: pip install pywinpty\x1b[0m\r\n')
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while self.alive:
            self._throttle()
            b = self.proc.stdout.read1(65536) if hasattr(self.proc.stdout, 'read1') else self.proc.stdout.read(1)
            if not b:
                break
            self._push_bytes(b.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        self.alive = False

    def write(self, text):
        for c in text:
            if c in '\r\n':
                self.q.put('\r\n')
                try:
                    self.proc.stdin.write((self.line + '\n').encode(self.encoding, 'replace'))
                    self.proc.stdin.flush()
                except OSError:
                    self.alive = False
                self.line = ''
            elif c in '\x7f\x08':
                if self.line:
                    self.line = self.line[:-1]
                    self.q.put('\b \b')
            elif c == '\x03':
                self.line = ''
                self.q.put('^C\r\n')
            elif c >= ' ':
                self.line += c
                self.q.put(c)

    def close(self):
        self.alive = False
        try:
            self.proc.kill()
        except Exception:
            pass


class ScriptSource(Backend):
    """Plays a script: list of (delay_seconds, text). Keyboard input is echoed
    locally with a tiny line editor - perfect for showing off effects."""
    name = 'demo'

    def __init__(self, script, encoding='utf-8', loop=False, echo=True, prompt='', marks=False):
        super().__init__(encoding)
        self.marks = marks
        self.script = list(script)
        self.echo = echo
        self.prompt = prompt
        self.loop = loop
        self.t0 = time.time()
        self.idx = 0
        self.acc = 0.0
        self.on_command = None
        self.line = ''
        threading.Thread(target=self._player, daemon=True).start()

    def _player(self):
        while self.alive and self.idx < len(self.script):
            delay, text = self.script[self.idx]
            time.sleep(max(0.0, delay))
            if callable(text):
                text = text()
            if isinstance(text, bytes):
                self._push_bytes(text)
            elif text:
                self.q.put(text)
            self.idx += 1
            if self.idx >= len(self.script) and self.loop:
                self.idx = 0

    def write(self, text):
        if not self.echo:
            return
        for c in text:
            if c in '\r\n':
                cmd = self.line
                self.line = ''
                threading.Thread(target=self._run, args=(cmd,), daemon=True).start()
            elif c in '\x7f\x08':
                if self.line:
                    self.line = self.line[:-1]
                    self.q.put('\b \b')
            elif c == '\x1b':
                break
            elif c >= ' ':
                self.line += c
                self.q.put(c)


    def _run(self, cmd):
        m = self.marks
        if m and cmd.strip():
            self.q.put('\r\n\x1b]133;C\x07')
        else:
            self.q.put('\r\n')
        out = self.on_command(cmd) if self.on_command else None
        code = 0
        if isinstance(out, tuple):
            out, code = out
        self.q.put((out or '') + (('\x1b]133;D;%d\x07' % code) if m and cmd.strip() else '') +
                   ('\x1b]133;A\x07' if m else '') + self.prompt + ('\x1b]133;B\x07' if m else ''))


class FileSource(ScriptSource):
    """cat a file (ANSI art!) - optionally decoded as cp437."""
    name = 'file'

    def __init__(self, path, encoding='cp437', **kw):
        with open(path, 'rb') as fh:
            data = fh.read()
        # strip SAUCE record
        k = data.rfind(b'\x1aSAUCE')
        if k >= 0:
            data = data[:k]
        if encoding in ('cp437', 'ascii', 'latin-1'):
            data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        super().__init__([(0.3, data)], encoding=encoding, **kw)


def create_backend(kind, cmd, cols, rows, encoding='utf-8', cwd=None):
    """kind: auto | pty | pipes"""
    cmd = cmd or default_shell()
    if kind in ('auto', 'pty'):
        try:
            if IS_WIN:
                return WinPty(cmd, cols, rows, encoding, cwd)
            return PosixPty(cmd, cols, rows, encoding, cwd)
        except Exception as e:  # pragma: no cover
            print('[pyterm] pty failed (%s), falling back to pipes' % e)
    return PipeShell(cmd, cols, rows, encoding, cwd)
