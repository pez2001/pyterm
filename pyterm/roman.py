"""Roman theme pieces: the marble tablet background.

  stone   a weathered marble tablet with veins, cracks and a carved, beveled frame
          (S P Q R in the top band), warm torch light that flickers across it and
          dust motes drifting in the light - more of them while you chisel (type)
"""
from __future__ import annotations

import math
import random

import numpy as np
import pygame

from . import signals
from .backgrounds import Background
from .scenes import glow

ADD = pygame.BLEND_RGB_ADD


def _noise(w, h, seed, octaves=5):
    rng = np.random.default_rng(seed)
    out = np.zeros((w, h), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        cw, ch = max(2, w >> (octaves - o)), max(2, h >> (octaves - o))
        g = rng.random((cw, ch)).astype(np.float32)
        s = pygame.Surface((cw, ch))
        v = (g * 255).astype(np.uint8)
        pygame.surfarray.blit_array(s, np.stack([v, v, v], -1))
        s = pygame.transform.smoothscale(s, (w, h))
        out += pygame.surfarray.array3d(s)[..., 0].astype(np.float32) / 255 * amp
        tot += amp
        amp *= 0.5
    return out / tot


def _carve_text(surf, x, y, text, k, dark, light):
    """tiny carved capitals: shadow up-left, light down-right"""
    from .weather import _F
    for dx, dy, col in ((0, 0, dark), (1, 1, light)):
        x0 = x
        for ch in text:
            g = _F.get(ch, _F[' '])
            for i, v in enumerate(g):
                if v == '#':
                    surf.fill(col, (x0 + (i % 3) * k + dx, y + (i // 3) * k + dy, k, k))
            x0 += 4 * k


class Stone(Background):
    name = 'stone'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.k = max(1, h // 240)
        base = np.array(self.p('color', [214, 204, 184]), np.float32)
        n1 = _noise(w, h, 3)
        n2 = _noise(w, h, 11, 4)
        X, Y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32), indexing='ij')
        # marble veins: thin dark lines where a turbulent sine crosses zero
        vein = np.abs(np.sin((X * 0.012 + Y * 0.02) + n1 * 9.0))
        vein = np.clip(1 - vein * 7, 0, 1) ** 2 * 0.09
        vein2 = np.clip(1 - np.abs(np.sin(X * 0.01 - Y * 0.004 + n2 * 6)) * 18, 0, 1) * 0.05
        tone = 0.86 + 0.16 * n2 - vein - vein2
        grain = np.random.default_rng(5).random((w, h)).astype(np.float32) * 0.06
        img = base[None, None, :] * (tone + grain)[..., None]
        img[..., 2] *= 0.97
        # pits & pores
        rng = np.random.default_rng(9)
        for _ in range(w * h // 900):
            px, py = rng.integers(0, w), rng.integers(0, h)
            img[px, py] *= 0.7
        s = pygame.Surface((w, h))
        pygame.surfarray.blit_array(s, np.clip(img, 0, 255).astype(np.uint8))
        self._frame(s, base)
        self._cracks(s, random.Random(4))
        self.static = s
        self.motes = [[random.uniform(0, w), random.uniform(0, h), random.uniform(0.2, 1.0), random.random() * 6]
                      for _ in range(40)]
        self.extra = []
        self.seq = signals.letter_seq

    def _frame(self, s, base):
        w, h, k = self.w, self.h, self.k
        b = int(self.p('frame', 12)) * k
        dark = tuple(int(v * 0.55) for v in base)
        mid = tuple(int(v * 0.78) for v in base)
        light = tuple(min(255, int(v * 1.12)) for v in base)
        # outer molding: raised bevel (light top-left, shadow bottom-right)
        for i in range(3 * k):
            pygame.draw.rect(s, light if i < 2 * k else mid, (i, i, w - 2 * i, h - 2 * i), 1)
        for i in range(2 * k):
            pygame.draw.line(s, dark, (i, h - 1 - i), (w - 1 - i, h - 1 - i))
            pygame.draw.line(s, dark, (w - 1 - i, i), (w - 1 - i, h - 1 - i))
        # inner groove around the inscription field
        r = pygame.Rect(b - 3 * k, b - 3 * k, w - 2 * (b - 3 * k), h - 2 * (b - 3 * k))
        pygame.draw.rect(s, dark, r, max(1, k))
        pygame.draw.rect(s, light, r.move(k, k), max(1, k))
        # corner rosettes
        for cx, cy in ((b // 2, b // 2), (w - b // 2, b // 2), (b // 2, h - b // 2), (w - b // 2, h - b // 2)):
            for a in range(8):
                ang = a * math.pi / 4
                ex, ey = cx + math.cos(ang) * 3 * k, cy + math.sin(ang) * 3 * k
                pygame.draw.line(s, dark, (cx, cy), (ex, ey), max(1, k))
            s.fill(light, (cx, cy, k, k))
        # S P Q R in the top band
        text = self.p('title', 'S P Q R')
        tk = max(1, (b - 3 * k) // 7)
        tw = len(text) * 4 * tk
        _carve_text(s, w // 2 - tw // 2, max(1, (b - 3 * k - 5 * tk) // 2), text, tk, dark, light)

    def _cracks(self, s, rng):
        w, h, k = self.w, self.h, self.k
        dark = (120, 110, 96)
        for _ in range(3):
            x, y = rng.uniform(0, w), rng.choice((rng.uniform(0, h * 0.2), rng.uniform(h * 0.8, h)))
            a = rng.uniform(0, math.tau)
            pts = [(x, y)]
            for _ in range(rng.randint(6, 14)):
                a += rng.uniform(-0.6, 0.6)
                x += math.cos(a) * rng.uniform(3, 8) * k
                y += math.sin(a) * rng.uniform(3, 8) * k
                pts.append((x, y))
            pygame.draw.lines(s, dark, False, pts, 1)
            pygame.draw.lines(s, (236, 228, 210), False, [(px + 1, py + 1) for px, py in pts], 1)

    def update(self, dt, energy):
        super().update(dt, energy)
        new, self.seq = signals.take_letters(self.seq)
        for _, c, x, y, typed in new[-6:]:
            if typed:
                for _ in range(2):
                    self.extra.append([x + random.uniform(-4, 4), y + random.uniform(-2, 6), random.uniform(0.4, 1.0),
                                       random.random() * 6, 4.0])
        for m in self.motes + self.extra:
            m[0] += (math.sin(self.t * 0.3 + m[3]) * 3 + 2) * dt * m[2]
            m[1] += (math.cos(self.t * 0.23 + m[3] * 2) * 2 + 1.5) * dt * m[2]
            if m[0] > self.w:
                m[0] = 0
            if m[1] > self.h:
                m[1] = 0
        for e in self.extra:
            e[4] -= dt
        self.extra = [e for e in self.extra if e[4] > 0][-80:]

    def draw(self, surf, first):
        w, h, k = self.w, self.h, self.k
        surf.blit(self.static, (0, 0))
        # warm torch light from the left, flickering softly
        fl = 0.85 + 0.1 * math.sin(self.t * 7.3) * math.sin(self.t * 3.1) + 0.05 * math.sin(self.t * 17)
        glow(surf, int(w * 0.18), int(h * 0.35), int(max(w, h) * 0.55), (int(34 * fl), int(22 * fl), int(6 * fl)))
        for x, y, sz, ph, *life in self.motes + self.extra:
            v = int(60 + 50 * math.sin(self.t * 1.3 + ph))
            surf.fill((v, int(v * 0.9), int(v * 0.7)), (int(x), int(y), k, k), special_flags=ADD)
