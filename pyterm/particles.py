"""Vectorized (numpy) particle engine.

All particles live in *virtual terminal space*: y grows with every line the
screen scrolls, so a full-screen scroll is O(1) - we just move the camera.
Drawing writes straight into the target surface via surfarray (one fancy-
index assignment for tens of thousands of particles).
"""
from __future__ import annotations

import numpy as np
import pygame

# palettes / color modes
SOLID, FIRE, FADE, SPARKLE, FLASH, COOL, RAINBOW = range(7)
# motion
BALLISTIC, HOMING = 0, 1
# easing (homing)
SMOOTH, FALL, BACK, LINEAR = range(4)


def _lut(stops):
    lut = np.zeros((256, 3), np.float32)
    for i in range(256):
        t = i / 255
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                k = (t - t0) / max(1e-6, t1 - t0)
                lut[i] = [c0[j] + (c1[j] - c0[j]) * k for j in range(3)]
                break
    return lut


FIRE_LUT = _lut([(0, (255, 255, 230)), (0.15, (255, 230, 90)), (0.4, (255, 130, 10)),
                 (0.7, (190, 35, 0)), (1.0, (40, 0, 0))])
RAINBOW_LUT = np.array([[127 + 127 * np.sin(i / 256 * 6.283 + p) for p in (0, 2.09, 4.18)]
                        for i in range(256)], np.float32)


class Particles:
    FIELDS_F = ('x', 'y', 'vx', 'vy', 'sx', 'sy', 'tx', 'ty', 'age', 'life', 'travel', 'grav', 'drag')
    FIELDS_I = ('kind', 'pal', 'ease', 'add')

    def __init__(self, capacity=120000, size=1):
        self.cap = capacity
        self.n = 0
        self.size = size
        for f in self.FIELDS_F:
            setattr(self, f, np.zeros(capacity, np.float32))
        for f in self.FIELDS_I:
            setattr(self, f, np.zeros(capacity, np.int8))
        self.col = np.zeros((capacity, 3), np.float32)
        self.rng = np.random.default_rng()

    def clear(self):
        self.n = 0

    @property
    def free(self):
        return self.cap - self.n

    def emit(self, count, x, y, vx=0.0, vy=0.0, life=1.0, col=(255, 255, 255), pal=SOLID,
             kind=BALLISTIC, tx=None, ty=None, travel=0.3, ease=SMOOTH, grav=0.0, drag=0.0,
             add=False, delay=0.0):
        count = int(min(count, self.cap - self.n))
        if count <= 0:
            return 0
        a, b = self.n, self.n + count

        def put(arr, v):
            if isinstance(v, np.ndarray):
                arr[a:b] = v[:count]
            else:
                arr[a:b] = v

        put(self.x, x)
        put(self.y, y)
        put(self.sx, x)
        put(self.sy, y)
        put(self.vx, vx)
        put(self.vy, vy)
        put(self.life, life)
        put(self.travel, travel)
        put(self.grav, grav)
        put(self.drag, drag)
        put(self.kind, kind)
        put(self.pal, pal)
        put(self.ease, ease)
        put(self.add, 1 if add is True else (0 if add is False else add))
        put(self.tx, x if tx is None else tx)
        put(self.ty, y if ty is None else ty)
        if isinstance(delay, np.ndarray):
            self.age[a:b] = -delay[:count]
        else:
            self.age[a:b] = -delay
        c = np.asarray(col, np.float32)
        if c.ndim == 1:
            self.col[a:b] = c
        else:
            self.col[a:b] = c[:count]
        self.n = b
        return count

    def update(self, dt):
        n = self.n
        if n == 0:
            return
        age = self.age[:n]
        age += dt
        act = age >= 0
        kind = self.kind[:n]
        vx, vy = self.vx[:n], self.vy[:n]
        x, y = self.x[:n], self.y[:n]
        drag = self.drag[:n]
        actf = act.astype(np.float32)
        damp = 1.0 - np.minimum(drag * dt, 0.95) * actf
        vx *= damp
        vy *= damp
        vy += self.grav[:n] * dt * actf
        x += vx * dt * actf
        y += vy * dt * actf
        h = kind == HOMING
        if h.any():
            idx = np.nonzero(h)[0]
            t = np.clip(age[idx] / np.maximum(self.travel[idx], 1e-4), 0, 1)
            e = self.ease[idx]
            ev = np.where(e == FALL, t * t,
                          np.where(e == BACK, 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2,
                                   np.where(e == LINEAR, t, t * t * (3 - 2 * t))))
            x[idx] = self.sx[idx] + (self.tx[idx] - self.sx[idx]) * ev
            y[idx] = self.sy[idx] + (self.ty[idx] - self.sy[idx]) * ev
        alive = age < self.life[:n]
        if not alive.all():
            keep = np.nonzero(alive)[0]
            m = len(keep)
            for f in self.FIELDS_F + self.FIELDS_I:
                arr = getattr(self, f)
                arr[:m] = arr[keep]
            self.col[:m] = self.col[keep]
            self.n = m

    def shift(self, y0, y1, dy):
        """move particles whose target lies in [y0, y1) by dy (partial scroll regions)"""
        n = self.n
        if not n:
            return
        m = (self.ty[:n] >= y0) & (self.ty[:n] < y1)
        if m.any():
            for f in ('y', 'sy', 'ty'):
                getattr(self, f)[:n][m] += dy

    def draw(self, surf, ox, oy):
        n = self.n
        if n == 0:
            return
        W, H = surf.get_size()
        age = self.age[:n]
        xi = (self.x[:n] + ox).astype(np.int32)
        yi = (self.y[:n] + oy).astype(np.int32)
        s = self.size
        vis = (age >= 0) & (xi >= 0) & (yi >= 0) & (xi < W - s + 1) & (yi < H - s + 1)
        idx = np.nonzero(vis)[0]
        if len(idx) == 0:
            return
        xi, yi = xi[idx], yi[idx]
        pal = self.pal[idx]
        c = self.col[idx].copy()
        lr = np.clip(age[idx] / np.maximum(self.life[idx], 1e-4), 0, 1)
        m = pal == FIRE
        if m.any():
            c[m] = FIRE_LUT[(lr[m] * 255).astype(np.int32)]
        m = pal == FADE
        if m.any():
            c[m] *= (1.0 - lr[m])[:, None]
        m = pal == SPARKLE
        if m.any():
            c[m] *= self.rng.uniform(0.15, 1.0, m.sum()).astype(np.float32)[:, None]
        m = pal == FLASH
        if m.any():
            tt = np.clip(age[idx][m] / np.maximum(self.travel[idx][m], 1e-4), 0, 1)[:, None]
            c[m] = 255 + (c[m] - 255) * tt
        m = pal == COOL
        if m.any():
            c[m] = 255 + (c[m] - 255) * lr[m][:, None]
        m = pal == RAINBOW
        if m.any():
            c[m] = RAINBOW_LUT[((xi[m] + yi[m] * 3 + (age[idx][m] * 400)).astype(np.int32)) & 255]
        try:
            arr = pygame.surfarray.pixels3d(surf)
        except Exception:
            return
        add = self.add[idx] == 1
        offs = [(0, 0)] if s == 1 else [(dx, dy) for dx in range(s) for dy in range(s)]
        ci = np.clip(c, 0, 255)
        if add.any():
            ax, ay, ac = xi[add], yi[add], ci[add]
            for dx, dy in offs:
                cur = arr[ax + dx, ay + dy].astype(np.float32)
                arr[ax + dx, ay + dy] = np.minimum(cur + ac, 255).astype(np.uint8)
        sol = ~add
        if sol.any():
            sx, sy, sc = xi[sol], yi[sol], ci[sol].astype(np.uint8)
            for dx, dy in offs:
                arr[sx + dx, sy + dy] = sc
        del arr
