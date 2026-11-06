"""Background effects - classic demoscene routines, numpy-vectorized and
rendered at low resolution then scaled up (chunky pixels for free).

Layers stack: the first layer is drawn normally, every following layer is
added on top (BLEND_ADD). ``energy`` (0..~2) rises with terminal output so the
whole world reacts to your workload.
"""
from __future__ import annotations

import math
import random

import numpy as np
import pygame


class Background:
    name = 'base'
    opaque = False

    def __init__(self, w, h, params=None, theme=None):
        self.params = params or {}
        self.theme = theme
        self.t = 0.0
        self.resize(w, h)

    def p(self, key, default):
        return self.params.get(self.name, {}).get(key, default) if isinstance(self.params.get(self.name), dict) else default

    def resize(self, w, h):
        self.w, self.h = max(1, w), max(1, h)

    def update(self, dt, energy):
        self.t += dt * (1 + energy * 1.5)

    def draw(self, surf, first):
        pass


def _pal_surface(w, h, pal):
    s = pygame.Surface((w, h), 0, 8)
    s.set_palette(pal)
    return s


def _gradient_palette(stops, n=256):
    out = []
    for i in range(n):
        t = i / (n - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                k = (t - t0) / max(1e-6, t1 - t0)
                out.append(tuple(int(c0[j] + (c1[j] - c0[j]) * k) for j in range(3)))
                break
    return out


class Plasma(Background):
    name = 'plasma'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.lw, self.lh = max(2, w // 4), max(2, h // 4)
        self.low = _pal_surface(self.lw, self.lh, [(0, 0, 0)] * 256)
        x = np.linspace(0, 1, self.lw, dtype=np.float32)[:, None]
        y = np.linspace(0, 1, self.lh, dtype=np.float32)[None, :]
        self.X, self.Y = x * (self.lw / self.lh), y
        self.base_pal = [(int(128 + 127 * math.sin(math.pi * i / 32)),
                          int(128 + 127 * math.sin(math.pi * i / 64 + 2)),
                          int(128 + 127 * math.sin(math.pi * i / 128 + 4))) for i in range(256)]

    def draw(self, surf, first):
        t = self.t
        X, Y = self.X, self.Y
        v = (np.sin(X * 10 + t) + np.sin((Y * 8 + t) * 0.7) + np.sin((X * 6 + Y * 6 + t * 1.3))
             + np.sin(np.sqrt((X - 0.5 + 0.4 * math.sin(t * 0.3)) ** 2 * 80 + (Y - 0.5) ** 2 * 80) + t))
        idx = ((v + 4) * 32).astype(np.uint8)
        pygame.surfarray.blit_array(self.low, idx)
        sh = int(t * 40) & 255
        self.low.set_palette(self.base_pal[sh:] + self.base_pal[:sh])
        big = pygame.transform.scale(self.low, (self.w, self.h))
        surf.blit(big, (0, 0), special_flags=0 if first else pygame.BLEND_RGB_ADD)


class Fire(Background):
    name = 'fire'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.lw, self.lh = max(4, w // 3), max(4, h // 3)
        self.f = np.zeros((self.lw, self.lh), np.int16)
        pal = _gradient_palette([(0, (0, 0, 0)), (0.25, (90, 0, 0)), (0.5, (220, 50, 0)),
                                 (0.75, (255, 180, 20)), (1.0, (255, 255, 220))])
        self.low = _pal_surface(self.lw, self.lh, pal)

    def update(self, dt, energy):
        super().update(dt, energy)
        f = self.f
        lw, lh = self.lw, self.lh
        f[:, -1] = np.random.randint(160 + int(min(energy, 1.5) * 60), 256, lw)
        steps = 2
        for _ in range(steps):
            src = f[:, 1:]
            r = np.random.randint(0, 3, src.shape)
            xs = (np.arange(lw)[:, None] + r - 1) % lw
            shifted = src[xs, np.arange(lh - 1)[None, :]]
            decay = np.random.randint(0, 6 if energy < 0.5 else 4, src.shape)
            f[:, :-1] = np.maximum(shifted - decay * 2, 0)

    def draw(self, surf, first):
        pygame.surfarray.blit_array(self.low, np.clip(self.f, 0, 255).astype(np.uint8))
        big = pygame.transform.scale(self.low, (self.w, self.h))
        surf.blit(big, (0, 0), special_flags=0 if first else pygame.BLEND_RGB_ADD)


class Tunnel(Background):
    name = 'tunnel'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.lw, self.lh = max(4, w // 3), max(4, h // 3)
        x = np.arange(self.lw, dtype=np.float32)[:, None] - self.lw / 2
        y = np.arange(self.lh, dtype=np.float32)[None, :] - self.lh / 2
        d = np.sqrt(x * x + y * y) + 1e-3
        self.dist = (32 * 32 / d).astype(np.int32)
        self.ang = (128 * np.arctan2(y, x) / math.pi).astype(np.int32)
        self.shade = np.clip(d / (self.lw / 2), 0, 1)
        tx = np.arange(256)[:, None]
        ty = np.arange(256)[None, :]
        self.tex = ((tx ^ ty) & 255).astype(np.int32)
        self.low = pygame.Surface((self.lw, self.lh))
        c1 = self.p('color', None)
        self.tint = np.array(c1 if c1 else (255, 80, 220), np.float32) / 255

    def draw(self, surf, first):
        t = self.t
        u = (self.dist + int(t * 60)) & 255
        v = (self.ang + int(t * 25)) & 255
        val = self.tex[u, v].astype(np.float32) * self.shade
        rgb = np.empty((self.lw, self.lh, 3), np.uint8)
        rgb[..., 0] = val * self.tint[0]
        rgb[..., 1] = val * self.tint[1] * (0.6 + 0.4 * math.sin(t))
        rgb[..., 2] = val * self.tint[2]
        pygame.surfarray.blit_array(self.low, rgb)
        big = pygame.transform.scale(self.low, (self.w, self.h))
        surf.blit(big, (0, 0), special_flags=0 if first else pygame.BLEND_RGB_ADD)


class Starfield(Background):
    name = 'starfield'

    def resize(self, w, h):
        super().resize(w, h)
        n = int(self.p('count', 600))
        self.sx = np.random.uniform(-1, 1, n).astype(np.float32)
        self.sy = np.random.uniform(-1, 1, n).astype(np.float32)
        self.sz = np.random.uniform(0.05, 1, n).astype(np.float32)

    def update(self, dt, energy):
        super().update(dt, energy)
        self.sz -= dt * (0.25 + energy * 0.9)
        m = self.sz <= 0.02
        k = int(m.sum())
        if k:
            self.sx[m] = np.random.uniform(-1, 1, k)
            self.sy[m] = np.random.uniform(-1, 1, k)
            self.sz[m] = 1.0

    def draw(self, surf, first):
        if first:
            surf.fill((0, 0, 8))
        w, h = self.w, self.h
        px = (self.sx / self.sz * w * 0.5 + w / 2).astype(np.int32)
        py = (self.sy / self.sz * h * 0.5 + h / 2).astype(np.int32)
        ok = (px >= 0) & (px < w - 1) & (py >= 0) & (py < h - 1)
        px, py, z = px[ok], py[ok], self.sz[ok]
        b = np.clip((1 - z) * 300, 0, 255).astype(np.uint8)
        arr = pygame.surfarray.pixels3d(surf)
        col = np.stack([b, b, np.minimum(255, b.astype(np.int32) + 40).astype(np.uint8)], 1)
        arr[px, py] = np.maximum(arr[px, py], col)
        near = z < 0.3
        arr[px[near] + 1, py[near]] = np.maximum(arr[px[near] + 1, py[near]], col[near])
        arr[px[near], py[near] + 1] = np.maximum(arr[px[near], py[near] + 1], col[near])
        del arr


class Copper(Background):
    """Amiga copper / raster bars"""
    name = 'copper'

    def resize(self, w, h):
        super().resize(w, h)
        self.bh = max(8, h // 14)
        cols = [(255, 40, 40), (255, 160, 0), (255, 255, 60), (40, 255, 80), (40, 200, 255), (160, 60, 255), (255, 60, 200)]
        self.bars = []
        for c in cols:
            s = pygame.Surface((1, self.bh))
            for y in range(self.bh):
                k = 1 - abs(y - self.bh / 2) / (self.bh / 2)
                k = k ** 1.5
                s.set_at((0, y), (int(c[0] * k), int(c[1] * k), int(c[2] * k)))
            self.bars.append(pygame.transform.scale(s, (w, self.bh)))

    def draw(self, surf, first):
        """bars chase each other on a sine (about 1.4 swings per second), the
        swing width breathes; bg_params: copper: {speed: 1.0}"""
        if first:
            surf.fill((0, 0, 0))
        t = self.t * float(self.p('speed', 1.0))
        amp = self.h * (0.30 + 0.08 * math.sin(t * 0.9))
        for i, b in enumerate(self.bars):
            y = self.h / 2 + math.sin(t * 4.4 + i * 0.42) * amp - self.bh / 2
            surf.blit(b, (0, int(y)), special_flags=pygame.BLEND_RGB_ADD)


class Grid(Background):
    """synthwave sun + perspective grid"""
    name = 'grid'

    def resize(self, w, h):
        super().resize(w, h)
        self.sun = pygame.Surface((w // 3, w // 3))
        r = w // 6
        for y in range(w // 3):
            k = y / (w // 3)
            c = (255, int(220 - 180 * k), int(80 + 120 * k))
            dx = int(math.sqrt(max(0, r * r - (y - r) ** 2)))
            if not (k > 0.5 and int(y / (3 + 6 * k)) % 2):
                pygame.draw.line(self.sun, c, (r - dx, y), (r + dx, y))

    def draw(self, surf, first):
        w, h = self.w, self.h
        hz = int(h * 0.55)
        if first:
            for y in range(0, hz, 4):
                k = y / hz
                surf.fill((int(20 + 60 * k), int(5 + 10 * k), int(40 + 50 * k)), (0, y, w, 4))
            surf.fill((10, 0, 20), (0, hz, w, h - hz))
        surf.blit(self.sun, (w // 2 - self.sun.get_width() // 2, hz - self.sun.get_height() * 2 // 3),
                  special_flags=pygame.BLEND_RGB_ADD)
        surf.fill((10, 0, 20), (0, hz, w, h - hz))
        col = (255, 40, 200)
        for i in range(-20, 21):
            x0 = w / 2 + i * w / 40
            x1 = w / 2 + i * w / 4
            pygame.draw.line(surf, col, (x0, hz), (x1, h))
        off = (self.t * 0.6) % 1
        for j in range(14):
            z = (j + 1 - off)
            y = hz + (h - hz) * (1 / z) ** 0.9 * 0.9
            if hz < y < h:
                pygame.draw.line(surf, col, (0, y), (w, y))


class Matrix(Background):
    name = 'matrix'

    def resize(self, w, h):
        super().resize(w, h)
        self.cell = 8
        self.ncol = w // self.cell + 1
        self.heads = np.random.uniform(-h, h, self.ncol)
        self.speed = np.random.uniform(40, 160, self.ncol)
        self.layer = pygame.Surface((w, h))
        self.layer.fill((0, 0, 0))
        self.font = pygame.font.Font(None, 12)
        pool = '0123456789ABCDEFZ$#*+<>=:|'
        self.glyphs = [self.font.render(c, False, (40 + 30 * k, 255 - 40 * k, 90)) for c in pool for k in range(3)]
        self.white = [self.font.render(c, False, (230, 255, 230)) for c in pool]

    def update(self, dt, energy):
        super().update(dt, energy)
        self.heads += self.speed * dt * (1 + energy)
        m = self.heads > self.h + 50
        self.heads[m] = np.random.uniform(-200, 0, int(m.sum()))
        self.layer.fill((228, 238, 228), special_flags=pygame.BLEND_RGB_MULT)
        for i in range(self.ncol):
            if random.random() < 0.6:
                y = int(self.heads[i] // self.cell * self.cell)
                if 0 <= y < self.h:
                    self.layer.blit(random.choice(self.glyphs), (i * self.cell, y))
                    self.layer.blit(random.choice(self.white), (i * self.cell, y + self.cell))

    def draw(self, surf, first):
        surf.blit(self.layer, (0, 0), special_flags=0 if first else pygame.BLEND_RGB_ADD)


class Metaballs(Background):
    name = 'metaballs'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.lw, self.lh = max(4, w // 5), max(4, h // 5)
        self.X = np.arange(self.lw, dtype=np.float32)[:, None]
        self.Y = np.arange(self.lh, dtype=np.float32)[None, :]
        pal = _gradient_palette([(0, (0, 0, 10)), (0.45, (0, 20, 60)), (0.55, (0, 200, 255)),
                                 (0.7, (180, 60, 255)), (1, (255, 255, 255))])
        self.low = _pal_surface(self.lw, self.lh, pal)

    def draw(self, surf, first):
        t = self.t
        f = np.zeros((self.lw, self.lh), np.float32)
        for i in range(6):
            bx = self.lw * (0.5 + 0.4 * math.sin(t * (0.5 + i * 0.13) + i))
            by = self.lh * (0.5 + 0.4 * math.cos(t * (0.4 + i * 0.17) + i * 2))
            f += (self.lw * 0.06) ** 2 / ((self.X - bx) ** 2 + (self.Y - by) ** 2 + 1)
        pygame.surfarray.blit_array(self.low, np.clip(f * 110, 0, 255).astype(np.uint8))
        big = pygame.transform.scale(self.low, (self.w, self.h))
        surf.blit(big, (0, 0), special_flags=0 if first else pygame.BLEND_RGB_ADD)


class Rasterwave(Background):
    """horizontal sine-distorted rainbow gradient (C64 demo vibe)"""
    name = 'rasterwave'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.strip = pygame.Surface((1, 256))
        for i in range(256):
            self.strip.set_at((0, i), (int(127 + 127 * math.sin(i / 40.7)), int(127 + 127 * math.sin(i / 40.7 + 2)),
                                       int(127 + 127 * math.sin(i / 40.7 + 4))))

    def draw(self, surf, first):
        h = self.h
        step = 3
        for y in range(0, h, step):
            i = int(y + 40 * math.sin(y * 0.02 + self.t * 2) + self.t * 50) & 255
            c = self.strip.get_at((0, i))
            surf.fill((c[0] // 3, c[1] // 3, c[2] // 3), (0, y, self.w, step),
                      special_flags=0 if first else pygame.BLEND_RGB_ADD)


class Shadebobs(Background):
    """classic shadebobs: soft blobs added into a wrapping 8-bit buffer"""
    name = 'shadebobs'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.lw, self.lh = max(8, w // 3), max(8, h // 3)
        self.buf = np.zeros((self.lw, self.lh), np.int32)
        r = max(4, self.lh // 7)
        yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
        d = np.sqrt(xx * xx + yy * yy) / r
        self.stamp = (np.clip(1 - d, 0, 1) * 6).astype(np.int32).T
        self.r = r
        pal = self.p('palette', None)
        if pal == 'fire':
            self.pal = _gradient_palette([(0, (0, 0, 0)), (0.3, (120, 0, 40)), (0.6, (255, 100, 0)), (0.85, (255, 230, 80)), (1, (255, 255, 255))])
        else:
            self.pal = _gradient_palette([(0, (0, 0, 0)), (0.25, (20, 30, 160)), (0.5, (200, 40, 200)),
                                          (0.75, (255, 140, 30)), (1, (255, 255, 220))])
        self.low = _pal_surface(self.lw, self.lh, self.pal)
        self.nbobs = int(self.p('bobs', 5))

    def update(self, dt, energy):
        super().update(dt, energy)
        t = self.t
        r = self.r
        for i in range(self.nbobs):
            x = int((self.lw - 2 * r - 1) * (0.5 + 0.48 * math.sin(t * (0.9 + i * 0.17) + i * 1.3)))
            y = int((self.lh - 2 * r - 1) * (0.5 + 0.48 * math.sin(t * (1.3 + i * 0.11) + i * 2.1)))
            self.buf[x:x + 2 * r + 1, y:y + 2 * r + 1] += self.stamp
        self.buf &= 255

    def draw(self, surf, first):
        pygame.surfarray.blit_array(self.low, self.buf.astype(np.uint8))
        surf.blit(pygame.transform.scale(self.low, (self.w, self.h)), (0, 0),
                  special_flags=0 if first else pygame.BLEND_RGB_ADD)


class Rotozoom(Background):
    """rotating, zooming checker/XOR texture"""
    name = 'rotozoom'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.lw, self.lh = max(8, w // 3), max(8, h // 3)
        x = np.arange(self.lw, dtype=np.float32) - self.lw / 2
        y = np.arange(self.lh, dtype=np.float32) - self.lh / 2
        self.X, self.Y = np.meshgrid(x, y, indexing='ij')
        tx, ty = np.meshgrid(np.arange(64), np.arange(64), indexing='ij')
        checker = ((tx // 8 + ty // 8) % 2) * 120
        tex = np.stack([checker + (tx ^ ty) * 2, checker // 2 + tx * 2, 200 - checker + ty * 0], -1)
        self.tex = np.clip(tex, 0, 255).astype(np.uint8)
        self.low = pygame.Surface((self.lw, self.lh))

    def draw(self, surf, first):
        t = self.t
        a = t * 0.5
        z = 0.6 + 0.45 * math.sin(t * 0.7)
        ca, sa = math.cos(a) * z, math.sin(a) * z
        u = ((self.X * ca - self.Y * sa) + t * 30).astype(np.int32) & 63
        v = ((self.X * sa + self.Y * ca) + t * 10).astype(np.int32) & 63
        pygame.surfarray.blit_array(self.low, self.tex[u, v])
        surf.blit(pygame.transform.scale(self.low, (self.w, self.h)), (0, 0),
                  special_flags=0 if first else pygame.BLEND_RGB_ADD)


class Twister(Background):
    """amiga style twisting bar"""
    name = 'twister'

    def resize(self, w, h):
        super().resize(w, h)
        self.lw, self.lh = max(8, w // 2), max(8, h // 2)
        self.low = pygame.Surface((self.lw, self.lh))
        self.cols = [(255, 60, 90), (60, 200, 255), (255, 210, 60), (120, 255, 120)]

    def draw(self, surf, first):
        low = self.low
        low.fill((0, 0, 0))
        t = self.t
        cx = self.lw * (0.5 + 0.12 * math.sin(t * 0.4))
        bw = self.lw * 0.16
        for y in range(0, self.lh, 1):
            a = t * 1.5 + y * 0.025 + math.sin(y * 0.012 + t) * 1.6
            xs = [cx + math.sin(a + k * math.pi / 2) * bw for k in range(4)]
            for k in range(4):
                x1, x2 = xs[k], xs[(k + 1) % 4]
                if x2 > x1:
                    shade = 0.35 + 0.65 * (x2 - x1) / (bw * 1.42)
                    c = self.cols[k]
                    low.fill((int(c[0] * shade), int(c[1] * shade), int(c[2] * shade)), (int(x1), y, max(1, int(x2 - x1)), 1))
        if first:
            surf.fill((0, 0, 0))
        surf.blit(pygame.transform.scale(low, (self.w, self.h)), (0, 0), special_flags=pygame.BLEND_RGB_ADD)


class Boing(Background):
    """the Amiga boing ball, with grid and shadow"""
    name = 'boing'

    def resize(self, w, h):
        super().resize(w, h)
        self.R = max(10, min(w, h) // 6)
        R = self.R
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        d2 = (xx * xx + yy * yy) / (R * R)
        self.mask = (d2 <= 1).T
        z = np.sqrt(np.clip(1 - d2, 0, 1))
        # tilt the ball
        tilt = 0.35
        x2 = xx / R * math.cos(tilt) - yy / R * math.sin(tilt)
        y2 = xx / R * math.sin(tilt) + yy / R * math.cos(tilt)
        self.lat = np.arcsin(np.clip(y2, -1, 1)).T
        self.lon = np.arctan2(x2, z).T
        self.light = np.clip(0.55 + 0.45 * (z.T * 0.8 - (xx / R).T * 0.3 - (yy / R).T * 0.3), 0.25, 1)
        self.ball = pygame.Surface((2 * R + 1, 2 * R + 1), pygame.SRCALPHA)
        self.shadow = pygame.Surface((2 * R + 1, 2 * R + 1), pygame.SRCALPHA)
        self.shadow.fill((0, 0, 0, 0))
        pygame.draw.circle(self.shadow, (0, 0, 0, 110), (R, R), R)
        self.x, self.y = w * 0.3, h * 0.2
        self.vx, self.vy = w * 0.18, 0.0
        self.grid = pygame.Surface((w, h))
        self.grid.fill((170, 170, 170))
        step = max(8, h // 12)
        for gx in range(0, w, step):
            pygame.draw.line(self.grid, (160, 40, 160), (gx, 0), (gx, int(h * 0.85)))
        for gy in range(0, int(h * 0.85), step):
            pygame.draw.line(self.grid, (160, 40, 160), (0, gy), (w, gy))
        base = int(h * 0.85)
        for i in range(-w // step, w // step * 2):
            pygame.draw.line(self.grid, (160, 40, 160), (w / 2 + (i * step - w / 2) * 0.7, base), (w / 2 + (i * step - w / 2) * 1.4, h))
        k = 0
        y = base
        while y < h:
            pygame.draw.line(self.grid, (160, 40, 160), (0, y), (w, y))
            k += 1
            y += 2 + k * 2

    def update(self, dt, energy):
        super().update(dt, energy)
        dt = dt * (1 + energy)
        g = self.h * 1.6
        self.vy += g * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        R = self.R
        floor = self.h * 0.85 - R
        if self.y > floor:
            self.y = floor
            self.vy = -math.sqrt(2 * g * (floor - self.h * 0.12))
        if self.x < R or self.x > self.w - R:
            self.vx = -self.vx
            self.x = max(R, min(self.w - R, self.x))

    def draw(self, surf, first):
        if first:
            surf.blit(self.grid, (0, 0))
        phase = self.t * (2.0 if self.vx > 0 else -2.0)
        chk = ((np.floor((self.lon + phase) / (math.pi / 8)) + np.floor(self.lat / (math.pi / 8))) % 2).astype(bool)
        r = np.where(chk, 230, 255) * self.light
        gb = np.where(chk, 30, 255) * self.light
        arr = pygame.surfarray.pixels3d(self.ball)
        arr[..., 0] = r.astype(np.uint8)
        arr[..., 1] = gb.astype(np.uint8)
        arr[..., 2] = gb.astype(np.uint8)
        del arr
        a = pygame.surfarray.pixels_alpha(self.ball)
        a[:] = self.mask * 255
        del a
        R = self.R
        surf.blit(self.shadow, (int(self.x - R + R * 0.4), int(self.y - R + R * 0.15)))
        surf.blit(self.ball, (int(self.x - R), int(self.y - R)))


class Vectorballs(Background):
    """rotating 3D object made of shaded balls"""
    name = 'vectorballs'

    def resize(self, w, h):
        super().resize(w, h)
        pts = []
        n = 4
        for x in range(n):
            for y in range(n):
                for z in range(n):
                    if x in (0, n - 1) or y in (0, n - 1) or z in (0, n - 1):
                        pts.append((x / (n - 1) - 0.5, y / (n - 1) - 0.5, z / (n - 1) - 0.5))
        self.P = np.array(pts, np.float32)
        self.balls = []
        for i, c in enumerate([(255, 80, 80), (80, 200, 255), (255, 220, 80)]):
            rr = max(4, h // 28)
            b = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
            for k in range(rr, 0, -1):
                f = 0.35 + 0.65 * (1 - k / rr)
                pygame.draw.circle(b, (int(c[0] * f), int(c[1] * f), int(c[2] * f), 255),
                                   (rr - (rr - k) // 3, rr - (rr - k) // 3), k)
            self.balls.append(b)
        self.cache = {}

    def draw(self, surf, first):
        if first:
            surf.fill((0, 0, 12))
        t = self.t
        a, b = t * 0.7, t * 0.5
        ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
        P = self.P
        x = P[:, 0] * ca - P[:, 2] * sa
        z = P[:, 0] * sa + P[:, 2] * ca
        y = P[:, 1] * cb - z * sb
        z = P[:, 1] * sb + z * cb
        scale = min(self.w, self.h) * 0.9
        persp = 1.0 / (z + 2.2)
        sx = self.w / 2 + x * scale * persp + math.sin(t * 0.6) * self.w * 0.2
        sy = self.h / 2 + y * scale * persp
        order = np.argsort(-z)
        for i in order:
            k = round(float(persp[i]) * 3, 1)
            bi = i % 3
            key = (bi, k)
            img = self.cache.get(key)
            if img is None:
                base = self.balls[bi]
                sz = max(2, int(base.get_width() * k / 1.4))
                img = pygame.transform.smoothscale(base, (sz, sz))
                self.cache[key] = img
            surf.blit(img, (int(sx[i]) - img.get_width() // 2, int(sy[i]) - img.get_height() // 2))


class Parallax(Background):
    """side-scrolling parallax: stars, far & near mountains (8-bit console vibe)"""
    name = 'parallax'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        rng = random.Random(7)
        self.stars = [(rng.uniform(0, w), rng.uniform(0, h * 0.6), rng.choice((1, 1, 2))) for _ in range(120)]
        cols = self.p('colors', None) or [(16, 16, 48), (40, 30, 90), (70, 40, 120), (20, 90, 60), (10, 50, 30)]
        self.sky, self.far_c, self.mid_c, self.near_c, self.ground_c = [tuple(c) for c in cols]
        self.layers = []
        for i, (col, hmin, hmax, step) in enumerate(((self.far_c, 0.35, 0.6, 18), (self.mid_c, 0.5, 0.75, 12),
                                                     (self.near_c, 0.68, 0.9, 8))):
            s = pygame.Surface((w * 2, h), pygame.SRCALPHA)
            s.fill((0, 0, 0, 0))
            pts = [(0, h)]
            x = 0
            while x <= w:
                pts.append((x, h * rng.uniform(hmin, hmax)))
                x += step
            pts[-1] = (w, pts[1][1])
            pts.append((w, h))
            pygame.draw.polygon(s, col, pts)
            s.blit(s, (w, 0), (0, 0, w, h))
            self.layers.append(s)

    def draw(self, surf, first):
        t = self.t
        surf.fill(self.sky)
        for x, y, z in self.stars:
            xx = int((x - t * 6 * z) % self.w)
            surf.fill((200, 200, 255) if z > 1 else (120, 120, 170), (xx, int(y), z, z))
        for i, s in enumerate(self.layers):
            off = int(t * (12 + i * 22)) % self.w
            surf.blit(s, (-off, 0))
        surf.fill(self.ground_c, (0, int(self.h * 0.93), self.w, self.h))


def _pix(rows, pal, k=1):
    s = pygame.Surface((len(rows[0]), len(rows)), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c in pal:
                s.set_at((x, y), pal[c])
    return pygame.transform.scale(s, (s.get_width() * k, s.get_height() * k)) if k > 1 else s


class Platformer(Background):
    """endless side-scrolling jump'n'run world: clouds, hills, brick ground,
    floating platforms, bonus blocks, spinning coins and patrolling slimes"""
    name = 'platformer'
    opaque = True
    T = 8

    def resize(self, w, h):
        super().resize(w, h)
        T = self.T
        self.sky = tuple(self.p('sky', (92, 148, 252)))
        brick = {'b': (200, 76, 12), 'd': (120, 40, 0), 'l': (252, 152, 56)}
        self.ground = _pix(["llllllll", "bbbdbbbb", "bbbdbbbb", "dddddddd", "bdbbbbbd", "bdbbbbbd", "dddddddd", "bbbbdbbb"], brick)
        self.grass = _pix(["gggggggg", "GgGGgGgG", "bbbbbbbb", "bbbdbbbb", "dddddddd", "bdbbbbbd", "bdbbbbbd", "dddddddd"],
                          dict(brick, g=(128, 208, 16), G=(0, 168, 0)))
        self.block = [_pix(["dddddddd", "dyyyyyyd", "dyywwyyd", "dyw..wyd", "dyy.wyyd", "dyyyyyyd", "dyy.yyyd", "dddddddd"],
                           {'d': (140, 70, 0), 'y': c, 'w': (255, 255, 255), '.': (140, 70, 0)})
                      for c in ((252, 188, 60), (255, 220, 120), (240, 160, 40))]
        self.plat = _pix(["llllllll", "bdbbbdbb", "dddddddd", "........"], brick)
        self.coin = [_pix(r, {'y': (255, 210, 40), 'w': (255, 250, 200)}) for r in (
            ["..yy..", ".ywyy.", ".ywyy.", ".ywyy.", ".yyyy.", "..yy.."],
            ["..yy..", "..wy..", "..wy..", "..wy..", "..yy..", "..yy.."],
            ["...y..", "...y..", "...y..", "...y..", "...y..", "...y.."])]
        self.slime = [_pix(r, {'g': (60, 200, 80), 'G': (20, 120, 40), 'w': (255, 255, 255), 'k': (0, 0, 0)}) for r in (
            ["..gggg..", ".gggggg.", "gwkggwkg", "gggggggg", "GGGGGGGG"],
            ["........", "..gggg..", "gwkggwkg", "gggggggg", "GGGGGGGG"])]
        self.cloud = _pix(["...wwww.....", ".wwwwwwww...", "wwwwwwwwwwww", ".wwwwwwwwww."], {'w': (255, 255, 255)}, 2)
        self.hill = pygame.Surface((T * 10, T * 5), pygame.SRCALPHA)
        self.hill.fill((0, 0, 0, 0))
        pygame.draw.ellipse(self.hill, (0, 168, 0), (0, 0, T * 10, T * 10))
        pygame.draw.ellipse(self.hill, (0, 120, 0), (T * 3, T, T, T // 2))
        self.cols_cache = {}
        self.scroll = 0.0
        self.slimes = []

    def column(self, c):
        col = self.cols_cache.get(c)
        if col is None:
            r = random.Random(c * 7919 + 13)
            ground = 2 if r.random() > 0.08 or c % 37 < 3 else 0       # pits
            plat = None
            if c % 23 in range(4, 9):
                plat = ('plat', 6)
            if c % 17 in (10, 11, 12):
                plat = ('block', 5 + (c % 17 == 11))
            coin = r.random() < 0.25
            col = (ground, plat, coin)
            self.cols_cache[c] = col
            if len(self.cols_cache) > 4000:
                self.cols_cache.clear()
        return col

    def update(self, dt, energy):
        super().update(dt, energy)
        self.scroll += dt * (18 + energy * 50)
        T = self.T
        if random.random() < dt * 0.6 and len(self.slimes) < 6:
            self.slimes.append([self.scroll + self.w + T, random.choice((-1, 1)) * 10])
        for sl in self.slimes:
            sl[0] += sl[1] * dt
        self.slimes = [sl for sl in self.slimes if sl[0] > self.scroll - 2 * T]

    def draw(self, surf, first):
        T = self.T
        h = self.h
        surf.fill(self.sky)
        # parallax clouds & hills
        for i in range(6):
            x = (i * 157 - self.scroll * 0.25) % (self.w + 120) - 60
            surf.blit(self.cloud, (x, 12 + (i * 37) % (h // 3)))
        gy = h - 2 * T
        for i in range(5):
            x = (i * 211 - self.scroll * 0.5) % (self.w + 200) - 100
            surf.blit(self.hill, (x, gy - self.hill.get_height() + T))
        c0 = int(self.scroll // T)
        off = int(self.scroll % T)
        ci = int(self.t * 8) % 4
        for i in range(self.w // T + 2):
            c = c0 + i
            x = i * T - off
            ground, plat, coin = self.column(c)
            if ground:
                surf.blit(self.grass, (x, gy))
                surf.blit(self.ground, (x, gy + T))
            if plat:
                kind, row = plat
                y = gy - row * T
                if kind == 'plat':
                    surf.blit(self.plat, (x, y))
                else:
                    surf.blit(self.block[int(self.t * 3) % 3], (x, y))
                if coin:
                    cimg = self.coin[(0, 1, 2, 1)[ci]]
                    surf.blit(cimg, (x + 1, y - T + int(math.sin(self.t * 4 + c) * 1.5)))
            elif coin and ground and c % 3 == 0:
                cimg = self.coin[(0, 1, 2, 1)[ci]]
                surf.blit(cimg, (x + 1, gy - 2 * T))
        fi = int(self.t * 4) % 2
        for sx, v in self.slimes:
            x = sx - self.scroll
            img = self.slime[fi]
            if v < 0:
                img = pygame.transform.flip(img, True, False)
            surf.blit(img, (x, gy - img.get_height()))


class Invaders(Background):
    """arcade attract mode: a marching alien armada, a cannon that aims at the
    letters you type (with the 'shoot' letter effect), a mystery ship and explosions"""
    name = 'invaders'

    ALIENS = [
        (["..X..X..", ".XXXXXX.", "XX.XX.XX", "XXXXXXXX", ".X.XX.X.", "X......X"],
         ["..X..X..", ".XXXXXX.", "XX.XX.XX", "XXXXXXXX", ".X.XX.X.", "..X..X.."]),
        (["...XX...", "..XXXX..", ".X.XX.X.", ".XXXXXX.", "..X..X..", ".X.XX.X."],
         ["...XX...", "..XXXX..", ".X.XX.X.", ".XXXXXX.", "..X..X..", "X.X..X.X"]),
        (["..XXXX..", ".XXXXXX.", "XXX..XXX", "XXXXXXXX", "..X..X..", ".X....X."],
         ["..XXXX..", ".XXXXXX.", "XXX..XXX", "XXXXXXXX", ".X.XX.X.", "X......X"]),
    ]
    CANNON = ["...X...", "..XXX..", ".XXXXX.", "XXXXXXX"]
    UFO = ["..XXXX..", ".XXXXXX.", "XX.XX.XX", ".XXXXXX."]
    BOOM = ["X..X..X", ".X.X.X.", "..XXX..", "XXX.XXX", "..XXX..", ".X.X.X.", "X..X..X"]

    def resize(self, w, h):
        super().resize(w, h)
        self.k = max(1, h // 140)
        k = self.k
        white = {'X': (255, 255, 255)}
        self.sprites = [[_pix(f, white, k) for f in pair] for pair in self.ALIENS]
        self.cannon = _pix(self.CANNON, {'X': (80, 255, 80)}, k)
        self.ufo = _pix(self.UFO, {'X': (255, 60, 60)}, k)
        self.boom = _pix(self.BOOM, white, k)
        self.new_wave()
        self.cx = w / 2
        self.shots = []
        self.bombs = []
        self.booms = []
        self.ufo_x = None
        self.score = 0
        self.fire_cd = 0.0

    def new_wave(self):
        k = self.k
        self.ax, self.ay = 10.0 * k, 24.0 * k
        self.dir = 1
        self.alive = [[True] * 11 for _ in range(5)]
        self.step_t = 0.0
        self.frame = 0
        self.sp = (12 * k, 10 * k)

    def update(self, dt, energy):
        super().update(dt, energy)
        from .effects import Shoot
        k = self.k
        n_alive = sum(map(sum, self.alive))
        if n_alive == 0:
            self.new_wave()
            return
        # march: faster when fewer aliens remain
        self.step_t += dt
        interval = 0.05 + 0.5 * n_alive / 55
        if self.step_t > interval:
            self.step_t = 0
            self.frame ^= 1
            self.ax += 2 * k * self.dir
            cols = [c for c in range(11) if any(self.alive[r][c] for r in range(5))]
            left = self.ax + cols[0] * self.sp[0]
            right = self.ax + cols[-1] * self.sp[0] + 8 * k
            if right > self.w - 4 or left < 4:
                self.dir *= -1
                self.ay += 4 * k
                if self.ay > self.h * 0.55:
                    self.new_wave()
        # cannon: aim at typed letters, otherwise at the lowest alien column
        target = None
        if Shoot.TARGETS:
            target = Shoot.TARGETS.pop(0) * self.w
        else:
            cols = [c for c in range(11) if any(self.alive[r][c] for r in range(5))]
            if cols:
                target = self.ax + cols[int(self.t) % len(cols)] * self.sp[0] + 4 * k
        if target is not None:
            self.cx += max(-120 * dt * (1 + energy), min(120 * dt * (1 + energy), target - self.cx))
        self.fire_cd -= dt
        if self.fire_cd <= 0:
            self.fire_cd = 0.45 / (1 + energy)
            self.shots.append([self.cx, self.h - 8 * k])
        for s in self.shots:
            s[1] -= 260 * k * dt
        # hits
        keep = []
        for s in self.shots:
            hit = False
            c = int((s[0] - self.ax) // self.sp[0])
            r = int((s[1] - self.ay) // self.sp[1])
            if 0 <= c < 11 and 0 <= r < 5 and self.alive[r][c]:
                lx = s[0] - self.ax - c * self.sp[0]
                ly = s[1] - self.ay - r * self.sp[1]
                if 0 <= lx < 8 * k and 0 <= ly < 6 * k:
                    self.alive[r][c] = False
                    self.booms.append([self.ax + c * self.sp[0], self.ay + r * self.sp[1], 0.25])
                    self.score += 10 * (3 - r // 2)
                    hit = True
            if self.ufo_x is not None and abs(s[0] - self.ufo_x - 4 * k) < 5 * k and s[1] < 14 * k:
                self.booms.append([self.ufo_x, 8 * k, 0.4])
                self.ufo_x = None
                self.score += 300
                hit = True
            if not hit and s[1] > 0:
                keep.append(s)
        self.shots = keep
        # bombs
        if random.random() < dt * 1.5:
            cols = [c for c in range(11) if any(self.alive[r][c] for r in range(5))]
            if cols:
                c = random.choice(cols)
                r = max(r for r in range(5) if self.alive[r][c])
                self.bombs.append([self.ax + c * self.sp[0] + 4 * k, self.ay + r * self.sp[1] + 6 * k])
        for b in self.bombs:
            b[1] += 90 * k * dt
        self.bombs = [b for b in self.bombs if b[1] < self.h]
        for b in self.booms:
            b[2] -= dt
        self.booms = [b for b in self.booms if b[2] > 0]
        # mystery ship
        if self.ufo_x is None and random.random() < dt * 0.08:
            self.ufo_x = -10.0 * k
        if self.ufo_x is not None:
            self.ufo_x += 50 * k * dt
            if self.ufo_x > self.w:
                self.ufo_x = None

    def draw(self, surf, first):
        if first:
            surf.fill((0, 0, 0))
        k = self.k
        for r in range(5):
            spr = self.sprites[0 if r == 0 else (1 if r < 3 else 2)][self.frame]
            for c in range(11):
                if self.alive[r][c]:
                    surf.blit(spr, (int(self.ax + c * self.sp[0]), int(self.ay + r * self.sp[1])))
        for x, y, t in self.booms:
            surf.blit(self.boom, (int(x), int(y)))
        if self.ufo_x is not None:
            surf.blit(self.ufo, (int(self.ufo_x), 8 * k))
        for x, y in self.shots:
            surf.fill((255, 255, 255), (int(x), int(y), k, 4 * k))
        for x, y in self.bombs:
            surf.fill((255, 255, 255), (int(x) + (int(y / (3 * k)) % 2) * k, int(y), k, 3 * k))
        surf.blit(self.cannon, (int(self.cx - 3.5 * k), self.h - 6 * k))
        surf.fill((80, 255, 80), (0, self.h - k, self.w, k))


BACKGROUNDS = {c.name: c for c in (Plasma, Fire, Tunnel, Starfield, Copper, Grid, Matrix, Metaballs, Rasterwave,
                                        Shadebobs, Rotozoom, Twister, Boing, Vectorballs, Parallax,
                                        Platformer, Invaders)}


class BackgroundStack:
    def __init__(self, names, w, h, params=None, theme=None, registry=None):
        reg = registry or BACKGROUNDS
        self.layers = []
        for n in names:
            if n in ('none', 'mine', ''):
                continue
            c = reg.get(n)
            if c:
                self.layers.append(c(w, h, params or {}, theme))
            else:
                print('[pixelterm] unknown background %s' % n)

    def resize(self, w, h):
        for l in self.layers:
            l.resize(w, h)

    def update(self, dt, energy):
        for l in self.layers:
            l.update(dt, energy)

    def draw(self, surf, bg_rgb, dim):
        if not self.layers:
            surf.fill(bg_rgb)
            return
        if not self.layers[0].opaque:
            surf.fill(bg_rgb)
        for i, l in enumerate(self.layers):
            l.draw(surf, i == 0)
        if dim < 1:
            d = int(255 * dim)
            surf.fill((d, d, d), special_flags=pygame.BLEND_RGB_MULT)


# live weather lives in its own module (network feed); registered here
from .weather import Weather  # noqa: E402

BACKGROUNDS['weather'] = Weather

# living scenes (dollhouse, railway, settlers, discocity)
from .scenes import SCENES  # noqa: E402

BACKGROUNDS.update(SCENES)

# water mirror (mirrors the layers below it and the terminal text)
from .water import WaterMirror  # noqa: E402

BACKGROUNDS['watermirror'] = WaterMirror

# more living scenes (aquarium, spacestation, garden, pinball, c64load, beach)
from .scenes2 import SCENES2  # noqa: E402

BACKGROUNDS.update(SCENES2)

# seasonal & holiday scenes
from .seasons import SEASONS  # noqa: E402

BACKGROUNDS.update(SEASONS)
from .seasons2 import SEASONS2  # noqa: E402

BACKGROUNDS.update(SEASONS2)

# roman stone tablet
from .roman import Stone  # noqa: E402

BACKGROUNDS['stone'] = Stone
