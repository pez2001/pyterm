"""CRT / post-processing stack.

virtual-resolution stage (cheap, before upscaling):
    phosphor afterglow, bloom, chromatic aberration, barrel curvature, glitch
window-resolution stage:
    scanlines + vignette (one precomputed multiply blit), flicker, noise
"""
from __future__ import annotations

import math
import random

import numpy as np
import pygame


class Post:
    def __init__(self):
        self.cfg = {}
        self.mult = None
        self.mult_key = None
        self.prev = None
        self.curve_key = None
        self.t = 0.0
        self.glitch_t = 0.0
        self.lock = None
        self.overlay = None
        self.flash = 0.0           # 0..1 colored flash (bell, errors)
        self.flash_rgb = (255, 255, 255)
        self.shake = 0.0

    def configure(self, crt, lock=None):
        self.cfg = dict(crt or {})
        self.mult_key = None
        self.curve_key = None
        self.lock = None
        if lock and lock.get('colors') and not lock.get('off'):
            self._build_lock(lock)

    # ------------------------------------------------------------ palette lock (gameboy / nes / c64 look)
    def _build_lock(self, lock):
        from .themes import hex2rgb
        cols = np.array([hex2rgb(c) for c in lock['colors']], np.float32)
        mode = lock.get('mode', 'nearest')
        dither = float(lock.get('dither', 0.0) or 0)
        bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16.0 - 0.5
        if mode == 'luma':
            luma = cols @ np.array([0.299, 0.587, 0.114], np.float32)
            order = np.argsort(luma)
            self.lock = ('luma', cols[order].astype(np.uint8), dither, bayer)
        else:
            g = np.arange(32, dtype=np.float32) * 8 + 4
            grid = np.stack(np.meshgrid(g, g, g, indexing='ij'), -1).reshape(-1, 3)
            d = ((grid[:, None, :] - cols[None, :, :]) ** 2 * np.array([0.3, 0.59, 0.11], np.float32)).sum(-1)
            lut = cols[np.argmin(d, 1)].astype(np.uint8).reshape(32, 32, 32, 3)
            self.lock = ('nearest', lut, dither, bayer)

    def _interlace(self, vs, amount):
        """two fields per frame: one field shows the previous frame (combing on motion)"""
        self.field = 1 - getattr(self, 'field', 0)
        prev = getattr(self, '_il_prev', None)
        cur = pygame.surfarray.array3d(vs)
        if prev is not None and prev.shape == cur.shape and amount >= 0.5:
            arr = pygame.surfarray.pixels3d(vs)
            arr[:, self.field::2] = prev[:, self.field::2]
            del arr
        self._il_prev = cur

    def _apply_overlay(self, vs):
        """arcade cellophane color bands: [[y0, y1, '#rrggbb'], ...] (fractions of the height)"""
        size = vs.get_size()
        key = (size, str(self.overlay))
        if getattr(self, '_ov_key', None) != key:
            from .themes import hex2rgb
            self._ov_key = key
            s = pygame.Surface(size)
            s.fill((255, 255, 255))
            for y0, y1, col in self.overlay:
                s.fill(hex2rgb(col), (0, int(y0 * size[1]), size[0], int((y1 - y0) * size[1]) + 1))
            self._ov = s
        vs.blit(self._ov, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    def _apply_lock(self, vs):
        mode, data, dither, bayer = self.lock
        w, h = vs.get_size()
        arr = pygame.surfarray.pixels3d(vs)
        if dither:
            by = np.tile(bayer, (w // 4 + 1, h // 4 + 1))[:w, :h]
        if mode == 'luma':
            l = (arr[..., 0].astype(np.float32) * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114) / 256.0
            n = len(data)
            if dither:
                l = l + by * dither / n
            idx = np.clip((l * n).astype(np.int32), 0, n - 1)
            arr[:] = data[idx]
        else:
            if dither:
                a = np.clip(arr.astype(np.float32) + (by * dither * 48)[..., None], 0, 255).astype(np.int32) >> 3
            else:
                a = arr.astype(np.int32) >> 3
            arr[:] = data[a[..., 0], a[..., 1], a[..., 2]]
        del arr

    def v(self, k, d=0.0):
        try:
            return float(self.cfg.get(k, d) or 0)
        except (TypeError, ValueError):
            return d

    # ------------------------------------------------------------ virtual res
    def virtual(self, vs, dt):
        self.t += dt
        w, h = vs.get_size()
        ph = self.v('phosphor')
        if ph > 0:
            if self.prev is None or self.prev.get_size() != (w, h):
                self.prev = vs.copy()
            else:
                d = int(255 * min(0.97, ph))
                self.prev.fill((d, d, d), special_flags=pygame.BLEND_RGB_MULT)
                vs.blit(self.prev, (0, 0), special_flags=pygame.BLEND_RGB_MAX)
                self.prev.blit(vs, (0, 0))
        bl = self.v('bloom')
        if bl > 0:
            sw, sh = max(1, w // 4), max(1, h // 4)
            small = pygame.transform.smoothscale(vs, (sw, sh))
            small = pygame.transform.smoothscale(small, (max(1, sw // 2), max(1, sh // 2)))
            small = pygame.transform.smoothscale(small, (sw, sh))
            k = int(255 * min(1.0, bl))
            small.fill((k, k, k), special_flags=pygame.BLEND_RGB_MULT)
            vs.blit(pygame.transform.smoothscale(small, (w, h)), (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        ab = int(self.v('aberration'))
        if ab > 0:
            red = vs.copy()
            red.fill((255, 0, 0), special_flags=pygame.BLEND_RGB_MULT)
            blue = vs.copy()
            blue.fill((0, 0, 255), special_flags=pygame.BLEND_RGB_MULT)
            vs.fill((0, 255, 0), special_flags=pygame.BLEND_RGB_MULT)
            vs.blit(red, (-ab, 0), special_flags=pygame.BLEND_RGB_ADD)
            vs.blit(blue, (ab, 0), special_flags=pygame.BLEND_RGB_ADD)
        gl = self.v('glitch')
        if gl > 0:
            if self.glitch_t > 0:
                self.glitch_t -= dt
                for _ in range(3):
                    y = random.randint(0, h - 4)
                    bh = random.randint(2, max(3, h // 20))
                    dx = random.randint(-w // 30, w // 30)
                    band = vs.subsurface((0, y, w, min(bh, h - y))).copy()
                    vs.blit(band, (dx, y))
            elif random.random() < gl * dt:
                self.glitch_t = random.uniform(0.05, 0.25)
        if self.flash > 0.01:
            r, g, b = self.flash_rgb
            k = self.flash
            vs.fill((int(r * k * 0.5), int(g * k * 0.5), int(b * k * 0.5)), special_flags=pygame.BLEND_RGB_ADD)
            self.flash *= math.exp(-dt * 6)
        il = self.v('interlace')
        if il > 0:
            self._interlace(vs, il)
        if self.overlay:
            self._apply_overlay(vs)
        if self.lock is not None:
            self._apply_lock(vs)
        cv = self.v('curvature')
        if cv > 0:
            self._curve(vs, cv)

    def _curve(self, vs, amount):
        w, h = vs.get_size()
        key = (w, h, amount)
        if self.curve_key != key:
            self.curve_key = key
            x = np.linspace(-1, 1, w, dtype=np.float32)[:, None]
            y = np.linspace(-1, 1, h, dtype=np.float32)[None, :]
            r2 = x * x + y * y
            k = 1 + amount * 0.12 * r2
            sx = ((x * k + 1) / 2 * (w - 1))
            sy = ((y * k + 1) / 2 * (h - 1))
            self.cmask = (np.abs(x * k) <= 1) & (np.abs(y * k) <= 1)
            self.cx = np.clip(sx, 0, w - 1).astype(np.int32)
            self.cy = np.clip(sy, 0, h - 1).astype(np.int32)
            self.cx, self.cy = np.broadcast_arrays(self.cx, self.cy)
        src = pygame.surfarray.array3d(vs)
        out = src[self.cx, self.cy]
        out[~self.cmask] = 0
        pygame.surfarray.blit_array(vs, out)

    # ------------------------------------------------------------ window res
    def window(self, win, rect, scale, dt):
        sl = self.v('scanlines')
        vg = self.v('vignette')
        lcd = self.v('lcd')
        if sl > 0 or vg > 0 or lcd > 0:
            key = (rect.size, sl, vg, scale, lcd)
            if key != self.mult_key:
                self.mult_key = key
                self.mult = self._build_mult(rect.size, sl, vg, scale, lcd)
            win.blit(self.mult, rect.topleft, special_flags=pygame.BLEND_RGB_MULT)
        il = self.v('interlace')
        if il > 0 and scale >= 2:
            key = (rect.size, scale, il)
            if getattr(self, '_ilm_key', None) != key:
                self._ilm_key = key
                self._ilm = [self._field_mask(rect.size, scale, il, f) for f in (0, 1)]
            win.blit(self._ilm[getattr(self, 'field', 0)], rect.topleft, special_flags=pygame.BLEND_RGB_MULT)
        fl = self.v('flicker')
        if fl > 0:
            k = int(255 * (1 - fl * random.random()))
            win.fill((k, k, k), rect, special_flags=pygame.BLEND_RGB_MULT)
        nz = self.v('noise')
        if nz > 0:
            for _ in range(int(nz * 20)):
                y = random.randint(rect.top, rect.bottom - 1)
                c = random.randint(10, 40)
                win.fill((c, c, c), (rect.left, y, rect.width, 1), special_flags=pygame.BLEND_RGB_ADD)
            if random.random() < nz * 0.5:
                y = int((self.t * 120) % rect.height) + rect.top
                win.fill((14, 14, 14), (rect.left, y, rect.width, max(2, rect.height // 40)),
                         special_flags=pygame.BLEND_RGB_ADD)

    @staticmethod
    def _field_mask(size, scale, amount, field):
        w, h = size
        rows = (np.arange(h) // max(1, scale // 2)) % 2 == field
        line = np.where(rows, 1 - 0.45 * min(1.0, amount), 1.0).astype(np.float32)
        arr = np.repeat(np.repeat((line * 255).astype(np.uint8)[None, :, None], w, 0), 3, 2)
        s = pygame.Surface((w, h))
        pygame.surfarray.blit_array(s, arr)
        return s

    @staticmethod
    def _build_mult(size, sl, vg, scale, lcd=0.0):
        w, h = size
        x = np.linspace(-1, 1, w, dtype=np.float32)[:, None]
        y = np.linspace(-1, 1, h, dtype=np.float32)[None, :]
        m = np.ones((w, h), np.float32)
        if vg > 0:
            m *= np.clip(1 - vg * (x * x * 0.6 + y * y * 0.8) ** 1.5, 0, 1)
        if sl > 0:
            period = max(2, int(scale))
            rows = np.arange(h)[None, :] % period
            line = np.where(rows == period - 1, 1 - sl, 1.0).astype(np.float32)
            if period >= 3:
                line = np.where(rows == 0, 1 - sl * 0.35, line)
            m = m * line
        if lcd > 0 and scale >= 2:
            # dot-matrix LCD: dark gap between every virtual pixel (game boy screen)
            gx = (np.arange(w)[:, None] % scale) == scale - 1
            gy = (np.arange(h)[None, :] % scale) == scale - 1
            m = m * np.where(gx | gy, 1 - lcd, 1.0).astype(np.float32)
        arr = np.repeat((m * 255).astype(np.uint8)[:, :, None], 3, axis=2)
        s = pygame.Surface((w, h))
        pygame.surfarray.blit_array(s, arr)
        return s
