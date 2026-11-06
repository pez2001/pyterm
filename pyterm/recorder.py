"""Video export of the effects: MP4 (H.264) or GIF.

Uses ffmpeg (from PATH or the imageio-ffmpeg package, which ships a binary on
Windows/Linux/macOS). GIF without ffmpeg falls back to Pillow, and without
either we write a PNG frame sequence. Frames are captured on the render
thread and handed to a writer thread; when the encoder can't keep up frames
are dropped instead of stalling the terminal.
"""
from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
import time

import pygame


def find_ffmpeg():
    p = shutil.which('ffmpeg')
    if p:
        return p
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _tobytes(surf):
    try:
        return pygame.image.tobytes(surf, 'RGB')
    except AttributeError:  # old pygame
        return pygame.image.tostring(surf, 'RGB')


class VideoRecorder:
    def __init__(self, path, fps=30, max_width=1280, fixed_step=False):
        self.path = path
        self.fps = fps
        self.max_width = max_width
        self.fixed_step = fixed_step     # headless rendering: every frame is a video frame
        self.fmt = 'gif' if path.lower().endswith('.gif') else 'mp4'
        self.size = None
        self.proc = None
        self.frames = []                 # Pillow / png fallbacks
        self.q = queue.Queue(maxsize=90)
        self.thread = None
        self.last = 0.0
        self.count = 0
        self.dropped = 0
        self.mode = None
        self.error = None

    def _start(self, size):
        w, h = size
        if w > self.max_width:
            h = int(h * self.max_width / w)
            w = self.max_width
        if self.fmt == 'gif' and w > 720:
            h = int(h * 720 / w)
            w = 720
        w, h = w // 2 * 2, h // 2 * 2
        self.size = (w, h)
        ff = find_ffmpeg()
        if ff:
            cmd = [ff, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (w, h),
                   '-r', str(self.fps), '-i', '-']
            if self.fmt == 'mp4':
                cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
                        '-movflags', '+faststart', self.path]
            else:
                cmd += ['-vf', 'split[a][b];[a]palettegen=max_colors=256:stats_mode=diff[p];'
                               '[b][p]paletteuse=dither=bayer:bayer_scale=3', self.path]
            flags = 0x08000000 if os.name == 'nt' else 0  # CREATE_NO_WINDOW
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, creationflags=flags)
            self.mode = 'ffmpeg'
        else:
            try:
                import PIL  # noqa: F401
                self.mode = 'pillow' if self.fmt == 'gif' else 'png'
            except ImportError:
                self.mode = 'png'
            if self.mode == 'png':
                self.png_dir = os.path.splitext(self.path)[0] + '_frames'
                os.makedirs(self.png_dir, exist_ok=True)
        self.thread = threading.Thread(target=self._writer, daemon=True)
        self.thread.start()

    def _writer(self):
        while True:
            item = self.q.get()
            if item is None:
                break
            try:
                if self.mode == 'ffmpeg':
                    self.proc.stdin.write(item)
                elif self.mode == 'pillow':
                    from PIL import Image
                    self.frames.append(Image.frombytes('RGB', self.size, item).quantize(256))
                else:
                    s = pygame.image.frombuffer(item, self.size, 'RGB')
                    pygame.image.save(s, os.path.join(self.png_dir, '%06d.png' % self.count))
            except Exception as e:
                self.error = str(e)
                break

    def add(self, surf):
        now = time.perf_counter()
        if not self.fixed_step and now - self.last < 1.0 / self.fps - 0.002:
            return
        self.last = now
        if self.size is None:
            self._start(surf.get_size())
        if surf.get_size() != self.size:
            surf = pygame.transform.smoothscale(surf, self.size)
        try:
            self.q.put(_tobytes(surf), block=self.fixed_step, timeout=5 if self.fixed_step else None)
            self.count += 1
        except queue.Full:
            self.dropped += 1

    def stop(self):
        if self.thread is None:
            return None
        self.q.put(None)
        self.thread.join(timeout=60)
        if self.mode == 'ffmpeg':
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=120)
            except Exception as e:
                self.error = str(e)
        elif self.mode == 'pillow' and self.frames:
            self.frames[0].save(self.path, save_all=True, append_images=self.frames[1:],
                                duration=int(1000 / self.fps), loop=0, optimize=False)
        elif self.mode == 'png':
            return self.png_dir
        return self.path
