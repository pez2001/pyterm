"""Seasonal & holiday scenes, part 2:

  easter    spring meadow: a bunny hops about and sniffs, chicks peck, painted eggs hide
            in the grass (every letter you type drops a new one), blossom tree, butterflies
  autumn    golden afternoon: maple trees in red/orange/yellow shed leaves that flutter
            down and pile up on the ground, gusts of wind with your output, a squirrel
  sakura    cherry blossom morning: Mt. Fuji, a pagoda, pink trees, petals drifting in
            the breeze onto a pond with koi; Enter sends a gust
  seasonal  picks the scene by date: New Year fireworks, Christmas, Halloween, Easter,
            otherwise the season (sakura, beach, autumn, winter)
"""
from __future__ import annotations

import datetime
import math
import random

import numpy as np
import pygame

from . import signals
from .backgrounds import Background
from .scenes import glow, gradient
from .seasons import Dots
from .weather import _lerp

ADD = pygame.BLEND_RGB_ADD


def easter_date(year):
    """Gregorian Easter Sunday (Anonymous / Meeus algorithm)"""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    hh = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ll = (32 + 2 * e + 2 * i - hh - k) % 7
    m = (a + 11 * hh + 22 * ll) // 451
    month = (hh + ll - 7 * m + 114) // 31
    day = (hh + ll - 7 * m + 114) % 31 + 1
    return datetime.date(year, month, day)


def _blob_canopy(surf, cx, cy, rx, ry, cols, rng, n=260, size=2):
    """leafy / blossom canopy out of many small dots"""
    pts = []
    for _ in range(n):
        a = rng.uniform(0, math.tau)
        r = math.sqrt(rng.random())
        x = cx + math.cos(a) * rx * r
        y = cy + math.sin(a) * ry * r
        shade = (y - (cy - ry)) / (2 * ry)                 # darker underneath
        c = _lerp(rng.choice(cols), (0, 0, 0), max(0.0, shade - 0.45) * 0.6)
        surf.fill(c, (int(x), int(y), size, size))
        pts.append((x, y))
    return pts


def _trunk(surf, x, y, h, w, col, rng, branches=4):
    pygame.draw.polygon(surf, col, [(x - w, y), (x + w, y), (x + w * 0.5, y - h), (x - w * 0.5, y - h)])
    for i in range(branches):
        q = 0.45 + i * 0.12
        by = y - h * q
        d = -1 if i % 2 else 1
        pygame.draw.line(surf, col, (x, by), (x + d * h * rng.uniform(0.25, 0.4), by - h * rng.uniform(0.2, 0.35)), max(1, int(w * 0.6)))


# ============================================================================ easter
EGG_COLS = [(255, 120, 150), (120, 200, 255), (255, 220, 90), (160, 230, 120), (200, 150, 255), (255, 160, 80)]


class Easter(Background):
    name = 'easter'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.k = k = h / 240
        self.gy = int(h * 0.7)
        rng = random.Random(4)
        st = self.static = pygame.Surface((w, h))
        st.blit(gradient(w, h, (110, 180, 245), (210, 236, 255), self.cache, 'sky'), (0, 0))
        glow(st, int(w * 0.15), int(h * 0.15), int(30 * k), (60, 56, 30))
        pygame.draw.circle(st, (255, 244, 180), (int(w * 0.15), int(h * 0.15)), int(10 * k))
        for i, (yb, col) in enumerate(((0.58, (150, 210, 120)), (0.64, (120, 196, 96)))):
            pts = [(0, h)] + [(x, int(h * yb - math.sin(x / w * (3 + i * 2) + i) * h * 0.05)) for x in range(0, w + 4, 4)] + [(w, h)]
            pygame.draw.polygon(st, col, pts)
        st.fill((96, 180, 80), (0, self.gy, w, h - self.gy))
        for _ in range(w):                                  # grass texture + flowers
            x, y = rng.uniform(0, w), rng.uniform(self.gy, h)
            st.fill(rng.choice([(80, 160, 64), (110, 196, 86), (70, 150, 60)]), (int(x), int(y), 1, int(rng.uniform(1, 3) * k)))
        for _ in range(50):
            x, y = rng.uniform(0, w), rng.uniform(self.gy + 2, h)
            c = rng.choice([(255, 255, 255), (255, 230, 80), (255, 140, 200), (180, 140, 255)])
            st.fill(c, (int(x), int(y), max(1, int(k * 1.5)), max(1, int(k * 1.5))))
        tx = int(w * 0.8)
        _trunk(st, tx, self.gy + 6, h * 0.3, 5 * k, (110, 76, 50), rng)
        _blob_canopy(st, tx, self.gy - h * 0.32, w * 0.13, h * 0.14, [(255, 200, 220), (255, 170, 200), (255, 230, 240), (240, 140, 180)], rng, n=900)
        self.eggs = []
        for _ in range(7):
            self._egg(rng.uniform(w * 0.05, w * 0.95), rng.uniform(self.gy + 6, h - 6), rng)
        self.bunny = {'x': w * 0.3, 'dir': 1, 'state': 'sit', 't': 2.0, 'hop': 0.0}
        self.chicks = [{'x': rng.uniform(w * 0.4, w * 0.7), 'ph': rng.random() * 6, 'dir': rng.choice((-1, 1))} for _ in range(3)]
        self.butterflies = [[rng.uniform(0, w), rng.uniform(h * 0.3, self.gy), rng.random() * 6, rng.choice(EGG_COLS)] for _ in range(3)]
        self.falling = []
        self.clouds = [[rng.uniform(0, w), rng.uniform(4, h * 0.25), rng.uniform(0.7, 1.3)] for _ in range(4)]
        self.seq = signals.letter_seq
        self.last_enter = signals.enter

    def _egg(self, x, y, rng=random):
        self.eggs.append({'x': x, 'y': y, 'c1': rng.choice(EGG_COLS), 'c2': rng.choice(EGG_COLS), 'pat': rng.randrange(3)})
        self.eggs = self.eggs[-40:]

    def update(self, dt, energy):
        super().update(dt, energy)
        w, h = self.w, self.h
        new, self.seq = signals.take_letters(self.seq)
        for l in new:
            if l[4] and random.random() < 0.5:
                self.falling.append([l[2], l[3], 0.0, random.uniform(self.gy + 6, h - 6)])
        for f in self.falling:
            f[2] += 220 * dt
            f[1] += f[2] * dt
            if f[1] >= f[3]:
                self._egg(f[0], f[3])
                f[1] = -1
        self.falling = [f for f in self.falling if f[1] >= 0]
        b = self.bunny
        b['t'] -= dt
        if signals.enter != self.last_enter:
            self.last_enter = signals.enter
            b['state'], b['t'] = 'hop', random.uniform(1.5, 3)
        if b['t'] <= 0:
            b['state'] = random.choice(['hop', 'hop', 'sit', 'sniff'])
            b['t'] = random.uniform(1.5, 4)
            if b['state'] == 'hop' and random.random() < 0.4:
                b['dir'] = -b['dir']
        if b['state'] == 'hop':
            b['hop'] = (b['hop'] + dt * 2.6) % 1
            b['x'] += b['dir'] * 26 * self.k * dt
            if b['x'] < 10 or b['x'] > w - 10:
                b['dir'] = -b['dir']
        else:
            b['hop'] = 0.0
        for c in self.chicks:
            if random.random() < dt * 0.4:
                c['dir'] = -c['dir']
            c['x'] = max(5, min(w - 5, c['x'] + c['dir'] * 5 * dt))
        for bf in self.butterflies:
            bf[0] = (bf[0] + 10 * dt) % (w + 10)
            bf[1] = h * 0.5 + math.sin(self.t * 0.7 + bf[2]) * h * 0.15
        for c in self.clouds:
            c[0] = (c[0] + 3 * c[2] * dt) % (w + 60)

    def draw(self, surf, first):
        w, h, k = self.w, self.h, self.k
        surf.blit(self.static, (0, 0))
        for x, y, s in self.clouds:
            for i in range(4):
                pygame.draw.circle(surf, (255, 255, 255), (int(x - 30 + i * 7 * s), int(y + (i % 2) * 2)), int(5 * s + (i % 2) * 2))
        for e in sorted(self.eggs, key=lambda e: e['y']):
            self._draw_egg(surf, e['x'], e['y'], e)
        for x, y, v, ty in self.falling:
            pygame.draw.ellipse(surf, (255, 230, 120), (x - 2 * k, y - 3 * k, 4 * k, 6 * k))
        for c in self.chicks:
            x, y = int(c['x']), int(self.gy + 14 * k)
            peck = int(self.t * 3 + c['ph']) % 4 == 0
            pygame.draw.circle(surf, (255, 226, 60), (x, y), int(3 * k))
            pygame.draw.circle(surf, (255, 236, 90), (x + int(2 * k * c['dir']), y - int((3 if not peck else 1) * k)), int(2 * k))
            surf.fill((250, 140, 30), (x + int(4 * k * c['dir']), y - int((3 if not peck else 1) * k), max(1, int(k)), max(1, int(k))))
            surf.fill((20, 20, 20), (x + int(2.5 * k * c['dir']), y - int((4 if not peck else 2) * k), 1, 1))
        self._draw_bunny(surf)
        for x, y, ph, c in self.butterflies:
            flap = max(1, int(3 * k * abs(math.sin(self.t * 10 + ph))))
            surf.fill(c, (int(x) - flap, int(y) - 1, flap, int(3 * k)))
            surf.fill(c, (int(x) + 1, int(y) - 1, flap, int(3 * k)))
            surf.fill((40, 30, 30), (int(x), int(y) - 1, 1, int(3 * k)))

    def _draw_egg(self, surf, x, y, e):
        k = self.k
        ew, eh = 6 * k, 8 * k
        r = pygame.Rect(int(x - ew / 2), int(y - eh), int(ew), int(eh))
        pygame.draw.ellipse(surf, _lerp(e['c1'], (0, 0, 0), 0.25), r.inflate(2, 2))
        pygame.draw.ellipse(surf, e['c1'], r)
        if e['pat'] == 0:
            surf.fill(e['c2'], (r.x + 1, r.centery - 1, r.w - 2, max(1, int(k * 1.5))))
        elif e['pat'] == 1:
            for dx, dy in ((-1, -2), (1, 0), (-1, 2)):
                surf.fill(e['c2'], (int(x + dx * k), int(y - eh / 2 + dy * k), max(1, int(k)), max(1, int(k))))
        else:
            for i in range(3):
                surf.fill(e['c2'], (r.x + 1 + i * int(2 * k), r.centery + (i % 2), max(1, int(k)), max(1, int(k))))
        surf.fill((255, 255, 255), (r.x + int(1.5 * k), r.y + int(2 * k), 1, max(1, int(k))))

    def _draw_bunny(self, surf):
        b = self.bunny
        k = self.k
        d = b['dir']
        hop = math.sin(b['hop'] * math.pi) * 8 * k
        x, y = b['x'], self.gy + 18 * k - hop
        fur, inner = (240, 236, 230), (255, 180, 190)
        pygame.draw.ellipse(surf, (90, 140, 70), (x - 7 * k, self.gy + 18 * k, 14 * k, 3 * k))      # shadow
        pygame.draw.ellipse(surf, fur, (x - 6 * k, y - 8 * k, 12 * k, 9 * k))                         # body
        pygame.draw.circle(surf, (255, 255, 255), (int(x - 6 * k * d), int(y - 5 * k)), int(2.2 * k))  # tail
        hx, hy = x + 5 * k * d, y - 10 * k
        pygame.draw.circle(surf, fur, (int(hx), int(hy)), int(4 * k))                                 # head
        twitch = 1 if (b['state'] == 'sniff' and int(self.t * 8) % 2) else 0
        for ex in (-1.5, 1.5):
            ear = pygame.Rect(int(hx + ex * k - k), int(hy - (10 + twitch) * k), int(2.4 * k), int(8 * k))
            pygame.draw.ellipse(surf, fur, ear)
            pygame.draw.ellipse(surf, inner, ear.inflate(-int(k), -int(2 * k)))
        surf.fill((30, 20, 30), (int(hx + 1.5 * k * d), int(hy - k), max(1, int(k)), max(1, int(k))))
        surf.fill((255, 130, 150), (int(hx + 3.5 * k * d), int(hy + 0.5 * k), max(1, int(k)), max(1, int(k))))


# ============================================================================ autumn
LEAF_COLS = [(220, 70, 30), (240, 130, 30), (250, 190, 50), (180, 50, 30), (200, 150, 60), (150, 90, 40)]


class Autumn(Background):
    name = 'autumn'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.k = k = h / 240
        self.gy = int(h * 0.8)
        rng = random.Random(10)
        st = self.static = pygame.Surface((w, h))
        st.blit(gradient(w, h, (120, 150, 200), (250, 200, 150), self.cache, 'sky'), (0, 0))
        glow(st, int(w * 0.8), int(h * 0.3), int(40 * k), (70, 50, 20))
        pygame.draw.circle(st, (255, 226, 160), (int(w * 0.8), int(h * 0.3)), int(12 * k))
        for i, (yb, col) in enumerate(((0.62, (190, 140, 110)), (0.7, (150, 110, 70)))):
            pts = [(0, h)] + [(x, int(h * yb - math.sin(x / w * (3 + i * 2) + i * 2) * h * 0.06)) for x in range(0, w + 4, 4)] + [(w, h)]
            pygame.draw.polygon(st, col, pts)
            for _ in range(90):                        # a band of distant autumn forest
                x = rng.uniform(0, w)
                y = h * yb - math.sin(x / w * (3 + i * 2) + i * 2) * h * 0.06 + rng.uniform(0, 3) * k
                c = _lerp(rng.choice(LEAF_COLS), col, 0.6 - i * 0.2)
                r = rng.uniform(1.5, 3.2) * k * (1 + i * 0.4)
                pygame.draw.circle(st, c, (int(x), int(y)), max(1, int(r)))
                st.fill(_lerp(c, col, 0.5), (int(x), int(y + r), 1, max(1, int(r))))
        st.fill((120, 90, 50), (0, self.gy, w, h - self.gy))
        for _ in range(w):
            st.fill(rng.choice([(110, 120, 50), (130, 110, 50), (100, 80, 40)]),
                    (int(rng.uniform(0, w)), int(rng.uniform(self.gy, h)), 1, max(1, int(rng.uniform(1, 3) * k))))
        self.canopies = []
        for fx, sc in ((0.12, 1.0), (0.45, 0.8), (0.78, 1.15)):
            tx = int(w * fx)
            th = h * 0.36 * sc
            _trunk(st, tx, self.gy + 4, th, 5 * k * sc, (80, 50, 32), rng)
            cy = self.gy - th * 0.95
            _blob_canopy(st, tx, cy, w * 0.11 * sc, h * 0.13 * sc, LEAF_COLS, rng, n=int(1700 * sc))
            _blob_canopy(st, tx, cy - h * 0.02 * sc, w * 0.08 * sc, h * 0.09 * sc, LEAF_COLS[:3], rng, n=int(500 * sc), size=3)
            self.canopies.append((tx, cy, w * 0.11 * sc, h * 0.13 * sc))
        for _ in range(8):                             # mushrooms
            mx, my = rng.uniform(0, w), self.gy + rng.uniform(4, 14) * k
            st.fill((240, 230, 210), (int(mx), int(my - 3 * k), max(1, int(2 * k)), int(3 * k)))
            pygame.draw.ellipse(st, (200, 50, 40), (mx - 2.5 * k, my - 6 * k, 7 * k, 4 * k))
            st.fill((255, 255, 255), (int(mx), int(my - 5 * k), 1, 1))
        self.pile = pygame.Surface((w, h - self.gy), pygame.SRCALPHA)
        self.pile.fill((0, 0, 0, 0))
        self.leaves = []                      # [x, y, vx, vy, col, phase, size]
        for _ in range(60):
            self._leaf(anywhere=True)
        self.wind = 0.0
        self.gust = 0.0
        self.squirrel = {'x': -20.0, 't': 6.0}
        self.seq = signals.letter_seq
        self.last_enter = signals.enter

    def _leaf(self, x=None, y=None, anywhere=False):
        if x is None:
            tx, cy, rx, ry = random.choice(self.canopies)
            x = tx + random.uniform(-rx, rx)
            y = cy + random.uniform(-ry * 0.5, ry) if not anywhere else random.uniform(0, self.gy)
        self.leaves.append([x, y, 0.0, random.uniform(8, 16), random.choice(LEAF_COLS), random.random() * 6,
                            random.choice((1, 2))])
        self.leaves = self.leaves[-260:]

    def update(self, dt, energy):
        super().update(dt, energy)
        w, h, k = self.w, self.h, self.k
        if random.random() < dt * (3 + energy * 12):
            self._leaf()
        new, self.seq = signals.take_letters(self.seq)
        for l in new:
            if l[4]:
                self._leaf(l[2] + random.uniform(-3, 3), l[3])
        if signals.enter != self.last_enter:
            self.last_enter = signals.enter
            self.gust = 1.0
        self.gust = max(0.0, self.gust - dt * 0.5)
        self.wind = 8 * math.sin(self.t * 0.23) + 6 * math.sin(self.t * 0.71) + energy * 25 + self.gust * 60
        arr = None
        for lf in self.leaves:
            lf[5] += dt * 3
            lf[0] += (self.wind + math.sin(lf[5]) * 18) * dt
            lf[1] += (lf[3] + math.cos(lf[5] * 1.3) * 6) * dt
            ground = self.gy + (hash(int(lf[0])) % max(1, h - self.gy - 2))
            if lf[1] >= ground and lf[0] >= 0 and lf[0] < w:
                if arr is None:
                    arr = True
                self.pile.fill(lf[4] + (255,), (int(lf[0]), int(lf[1] - self.gy), lf[6], 1))
                lf[1] = -999
        self.leaves = [lf for lf in self.leaves if lf[1] > -900 and -30 < lf[0] < w + 30]
        sq = self.squirrel
        sq['t'] -= dt
        if sq['t'] <= 0:
            sq['x'] += 40 * k * dt
            if sq['x'] > w + 20:
                sq['x'], sq['t'] = -20.0, random.uniform(20, 40)

    def draw(self, surf, first):
        w, h, k = self.w, self.h, self.k
        surf.blit(self.static, (0, 0))
        surf.blit(self.pile, (0, self.gy))
        for x, y, vx, vy, col, ph, size in self.leaves:
            flip = math.sin(ph * 2)
            if abs(flip) > 0.5:
                surf.fill(col, (int(x), int(y), size + 1, max(1, size)))
            else:
                surf.fill(_lerp(col, (0, 0, 0), 0.25), (int(x), int(y), 1, size + 1))
        sq = self.squirrel
        if sq['t'] <= 0:
            x, y = int(sq['x']), int(self.gy + 8 * k - abs(math.sin(self.t * 10)) * 3 * k)
            c = (150, 80, 40)
            pygame.draw.ellipse(surf, c, (x, y, 8 * k, 5 * k))
            pygame.draw.circle(surf, c, (int(x + 8 * k), int(y + k)), int(2.5 * k))
            pygame.draw.ellipse(surf, (180, 100, 50), (x - 6 * k, y - 7 * k, 7 * k, 9 * k))
            surf.fill((20, 10, 10), (int(x + 9 * k), int(y), 1, 1))


# ============================================================================ sakura
class Sakura(Background):
    name = 'sakura'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.k = k = h / 240
        self.pond = int(h * 0.8)
        rng = random.Random(3)
        st = self.static = pygame.Surface((w, h))
        st.blit(gradient(w, h, (150, 170, 220), (255, 214, 214), self.cache, 'sky'), (0, 0))
        glow(st, int(w * 0.3), int(h * 0.3), int(46 * k), (60, 40, 30))
        pygame.draw.circle(st, (255, 236, 210), (int(w * 0.3), int(h * 0.3)), int(14 * k))
        fx, fy = int(w * 0.62), int(h * 0.62)                  # mount fuji
        fw, fh = w * 0.35, h * 0.36
        pygame.draw.polygon(st, (150, 150, 200), [(fx - fw, fy), (fx - fw * 0.12, fy - fh), (fx + fw * 0.12, fy - fh), (fx + fw, fy)])
        pygame.draw.polygon(st, (250, 250, 255), [(fx - fw * 0.34, fy - fh * 0.62), (fx - fw * 0.12, fy - fh), (fx + fw * 0.12, fy - fh),
                                                  (fx + fw * 0.34, fy - fh * 0.62), (fx + fw * 0.2, fy - fh * 0.68),
                                                  (fx + fw * 0.06, fy - fh * 0.6), (fx - fw * 0.08, fy - fh * 0.7), (fx - fw * 0.22, fy - fh * 0.6)])
        st.fill((120, 150, 110), (0, int(h * 0.62), w, self.pond - int(h * 0.62)))
        for _ in range(40):
            x = rng.uniform(0, w)
            pygame.draw.circle(st, (90, 130, 90), (int(x), int(h * 0.62)), int(rng.uniform(3, 7) * k))
        px, py = int(w * 0.13), int(h * 0.62)                 # pagoda
        pc = (110, 40, 40)
        for i in range(4):
            ww = (16 - i * 3) * k
            yy = py - i * 9 * k
            st.fill(pc, (int(px - ww * 0.4), int(yy - 7 * k), int(ww * 0.8), int(7 * k)))
            pygame.draw.polygon(st, (40, 30, 40), [(px - ww, yy - 6 * k), (px + ww, yy - 6 * k), (px + ww * 0.6, yy - 9 * k), (px - ww * 0.6, yy - 9 * k)])
        st.fill((40, 30, 40), (px, int(py - 46 * k), max(1, int(k)), int(10 * k)))
        self.trees = []
        for tx, sc in ((0.3, 1.0), (0.88, 1.2)):
            x = int(w * tx)
            _trunk(st, x, self.pond + 2, h * 0.32 * sc, 5 * k * sc, (70, 40, 40), rng)
            cy = self.pond - h * 0.34 * sc
            _blob_canopy(st, x, cy, w * 0.12 * sc, h * 0.12 * sc, [(255, 190, 210), (255, 214, 230), (250, 160, 190), (255, 240, 246)], rng, n=int(1200 * sc))
            self.trees.append((x, cy, w * 0.12 * sc, h * 0.12 * sc))
        lx = int(w * 0.6)                                       # stone lantern
        st.fill((150, 150, 150), (lx - int(2 * k), self.pond - int(10 * k), int(4 * k), int(10 * k)))
        st.fill((130, 130, 130), (lx - int(5 * k), self.pond - int(16 * k), int(10 * k), int(6 * k)))
        st.fill((255, 220, 140), (lx - int(2 * k), self.pond - int(15 * k), int(4 * k), int(3 * k)))
        pygame.draw.polygon(st, (120, 120, 120), [(lx - 7 * k, self.pond - 16 * k), (lx + 7 * k, self.pond - 16 * k), (lx, self.pond - 21 * k)])
        self.petals = Dots(1500)
        self.floating = []
        self.koi = [{'x': rng.uniform(0, w), 'y': rng.uniform(self.pond + 6, h - 4), 'v': rng.choice((-1, 1)) * rng.uniform(5, 10),
                     'c': rng.choice([(255, 120, 40), (255, 255, 255), (255, 200, 60)]), 'ph': rng.random() * 6} for _ in range(3)]
        self.gust = 0.0
        self.seq = signals.letter_seq
        self.last_enter = signals.enter

    def _petals(self, n, x=None, y=None):
        if n <= 0:
            return
        if x is None:
            tx, cy, rx, ry = random.choice(self.trees)
            x = tx + np.random.uniform(-rx, rx, n)
            y = cy + np.random.uniform(-ry * 0.5, ry, n)
        col = np.array(random.choice([(255, 200, 220), (255, 225, 235), (250, 170, 200)]), np.float32)
        self.petals.add(x, y, np.random.uniform(2, 8, n), np.random.uniform(6, 12, n), np.random.uniform(12, 20, n), col,
                        flick=0.15, size=np.random.choice([1, 2], n).astype(np.int8))

    def update(self, dt, energy):
        super().update(dt, energy)
        w, h = self.w, self.h
        if random.random() < dt * (8 + energy * 20):
            self._petals(1)
        new, self.seq = signals.take_letters(self.seq)
        for l in new:
            if l[4]:
                self._petals(3, np.full(3, l[2], np.float32) + np.random.uniform(-3, 3, 3), l[3])
        if signals.enter != self.last_enter:
            self.last_enter = signals.enter
            self.gust = 1.0
            self._petals(30)
        self.gust = max(0.0, self.gust - dt * 0.6)
        P = self.petals
        n = P.n
        if n:
            P.vx[:n] = 6 + self.gust * 40 + np.sin(self.t * 1.3 + P.y[:n] * 0.08) * 8
            P.vy[:n] = 9 + np.cos(self.t * 1.7 + P.x[:n] * 0.05) * 5
            landed = P.y[:n] > self.pond + 2
            if landed.any():
                for i in np.nonzero(landed)[0][:10]:
                    self.floating.append([float(P.x[i]), float(P.y[i]), P.col[i].copy(), 0.0])
                P.life[:n][landed] = 0
        P.step(dt)
        for f in self.floating:
            f[0] += (3 + self.gust * 10) * dt
            f[3] += dt
        self.floating = [f for f in self.floating if f[3] < 25 and f[0] < w][-200:]
        for c in self.koi:
            c['x'] += c['v'] * dt
            c['y'] += math.sin(self.t * 0.8 + c['ph']) * 2 * dt
            if c['x'] < -10 or c['x'] > w + 10:
                c['v'] = -c['v']

    def draw(self, surf, first):
        w, h, k, pd = self.w, self.h, self.k, self.pond
        surf.blit(self.static, (0, 0))
        depth = h - pd
        surf.fill((90, 120, 150), (0, pd, w, depth))
        src = surf.subsurface((0, max(0, pd - depth), w, min(depth, pd))).copy()
        src = pygame.transform.flip(src, False, True)
        src.fill((150, 170, 190), special_flags=pygame.BLEND_RGB_MULT)
        for yy in range(src.get_height()):
            surf.blit(src, (int(math.sin(self.t * 1.5 + yy * 0.6) * (0.5 + yy * 0.06)), pd + yy), (0, yy, w, 1))
        for c in self.koi:
            x, y = int(c['x']), int(c['y'])
            d = 1 if c['v'] > 0 else -1
            col = tuple(int(v * 0.7) for v in c['c'])
            pygame.draw.ellipse(surf, col, (x - 4 * k, y - 1.5 * k, 8 * k, 3 * k))
            tail = int(math.sin(self.t * 6 + c['ph']) * k)
            surf.fill(col, (int(x - 5 * k * d), y - 1 + tail, max(1, int(2 * k)), max(1, int(2 * k))))
        surf.fill((200, 220, 240), (0, pd, w, 1))
        for x, y, col, age in self.floating:
            surf.fill(tuple(int(v) for v in col), (int(x), int(y), 2, 1))
        self.petals.draw(surf, fade_pow=0.15)


# ============================================================================ seasonal (auto by date)
def pick_scene(today=None):
    d = today or datetime.date.today()
    if (d.month == 12 and d.day == 31) or (d.month == 1 and d.day == 1):
        return 'fireworks'
    if d.month == 12 and 1 <= d.day <= 26:
        return 'christmas'
    if (d.month == 10 and d.day >= 20) or (d.month == 11 and d.day == 1):
        return 'halloween'
    e = easter_date(d.year)
    if abs((d - e).days) <= 7:
        return 'easter'
    return {12: 'winter', 1: 'winter', 2: 'winter', 3: 'sakura', 4: 'sakura', 5: 'sakura',
            6: 'beach', 7: 'beach', 8: 'beach'}.get(d.month, 'autumn')


class Seasonal(Background):
    """bg_params: seasonal: {force: halloween}  to pin one"""
    name = 'seasonal'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.child = None
        self.child_name = None
        self.check = 0.0
        self._choose()

    def _choose(self):
        from .backgrounds import BACKGROUNDS
        name = self.p('force', None) or pick_scene()
        if name != self.child_name or self.child is None or (self.child.w, self.child.h) != (self.w, self.h):
            cls = BACKGROUNDS.get(name)
            if cls:
                self.child = cls(self.w, self.h, self.params, self.theme)
                self.child_name = name

    @property
    def wants_text(self):
        return getattr(self.child, 'wants_text', False)

    def update(self, dt, energy):
        super().update(dt, energy)
        self.check -= dt
        if self.check <= 0:
            self.check = 60.0
            self._choose()
        if self.child:
            if hasattr(self, 'text_layers'):
                self.child.text_layers = self.text_layers
            self.child.update(dt, energy)

    def draw(self, surf, first):
        if self.child:
            self.child.draw(surf, first)


SEASONS2 = {c.name: c for c in (Easter, Autumn, Sakura, Seasonal)}
