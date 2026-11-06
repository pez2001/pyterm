"""Regression tests for process handling and friendly errors.

    python -m unittest discover -s tests -v
"""
import os
import subprocess
import sys
import time
import types
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pyterm import backend  # noqa: E402
from pyterm.config import build_config, parse_size  # noqa: E402

posix_only = unittest.skipIf(backend.IS_WIN, 'needs a POSIX pty')


def wait_until(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def is_zombie_or_gone(pid):
    try:
        with open('/proc/%d/stat' % pid) as f:
            return f.read().rsplit(')', 1)[-1].split()[0] == 'Z'
    except OSError:
        return True


@posix_only
class PosixPtyTests(unittest.TestCase):
    def test_output_is_bounded_when_nobody_reads(self):
        b = backend.PosixPty('yes', 80, 25)
        try:
            time.sleep(1.5)     # the render loop is "stuck"; `yes` produces far more than we can display
            self.assertLessEqual(b.q.qsize(), backend.MAX_QUEUED + 2)
        finally:
            b.close()

    def test_output_flows_again_after_reading(self):
        b = backend.PosixPty('yes', 80, 25)
        try:
            time.sleep(0.5)
            self.assertTrue(b.read())
            self.assertTrue(wait_until(lambda: b.q.qsize() > 0))    # reader resumed
        finally:
            b.close()

    def test_close_kills_collects_and_releases(self):
        b = backend.PosixPty('sleep 100', 80, 25)
        pid, fd = b.pid, b.fd
        time.sleep(0.2)
        b.close()
        with self.assertRaises(ChildProcessError):   # nothing left to wait for: no zombie
            os.waitpid(pid, os.WNOHANG)
        with self.assertRaises(OSError):             # descriptor closed
            os.fstat(fd)
        b.close()                                    # second close is harmless

    def test_close_kills_a_shell_that_ignores_hangup(self):
        b = backend.PosixPty(['sh', '-c', 'trap "" HUP TERM; sleep 100'], 80, 25)
        pid = b.pid
        time.sleep(0.3)
        t0 = time.time()
        b.close()
        self.assertLess(time.time() - t0, 5)
        with self.assertRaises(ChildProcessError):
            os.waitpid(pid, os.WNOHANG)

    def test_close_kills_children_of_the_shell(self):
        b = backend.PosixPty(['sh', '-c', 'sleep 100 & echo child=$! ; wait'], 80, 25)
        seen = []

        def got_pid():
            seen.append(b.read())
            return 'child=' in ''.join(seen) and ''.join(seen).split('child=')[1].strip()[:1].isdigit()

        self.assertTrue(wait_until(got_pid))
        child = int(''.join(seen).split('child=')[1].split()[0])
        b.close()
        self.assertTrue(wait_until(lambda: is_zombie_or_gone(child)), 'grandchild survived close()')

    def test_finished_shell_is_collected_without_close(self):
        b = backend.PosixPty('true', 80, 25)
        pid = b.pid

        def collected():
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                return True
            return False

        self.assertTrue(wait_until(collected, 5), 'zombie left behind after the shell exited')
        b.close()


class ShellProblemTests(unittest.TestCase):
    def test_existing_programs_are_fine(self):
        self.assertIsNone(backend.shell_problem(sys.executable))
        self.assertIsNone(backend.shell_problem('"%s" -i' % sys.executable))
        self.assertIsNone(backend.shell_problem(None))
        self.assertIsNone(backend.shell_problem(''))

    def test_missing_program(self):
        msg = backend.shell_problem('/no/such/shell --login')
        self.assertIn('not found', msg)
        self.assertIn('/no/such/shell', msg)

    def test_directory_and_non_executable(self):
        self.assertIn('directory', backend.shell_problem(ROOT))
        if not backend.IS_WIN:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.txt') as f:
                os.chmod(f.name, 0o644)
                self.assertIn('not executable', backend.shell_problem(f.name))


class SizeTests(unittest.TestCase):
    def test_parse_size(self):
        self.assertEqual(parse_size('1280x720'), (1280, 720))
        self.assertEqual(parse_size('800X600'), (800, 600))
        self.assertEqual(parse_size(' 640 x 480 '), (640, 480))

    def test_bad_sizes_give_a_readable_error(self):
        import argparse
        for bad in ('1280', 'axb', '1280x', 'x720', '0x0', '-5x10', '10x-5', ''):
            with self.assertRaises(argparse.ArgumentTypeError, msg=bad) as cm:
                parse_size(bad)
            self.assertIn('size', str(cm.exception).lower())

    def test_build_config_uses_size(self):
        cfg, _ = build_config(['--demo', '--size', '1000x700'])
        self.assertEqual((cfg['width'], cfg['height']), (1000, 700))


class ThemeScreenTests(unittest.TestCase):
    def grid(self, screen):
        from pyterm.app import App
        fake = types.SimpleNamespace(theme={'name': 'unit-%r' % (screen,), 'screen': screen})
        return App.screen_grid(fake)

    def test_valid(self):
        self.assertEqual(self.grid({'cols': 40, 'rows': 25, 'border': [32, 36]}), (40, 25, 32, 36))
        self.assertEqual(self.grid({'cols': '40', 'rows': '25'}), (40, 25, 32, 32))

    def test_invalid_values_fall_back_instead_of_crashing(self):
        for bad in ({'cols': 'abc', 'rows': 5}, {'cols': -1, 'rows': 5}, {'cols': [1], 'rows': 5},
                    {'cols': 40, 'rows': 25, 'border': ['x', 1]}):
            self.assertIsNone(self.grid(bad), bad)

    def test_not_set(self):
        self.assertIsNone(self.grid(None))
        self.assertIsNone(self.grid({'cols': 0, 'rows': 0}))


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ, XDG_CONFIG_HOME=os.path.join(ROOT, 'build', 'no-config'), APPDATA=os.path.join(ROOT, 'build', 'no-config'))
        return subprocess.run([sys.executable, '-m', 'pyterm', '--gpu', 'false', *args], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)

    def test_missing_shell_exits_with_a_message(self):
        r = self.run_cli('-e', '/no/such/shell')
        self.assertEqual(r.returncode, 2)
        self.assertIn('shell not found', r.stderr)
        self.assertNotIn('Traceback', r.stderr)

    def test_bad_size_exits_with_a_message(self):
        for bad in ('1280', 'axb', '0x0'):
            r = self.run_cli('--size', bad, '--demo')
            self.assertEqual(r.returncode, 2, bad)
            self.assertIn('--size', r.stderr)
            self.assertNotIn('Traceback', r.stderr)


if __name__ == '__main__':
    unittest.main()
