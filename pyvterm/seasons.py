"""Seasonal & holiday scenes, part 1:

  fireworks  New Year's Eve over a city skyline: rockets with glowing trails burst into
             thousands of tiny colorful pixels (peony, chrysanthemum, willow, ring,
             crossette, glitter, hearts, the new year in numbers), smoke, flashes lighting
             up the sky, everything mirrored in the river; countdown on Dec 31
  christmas  snowy village at night: decorated tree with blinking lights and a glowing
             star, houses with warm windows and smoking chimneys, a snowman, falling snow,
             Santa's sleigh crossing the moon
  halloween  haunted hill: full moon, flickering haunted house, bats, a ghost, fog,
             grinning jack-o'-lanterns, a spider on its thread; lightning on failure
  winter     arctic night: northern lights dancing over snowy mountains and a frozen lake,
             pine forest, a cabin with a warm window, gentle snow

Everything reacts to the terminal via pyvterm.signals.
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
from .weather import _F, _lerp, tiny_text

ADD = pygame.BLEND_RGB_ADD
MULT = pygame.BLEND_RGB_MULT


# ============================================================================ pixel particles
class Dots:
    """a small numpy particle system that draws single pixels straight into a surface"""

    def __init__(self, cap=8000):
        self.cap = cap
        self.n = 0
        z = lambda: np.zeros(cap, np.float32)
        self.x, self.y, self.vx, self.vy = z(), z(), z(), z()
        self.life, self.max, self.drag, self.grav, self.flick = z(), z(), z(), z(), z()
        self.col = np.zeros((cap, 3), np.float32)
        self.tag = np.zeros(cap, np.int16)          # user tag (e.g. crossette carriers)
        self.size = np.zeros(cap, np.int8)
        self.hot = 0.0                               # seconds a new particle glows white-hot

    def add(self, x, y, vx, vy, life, col, drag=0.0, grav=0.0, flick=0.0, tag=0, size=1):
        N = max(np.size(v) for v in (x, y, vx, vy, life, drag, grav, flick))
        if N == 0:
            return
        k = min(N, self.cap - self.n)
        if k <= 0:
            return
        s = slice(self.n, self.n + k)
        b = lambda v, dt=np.float32: np.broadcast_to(np.asarray(v, dt).reshape(-1) if np.size(v) > 1 else np.asarray(v, dt), (N,))[:k]
        self.x[s] = b(x)
        self.y[s] = b(y)
        self.vx[s] = b(vx)
        self.vy[s] = b(vy)
        self.life[s] = b(life)
        self.max[s] = b(life)
        self.drag[s] = b(drag)
        self.grav[s] = b(grav)
        self.flick[s] = b(flick)
        self.tag[s] = b(tag, np.int16)
        self.size[s] = b(size, np.int8)
        c = np.asarray(col, np.float32)
        self.col[s] = np.broadcast_to(c, (N, 3))[:k] if c.ndim == 1 else c[:k]
        self.n += k

    def step(self, dt):
        n = self.n
        if not n:
            return
        sl = slice(0, n)
        f = np.maximum(0.0, 1 - self.drag[sl] * dt)
        self.vx[sl] *= f
        self.vy[sl] = self.vy[sl] * f + self.grav[sl] * dt
        self.x[sl] += self.vx[sl] * dt
        self.y[sl] += self.vy[sl] * dt
        self.life[sl] -= dt
        alive = self.life[sl] > 0
        if not alive.all():
            idx = np.nonzero(alive)[0]
            m = len(idx)
            for a in (self.x, self.y, self.vx, self.vy, self.life, self.max, self.drag, self.grav, self.flick,
                      self.tag, self.size):
                a[:m] = a[idx]
            self.col[:m] = self.col[idx]
            self.n = m

    def kill(self, mask):
        self.life[:self.n][mask] = 0

    def draw(self, surf, fade_pow=0.7, ox=0, oy=0):
        n = self.n
        if not n:
            return
        w, h = surf.get_size()
        k = np.clip(self.life[:n] / np.maximum(self.max[:n], 1e-3), 0, 1) ** fade_pow
        fl = self.flick[:n]
        if fl.any():
            k = k * (1 - fl * np.random.random(n).astype(np.float32) ** 2)
        c = self.col[:n]
        if self.hot:
            age = self.max[:n] - self.life[:n]
            hot = np.clip(1 - age / self.hot, 0, 1)[:, None]
            c = c + (255 - c) * hot * 0.85
        c = np.minimum(255, c * k[:, None])
        xi = (self.x[:n] + ox).astype(np.int32)
        yi = (self.y[:n] + oy).astype(np.int32)
        ok = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
        arr = pygame.surfarray.pixels3d(surf)
        xs, ys, cs = xi[ok], yi[ok], c[ok]
        arr[xs, ys] = np.maximum(arr[xs, ys], cs.astype(np.uint8))
        big = self.size[:n][ok] > 1
        if big.any():
            for dx, dy in ((1, 0), (0, 1), (1, 1)):
                x2 = np.minimum(xs[big] + dx, w - 1)
                y2 = np.minimum(ys[big] + dy, h - 1)
                arr[x2, y2] = np.maximum(arr[x2, y2], cs[big].astype(np.uint8))
        del arr


def _text_points(text):
    pts = []
    x0 = 0
    for ch in text:
        g = _F.get(ch, _F[' '])
        for i, v in enumerate(g):
            if v == '#':
                pts.append((x0 + i % 3, i // 3))
        x0 += 4
    a = np.array(pts, np.float32) if pts else np.zeros((1, 2), np.float32)
    a[:, 0] -= (x0 - 1) / 2
    a[:, 1] -= 2
    return a


PALETTES = [[(255, 60, 60), (255, 200, 80)], [(80, 160, 255), (220, 240, 255)], [(80, 255, 120), (240, 255, 150)],
            [(255, 80, 220), (160, 100, 255)], [(255, 210, 60)], [(255, 255, 255), (150, 220, 255)],
            [(255, 140, 30), (255, 60, 40)], [(60, 255, 230), (255, 255, 255)], [(255, 90, 160), (255, 240, 200)],
            [(180, 80, 255), (80, 255, 200)]]


def _skyline(w, h, top_y, rng, lit=0.45):
    """city silhouette with lit windows, a TV tower and a church spire -> SRCALPHA surface"""
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    base = (10, 10, 22, 255)
    x = 0
    while x < w:
        bw = rng.randint(max(6, w // 50), max(10, w // 18))
        bh = int((h - top_y) * rng.uniform(0.25, 0.85))
        s.fill(base, (x, h - bh, bw, bh))
        if rng.random() < 0.3:
            s.fill(base, (x + bw // 3, h - bh - 4, max(2, bw // 4), 4))
        for wy in range(h - bh + 3, h - 2, 4):
            for wx in range(x + 2, x + bw - 2, 3):
                if rng.random() < lit:
                    c = rng.choice([(255, 210, 120), (255, 190, 90), (200, 220, 255), (255, 230, 170)])
                    s.fill(c + (255,), (wx, wy, 1, 2))
        x += bw + rng.randint(0, 2)
    tx = int(w * rng.uniform(0.55, 0.7))           # TV tower
    th = int((h - top_y) * 1.05)
    s.fill(base, (tx, h - th, 2, th))
    pygame.draw.circle(s, base, (tx + 1, h - int(th * 0.72)), max(3, w // 110))
    s.fill((255, 40, 40, 255), (tx, h - th - 2, 2, 2))
    cx = int(w * rng.uniform(0.2, 0.3))           # church spire
    ch = int((h - top_y) * 0.95)
    s.fill(base, (cx - 4, h - int(ch * 0.6), 9, int(ch * 0.6)))
    pygame.draw.polygon(s, base, [(cx - 4, h - int(ch * 0.6)), (cx + 4, h - int(ch * 0.6)), (cx, h - ch)])
    return s


# ============================================================================ fireworks
class Fireworks(Background):
    name = 'fireworks'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.river = int(h * 0.80)
        rng = random.Random(2026)
        self.city = _skyline(w, self.river, int(self.river * 0.55), rng)
        self.stars = [(rng.uniform(0, w), rng.uniform(0, self.river * 0.6), rng.random()) for _ in range(110)]
        self.fx = pygame.Surface((w, self.river))
        self.fx.fill((0, 0, 0))
        self.dots = Dots(12000)
        self.dots.hot = 0.22
        self.rockets = []
        self.smoke = []
        self.flash = 0.0
        self.flash_col = (255, 255, 255)
        self.next = 0.5
        self.seq = signals.letter_seq
        self.last_enter = signals.enter
        self.last_cmd = signals.cmd
        self.finale = 0.0
        self.typed_n = 0

    # ---------------------------------------------------------------- rockets
    def launch(self, kind=None, x=None, small=False):
        w, h = self.w, self.river
        x = x if x is not None else random.uniform(w * 0.1, w * 0.9)
        apex = random.uniform(h * 0.12, h * 0.42) if not small else random.uniform(h * 0.35, h * 0.55)
        if kind == 'text':
            apex, x = h * 0.3, w * random.uniform(0.35, 0.65)
        vy = -math.sqrt(2 * 90 * (h - apex))
        kind = kind or random.choice(['peony', 'peony', 'chrysanthemum', 'willow', 'ring', 'crossette', 'glitter',
                                      'twocolor', 'palm', 'heart', 'peony', 'chrysanthemum'])
        if small:
            kind = random.choice(['peony', 'glitter', 'ring'])
        self.rockets.append({'x': x, 'y': float(h), 'vx': random.uniform(-8, 8), 'vy': vy, 'kind': kind,
                             'pal': random.choice(PALETTES), 'small': small})

    def burst(self, r):
        x, y, kind, pal = r['x'], r['y'], r['kind'], r['pal']
        small = r['small']
        sc = (0.55 if small else 1.0) * self.h / 240
        D = self.dots
        n = int((180 if small else 520) * min(1.6, max(0.7, sc)))
        col = np.array(pal[0], np.float32)

        def sphere(n, sp, jitter=0.12):
            a = np.random.uniform(0, math.tau, n).astype(np.float32)
            z = np.random.uniform(-1, 1, n).astype(np.float32)
            rr = np.sqrt(1 - z * z)
            s = sp * (1 + np.random.uniform(-jitter, jitter, n).astype(np.float32))
            return np.cos(a) * rr * s, np.sin(a) * rr * s

        if kind in ('peony', 'twocolor', 'chrysanthemum', 'glitter'):
            vx, vy = sphere(n, 62 * sc)
            if kind == 'twocolor' and len(pal) > 1:
                cols = np.where((vx > 0)[:, None], np.array(pal[0], np.float32), np.array(pal[1], np.float32))
            else:
                cols = col
            life = np.random.uniform(1.1, 1.8, n) * (1.3 if kind == 'chrysanthemum' else 1)
            D.add(x + vx * 0.02, y + vy * 0.02, vx, vy, life, cols, drag=1.4, grav=28,
                  flick=0.9 if kind == 'glitter' else 0.15, size=1)
            if len(pal) > 1 and kind != 'twocolor':            # inner core in the second color
                vx2, vy2 = sphere(n // 3, 30 * sc)
                D.add(x, y, vx2, vy2, np.random.uniform(0.8, 1.3, n // 3), np.array(pal[1], np.float32),
                      drag=1.6, grav=24, flick=0.3)
        elif kind == 'willow':
            vx, vy = sphere(n, 52 * sc)
            gold = np.array([255, 196, 90], np.float32)
            D.add(x, y, vx, vy, np.random.uniform(2.6, 3.6, n), gold, drag=1.1, grav=18, flick=0.4)
        elif kind == 'ring':
            a = np.linspace(0, math.tau, n // 2, endpoint=False).astype(np.float32)
            tilt = random.uniform(0.3, 0.9)
            rot = random.uniform(0, math.pi)
            ux, uy = np.cos(a) * 60 * sc, np.sin(a) * 60 * sc * tilt
            vx = ux * math.cos(rot) - uy * math.sin(rot)
            vy = ux * math.sin(rot) + uy * math.cos(rot)
            D.add(x, y, vx, vy, np.random.uniform(1.2, 1.5, len(a)), col, drag=1.3, grav=20, flick=0.2)
        elif kind == 'crossette':
            a = np.linspace(0, math.tau, 8, endpoint=False).astype(np.float32) + random.uniform(0, 1)
            D.add(x, y, np.cos(a) * 55 * sc, np.sin(a) * 55 * sc, 0.75, col, drag=0.8, grav=30, tag=1, size=2)
        elif kind == 'palm':
            a = np.linspace(0, math.tau, 7, endpoint=False).astype(np.float32) - math.pi / 2
            for k in range(36):
                f = 0.5 + k / 36
                D.add(x, y, np.cos(a) * 60 * sc * f, np.sin(a) * 60 * sc * f, 1.6 + 0.4 * f,
                      np.array([255, 200, 110], np.float32), drag=1.2, grav=34, flick=0.25)
        elif kind == 'heart':
            t = np.linspace(0, math.tau, n // 2, endpoint=False).astype(np.float32)
            hx = 16 * np.sin(t) ** 3
            hy = -(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t))
            d = 2.6
            D.add(x, y, hx * 2.4 * sc * d / 3, hy * 2.4 * sc * d / 3, np.random.uniform(1.4, 1.8, len(t)),
                  np.array([255, 70, 120], np.float32), drag=d, grav=6, flick=0.2)
        elif kind == 'text':
            text = r.get('text', 'HNY')
            pts = _text_points(text)
            k = min(5.0 * sc, self.w * 0.5 / max(1, len(text) * 4))
            d = 2.4
            m = len(pts)
            cols = np.array(random.choice(PALETTES)[0], np.float32)
            for rep in range(max(6, int(k * k * 0.55))):     # fill every font dot so the numbers read well
                jx = np.random.uniform(-k * 0.5, k * 0.5, m)
                jy = np.random.uniform(-k * 0.5, k * 0.5, m)
                D.add(x + np.random.uniform(-0.5, 0.5, m), y + np.random.uniform(-0.5, 0.5, m),
                      (pts[:, 0] * k + jx) * d, (pts[:, 1] * k + jy) * d,
                      np.random.uniform(2.4, 3.2, m), cols, drag=d, grav=3, flick=0.3)
        # flash + glow + smoke
        self.flash = min(0.8, self.flash + (0.25 if small else 0.5))
        self.flash_col = tuple(int(v) for v in pal[0])
        glow(self.fx, x, y, int(14 * max(0.6, sc)), tuple(int(v * 0.6) for v in pal[0]))
        for _ in range(3):
            self.smoke.append([x + random.uniform(-10, 10), y + random.uniform(-6, 6), random.uniform(6, 14) * sc, 1.0])

    def update(self, dt, energy):
        super().update(dt, energy)
        now = datetime.datetime.now()
        midnight = (now.month == 1 and now.day == 1 and now.hour == 0 and now.minute < 20)
        self.next -= dt * (1 + energy * 2 + (3 if midnight else 0) + (4 if self.finale > 0 else 0))
        if self.next <= 0:
            self.launch()
            if random.random() < 0.25:
                self.launch()
            self.next = random.uniform(0.6, 1.8)
            if random.random() < (0.5 if midnight else 0.06):
                yr = now.year + (1 if now.month == 12 else 0)
                self.launch(kind='text')
                self.rockets[-1]['text'] = random.choice([str(yr), 'HNY', str(yr)]) if midnight or now.month in (12, 1) \
                    else random.choice(['PYVTERM', 'HI', str(yr)])
        if signals.enter != self.last_enter:
            self.last_enter = signals.enter
            for _ in range(random.randint(1, 3)):
                self.launch()
        new, self.seq = signals.take_letters(self.seq)
        for l in new:
            if l[4]:
                self.typed_n += 1
                if self.typed_n % 3 == 0:
                    self.launch(small=True, x=l[2])
        if signals.cmd is not self.last_cmd and signals.cmd:
            self.last_cmd = signals.cmd
            if signals.cmd[0] == 0 and signals.cmd[1] >= 2:
                self.finale = 3.0
            elif signals.cmd[0]:
                self.launch(kind='peony')
                self.rockets[-1]['pal'] = [(255, 40, 30)]
        self.finale = max(0.0, self.finale - dt)
        D = self.dots
        for r in self.rockets:
            r['vy'] += 90 * dt
            r['x'] += r['vx'] * dt
            r['y'] += r['vy'] * dt
            k = 3
            D.add(np.full(k, r['x'], np.float32) + np.random.uniform(-0.6, 0.6, k), r['y'] + np.random.uniform(0, 2, k),
                  np.random.uniform(-6, 6, k), np.random.uniform(8, 24, k), np.random.uniform(0.25, 0.5, k),
                  np.array([255, 190, 110], np.float32), drag=2, grav=20, flick=0.6)
            if r['vy'] >= -6:
                self.burst(r)
                r['done'] = True
        self.rockets = [r for r in self.rockets if not r.get('done')]
        # crossette carriers split into four
        n = D.n
        if n:
            split = (D.tag[:n] == 1) & (D.life[:n] < 0.05)
            idx = np.nonzero(split)[0]
            for i in idx[:12]:
                a = np.array([0, 1.57, 3.14, 4.71], np.float32) + random.uniform(0, 1.5)
                D.add(np.full(4, D.x[i]), D.y[i], np.cos(a) * 40, np.sin(a) * 40, 0.9, D.col[i], drag=1.5, grav=26, flick=0.3)
            if len(idx):
                D.tag[idx] = 0
        D.step(dt)
        for s in self.smoke:
            s[0] += 4 * dt
            s[1] -= 2 * dt
            s[2] += 3 * dt
            s[3] -= dt * 0.12
        self.smoke = [s for s in self.smoke if s[3] > 0][-40:]
        self.flash = max(0.0, self.flash - dt * 4.0)
        self.dt_last = dt

    def draw(self, surf, first):
        w, h, rv = self.w, self.h, self.river
        surf.blit(gradient(w, rv, (4, 4, 18), (28, 14, 44), self.cache, 'sky'), (0, 0))
        for x, y, tw in self.stars:
            v = int(110 + 90 * math.sin(self.t * 1.5 + tw * 40))
            surf.fill((v, v, v), (int(x), int(y), 1, 1))
        if self.flash > 0.01:
            f = self.flash * 0.12
            surf.fill(tuple(int(c * f) for c in self.flash_col), (0, 0, w, rv), special_flags=ADD)
        # smoke drifting in the light
        for x, y, r, life in self.smoke:
            v = int(10 * life)
            glow(surf, x, y, max(2, int(r)), (v, v, v + 2))
        # fireworks layer: fade the old frame (trails), draw new pixels, add onto the sky
        fade = int(255 * math.exp(-getattr(self, 'dt_last', 1 / 30) * 7.5))
        self.fx.fill((fade, fade, fade), special_flags=MULT)
        self.dots.draw(self.fx)
        surf.blit(self.fx, (0, 0), special_flags=ADD)
        surf.blit(self.city, (0, 0))
        # countdown on New Year's Eve
        now = datetime.datetime.now()
        if now.month == 12 and now.day == 31 and now.hour == 23:
            left = 3600 - now.minute * 60 - now.second
            tiny_text(surf, w // 2 - 22, 4, 'T-%02d:%02d' % (left // 60, left % 60), (255, 230, 150))
        elif now.month == 1 and now.day == 1 and now.hour == 0:
            tiny_text(surf, w // 2 - 34, 4, 'HAPPY NEW YEAR %d' % now.year, (255, 230, 150))
        # river: rippled, darkened mirror of sky + fireworks + city lights
        depth = h - rv
        surf.fill((4, 4, 14), (0, rv, w, depth))
        src = surf.subsurface((0, max(0, rv - depth), w, min(depth, rv))).copy()
        src = pygame.transform.flip(src, False, True)
        src.fill((120, 120, 150), special_flags=MULT)
        for yy in range(0, src.get_height(), 1):
            dx = int(math.sin(self.t * 2.2 + yy * 0.5) * (1 + yy * 0.12))
            surf.blit(src, (dx, rv + yy), (0, yy, w, 1))
        surf.fill((30, 30, 50), (0, rv, w, 1), special_flags=ADD)


# ============================================================================ christmas
def _star_pts(cx, cy, r1, r2, n=5, rot=-math.pi / 2):
    return [(cx + math.cos(rot + i * math.pi / n) * (r1 if i % 2 == 0 else r2),
             cy + math.sin(rot + i * math.pi / n) * (r1 if i % 2 == 0 else r2)) for i in range(2 * n)]


class Christmas(Background):
    name = 'christmas'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.k = k = h / 240
        rng = random.Random(1224)
        self.ground = int(h * 0.72)
        self.static = pygame.Surface((w, h))
        st = self.static
        st.blit(gradient(w, h, (6, 10, 34), (40, 46, 96), self.cache, 'sky'), (0, 0))
        self.stars = [(rng.uniform(0, w), rng.uniform(0, h * 0.5), rng.random()) for _ in range(90)]
        self.moon = (int(w * 0.78), int(h * 0.17), max(8, int(14 * k)))
        mx, my, mr = self.moon
        glow(st, mx, my, mr * 4, (34, 36, 50))
        pygame.draw.circle(st, (246, 244, 226), (mx, my), mr)
        for dx, dy, r in ((-3, -2, 3), (4, 3, 2), (-1, 5, 2)):
            pygame.draw.circle(st, (222, 220, 204), (mx + int(dx * k), my + int(dy * k)), max(1, int(r * k)))
        # far hills with pines
        for layer, (yb, col, amp) in enumerate(((0.60, (150, 170, 210), 0.05), (0.66, (196, 214, 240), 0.04))):
            pts = [(0, h)]
            for x in range(0, w + 6, 6):
                pts.append((x, int(h * yb - math.sin(x / w * (4 + layer * 3) + layer) * h * amp)))
            pts.append((w, h))
            pygame.draw.polygon(st, col, pts)
            for _ in range(18 + layer * 10):
                x = rng.uniform(0, w)
                y = h * yb - math.sin(x / w * (4 + layer * 3) + layer) * h * amp
                self._pine(st, x, y + 2, rng.uniform(6, 12) * k * (0.7 + layer * 0.3), _lerp(col, (20, 50, 40), 0.55 + 0.2 * layer))
        # snowy foreground
        pygame.draw.ellipse(st, (226, 236, 250), (-w * 0.2, self.ground - h * 0.06, w * 1.4, h * 0.6))
        for _ in range(60):
            x, y = rng.uniform(0, w), rng.uniform(self.ground, h)
            st.fill((200, 214, 238), (int(x), int(y), int(rng.uniform(3, 9) * k), 1))
        # houses
        self.houses = []
        for i, (fx, sc) in enumerate(((0.06, 0.9), (0.2, 1.1), (0.36, 0.8), (0.5, 1.0))):
            hx, hy = int(w * fx), int(h * 0.67) + int(i % 2 * 3 * k)
            self.houses.append(self._house(st, hx, hy, sc * k, rng))
        self.tree = (int(w * 0.75), self.ground + int(h * 0.12))
        self.lights = self._tree(st)
        self.snowman = (int(w * 0.6), self.ground + int(h * 0.15))
        self.snow = Dots(2500)
        for _ in range(4):
            self._spawn_snow(400, anywhere=True)
        self.sleigh = None
        self.next_sleigh = 8.0
        self.smoke = []
        self.shoot = None
        self.sparkle = 0.0
        self.wave = 0.0
        self.seq = signals.letter_seq
        self.last_enter = signals.enter
        self.last_cmd = signals.cmd

    def _pine(self, s, x, y, size, col):
        for i in range(3):
            ww = size * (1 - i * 0.25)
            yy = y - i * size * 0.45
            pygame.draw.polygon(s, col, [(x - ww * 0.5, yy), (x + ww * 0.5, yy), (x, yy - size * 0.7)])
        s.fill(_lerp(col, (60, 40, 30), 0.5), (int(x), int(y), 1, max(1, int(size * 0.2))))

    def _house(self, s, x, y, k, rng):
        wall = rng.choice([(150, 70, 60), (120, 90, 70), (170, 130, 90), (110, 80, 100)])
        bw, bh = int(30 * k), int(18 * k)
        s.fill(_lerp(wall, (20, 20, 40), 0.45), (x, y - bh, bw, bh))
        s.fill(_lerp(wall, (20, 20, 40), 0.25), (x, y - bh, int(bw * 0.6), bh))
        roof = [(x - 3 * k, y - bh), (x + bw + 3 * k, y - bh), (x + bw * 0.5, y - bh - 14 * k)]
        pygame.draw.polygon(s, (90, 30, 30), roof)
        pygame.draw.polygon(s, (240, 246, 255), [(x - 3 * k, y - bh), (x + bw + 3 * k, y - bh),
                                                 (x + bw * 0.5 + 6 * k, y - bh - 10 * k), (x + bw * 0.5, y - bh - 14 * k),
                                                 (x + bw * 0.5 - 6 * k, y - bh - 10 * k)])
        for ix in range(int(x), int(x + bw), max(2, int(4 * k))):     # icicles
            s.fill((210, 230, 255), (ix, int(y - bh), 1, rng.randint(1, max(2, int(3 * k)))))
        chim = (int(x + bw * 0.7), int(y - bh - 12 * k))
        s.fill((80, 40, 40), (chim[0], chim[1], int(4 * k), int(8 * k)))
        s.fill((240, 246, 255), (chim[0] - 1, chim[1] - 1, int(4 * k) + 2, max(1, int(2 * k))))
        wins = []
        for wx in (x + int(5 * k), x + int(19 * k)):
            r = pygame.Rect(wx, y - bh + int(5 * k), int(6 * k), int(6 * k))
            wins.append(r)
        s.fill((60, 30, 20), (x + int(13 * k), y - int(10 * k), int(5 * k), int(10 * k)))
        return {'wins': wins, 'chim': chim, 'k': k, 'ph': rng.random() * 9}

    def _tree(self, s):
        tx, ty = self.tree
        k = self.k
        H = int(self.h * 0.42)
        s.fill((80, 50, 30), (tx - int(3 * k), ty - int(8 * k), int(6 * k), int(8 * k)))
        lights = []
        rng = random.Random(25)
        for i in range(5):
            y0 = ty - int(8 * k) - i * H * 0.18
            ww = H * (0.42 - i * 0.07)
            top = y0 - H * 0.3
            pygame.draw.polygon(s, (14, 70, 40), [(tx - ww, y0), (tx + ww, y0), (tx, top)])
            pygame.draw.polygon(s, (22, 96, 54), [(tx - ww * 0.95, y0 - 1), (tx, y0 - 1), (tx, top + 2)])
            for x in range(int(tx - ww), int(tx + ww), max(2, int(3 * k))):    # snow on the branch tips
                if rng.random() < 0.45:
                    s.fill((230, 240, 255), (x, int(y0) - 1, max(1, int(2 * k)), 1))
            for j in range(int(10 + ww * 0.25)):
                q = rng.random()
                yy = y0 - (y0 - top) * q * 0.9
                half = ww * (1 - q * 0.9) * 0.9
                lights.append((tx + rng.uniform(-half, half), yy, rng.choice([(255, 60, 60), (255, 200, 60), (80, 160, 255),
                                                                              (80, 255, 120), (255, 120, 220)]), rng.random()))
        self.star_pos = (tx, int(ty - int(8 * k) - 4 * H * 0.18 - H * 0.3 - 2 * k))
        # presents
        for dx, (bw, bh, c, rc) in zip((-24, -12, 10, 20), ((10, 7, (200, 40, 50), (255, 220, 80)), (8, 9, (60, 120, 220), (240, 240, 255)),
                                                            (11, 6, (60, 170, 80), (255, 80, 80)), (7, 8, (240, 200, 60), (200, 40, 40)))):
            x0, y0 = tx + int(dx * k), ty - int(bh * k)
            s.fill(c, (x0, y0, int(bw * k), int(bh * k)))
            s.fill(rc, (x0 + int(bw * k / 2), y0, max(1, int(k)), int(bh * k)))
            s.fill(rc, (x0, y0 + int(bh * k / 2), int(bw * k), max(1, int(k))))
            s.fill(rc, (x0 + int(bw * k / 2) - int(2 * k), y0 - int(2 * k), int(4 * k), int(2 * k)))
        return lights

    def _spawn_snow(self, n, anywhere=False):
        w, h = self.w, self.h
        depth = np.random.random(n).astype(np.float32)
        y = np.random.uniform(0, h, n) if anywhere else np.random.uniform(-10, 0, n)
        v = 0.5 + depth
        col = (np.array([200, 210, 235], np.float32) * (0.55 + 0.45 * depth[:, None]))
        self.snow.add(np.random.uniform(0, w, n), y, np.random.uniform(-3, 3, n), 10 + 22 * v,
                      np.full(n, 99.0), col, size=np.where(depth > 0.82, 2, 1).astype(np.int8))

    def update(self, dt, energy):
        super().update(dt, energy)
        w, h = self.w, self.h
        rate = 60 + energy * 140
        n = np.random.poisson(rate * dt)
        if n:
            self._spawn_snow(int(n))
        S = self.snow
        m = S.n
        if m:
            S.vx[:m] = np.sin(self.t * 0.8 + S.y[:m] * 0.05) * 6
            S.life[:m] = np.where(S.y[:m] > h + 2, 0, 99)
        S.step(dt)
        new, self.seq = signals.take_letters(self.seq)
        if any(l[4] for l in new):
            self.sparkle = 0.6
        self.sparkle = max(0.0, self.sparkle - dt)
        if signals.enter != self.last_enter:
            self.last_enter = signals.enter
            self.wave = 1.2
            self.shoot = [random.uniform(w * 0.1, w * 0.6), random.uniform(h * 0.05, h * 0.2), 0.0]
        self.wave = max(0.0, self.wave - dt)
        if self.shoot:
            self.shoot[2] += dt
            if self.shoot[2] > 0.9:
                self.shoot = None
        if signals.cmd is not self.last_cmd and signals.cmd:
            self.last_cmd = signals.cmd
            if signals.cmd[0] == 0 and signals.cmd[1] >= 2 and self.sleigh is None:
                self.next_sleigh = 0
        self.next_sleigh -= dt
        if self.sleigh is None and self.next_sleigh <= 0:
            self.sleigh = {'x': -60.0, 'trail': Dots(600)}
        if self.sleigh:
            sl = self.sleigh
            sl['x'] += dt * w * 0.09
            sx, sy = self._sleigh_pos(sl['x'])
            sl['trail'].add(np.random.uniform(sx - 2, sx + 2, 3), np.random.uniform(sy + 2, sy + 5, 3),
                            np.random.uniform(-6, 6, 3), np.random.uniform(2, 10, 3), np.random.uniform(0.6, 1.2, 3),
                            np.array([255, 220, 140], np.float32), drag=1, grav=8, flick=0.8)
            sl['trail'].step(dt)
            if sl['x'] > w + 120:
                self.sleigh = None
                self.next_sleigh = random.uniform(40, 80)
        for hs in self.houses:
            if random.random() < dt * 2:
                cx, cy = hs['chim']
                self.smoke.append([cx + 2 * hs['k'], cy - 1, 1.5 * hs['k'], 1.0])
        for p in self.smoke:
            p[0] += (3 + math.sin(self.t + p[1]) * 2) * dt
            p[1] -= 7 * dt
            p[2] += 1.6 * dt
            p[3] -= dt * 0.35
        self.smoke = [p for p in self.smoke if p[3] > 0][-60:]

    def _sleigh_pos(self, x):
        w, h = self.w, self.h
        q = x / w
        return x, h * 0.32 - math.sin(min(1.2, max(-0.2, q)) * math.pi) * h * 0.2

    def draw(self, surf, first):
        w, h, k = self.w, self.h, self.k
        surf.blit(self.static, (0, 0))
        for x, y, tw in self.stars:
            v = int(120 + 110 * math.sin(self.t * 1.7 + tw * 40))
            surf.fill((v, v, min(255, v + 20)), (int(x), int(y), 1, 1))
        if self.shoot:
            x, y, a = self.shoot
            ex, ey = x + a * w * 0.35, y + a * h * 0.12
            pygame.draw.line(surf, (200, 210, 255), (ex - 14 * k, ey - 5 * k), (ex, ey))
            surf.fill((255, 255, 255), (int(ex), int(ey), 2, 2))
        # windows flicker warmly, chimney smoke
        for hs in self.houses:
            for i, r in enumerate(hs['wins']):
                f = 0.85 + 0.15 * math.sin(self.t * 6 + hs['ph'] + i * 2.3) * math.sin(self.t * 2.3 + i)
                c = (int(255 * f), int(196 * f), int(100 * f))
                surf.fill(c, r)
                surf.fill((70, 40, 30), (r.x + r.w // 2, r.y, 1, r.h))
                surf.fill((70, 40, 30), (r.x, r.y + r.h // 2, r.w, 1))
                glow(surf, r.centerx, r.centery, int(8 * hs['k']), (40, 26, 8))
        for x, y, r, life in self.smoke:
            v = int(46 * life)
            glow(surf, x, y, max(2, int(r * 1.6)), (v, v, v + 8))
        # tree lights (chasing pattern), star
        t = self.t
        boost = 1.0 + self.sparkle
        for i, (x, y, c, ph) in enumerate(self.lights):
            on = (math.sin(t * 2.4 + ph * 6.28) > -0.2) if (int(t / 6) % 2) else ((i + int(t * 4)) % 3 != 0)
            if on:
                cc = tuple(min(255, int(v * boost)) for v in c)
                surf.fill(cc, (int(x), int(y), max(1, int(k * 1.4)), max(1, int(k * 1.4))))
                glow(surf, x, y, int(4 * k), tuple(int(v * 0.18) for v in c))
        sx, sy = self.star_pos
        pulse = 0.75 + 0.25 * math.sin(t * 3)
        glow(surf, sx, sy, int(18 * k * pulse), (int(90 * pulse), int(76 * pulse), int(20 * pulse)))
        pygame.draw.polygon(surf, (255, 224, 90), _star_pts(sx, sy, 7 * k, 3 * k))
        pygame.draw.polygon(surf, (255, 250, 210), _star_pts(sx, sy, 3.5 * k, 1.5 * k))
        self._snowman(surf)
        if self.sleigh:
            self.sleigh['trail'].draw(surf)
            self._draw_sleigh(surf, *self._sleigh_pos(self.sleigh['x']))
        self.snow.draw(surf, fade_pow=0)

    def _snowman(self, surf):
        x, y = self.snowman
        k = self.k
        for r, dy in ((9, 0), (7, -14), (5, -25)):
            pygame.draw.circle(surf, (150, 166, 200), (x, int(y + dy * k)), int(r * k) + 1)
            pygame.draw.circle(surf, (246, 250, 255), (x, int(y + dy * k)), int(r * k))
            pygame.draw.circle(surf, (200, 214, 236), (x + int(r * 0.35 * k), int(y + dy * k + r * 0.3 * k)), int(r * 0.6 * k))
        hy = int(y - 25 * k)
        surf.fill((240, 140, 40), (x + int(2 * k), hy, int(4 * k), max(1, int(k))))          # carrot
        surf.fill((20, 20, 20), (x - int(2 * k), hy - int(2 * k), max(1, int(k)), max(1, int(k))))
        surf.fill((20, 20, 20), (x + int(1 * k), hy - int(2 * k), max(1, int(k)), max(1, int(k))))
        surf.fill((30, 30, 36), (x - int(5 * k), hy - int(6 * k), int(10 * k), max(1, int(2 * k))))  # hat
        surf.fill((30, 30, 36), (x - int(3 * k), hy - int(12 * k), int(6 * k), int(6 * k)))
        surf.fill((200, 40, 40), (x - int(5 * k), int(y - 20 * k), int(10 * k), int(2 * k)))        # scarf
        surf.fill((200, 40, 40), (x + int(2 * k), int(y - 20 * k), int(2 * k), int(6 * k)))
        for i in range(3):
            surf.fill((30, 30, 30), (x, int(y - (16 - i * 3) * k), max(1, int(k)), max(1, int(k))))
        wave = math.sin(self.t * 12) * 3 * k if self.wave > 0 else 0
        arm = (90, 60, 30)
        pygame.draw.line(surf, arm, (x - 6 * k, y - 14 * k), (x - 14 * k, y - 20 * k))
        pygame.draw.line(surf, arm, (x + 6 * k, y - 14 * k), (x + 14 * k, y - 22 * k - wave))

    def _draw_sleigh(self, surf, x, y):
        k = self.k
        col = (20, 14, 24)
        for i in range(4):          # reindeer pairs ahead of the sleigh
            rx = x + (14 + i * 9) * k
            ry = y - (i * 1.5) * k + math.sin(self.t * 8 + i) * k
            surf.fill(col, (int(rx), int(ry), int(6 * k), int(2 * k)))
            leg = int(self.t * 10 + i) % 2
            surf.fill(col, (int(rx + k), int(ry + 2 * k), max(1, int(k)), int((2 + leg) * k)))
            surf.fill(col, (int(rx + 4 * k), int(ry + 2 * k), max(1, int(k)), int((3 - leg) * k)))
            surf.fill(col, (int(rx + 5 * k), int(ry - 2 * k), int(2 * k), int(2 * k)))
            surf.fill(col, (int(rx + 6 * k), int(ry - 4 * k), max(1, int(k)), int(2 * k)))
            if i == 3:
                glow(surf, rx + 7 * k, ry - k, int(4 * k), (120, 20, 20))
                surf.fill((255, 40, 40), (int(rx + 7 * k), int(ry - k), max(1, int(k)), max(1, int(k))))
        pygame.draw.line(surf, col, (x + 6 * k, y), (x + 14 * k, y - k))
        surf.fill(col, (int(x - 6 * k), int(y - 3 * k), int(12 * k), int(4 * k)))
        pygame.draw.line(surf, col, (x - 8 * k, y + 2 * k), (x + 7 * k, y + 2 * k))
        surf.fill(col, (int(x - 3 * k), int(y - 7 * k), int(4 * k), int(4 * k)))        # santa
        surf.fill(col, (int(x - 7 * k), int(y - 6 * k), int(4 * k), int(4 * k)))        # sack


# ============================================================================ halloween
class Halloween(Background):
    name = 'halloween'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.k = k = h / 240
        rng = random.Random(1031)
        st = self.static = pygame.Surface((w, h))
        st.blit(gradient(w, h, (16, 6, 30), (120, 46, 40), self.cache, 'sky'), (0, 0))
        self.stars = [(rng.uniform(0, w), rng.uniform(0, h * 0.45), rng.random()) for _ in range(60)]
        mx, my, mr = int(w * 0.7), int(h * 0.22), max(10, int(22 * k))
        self.moon = (mx, my, mr)
        glow(st, mx, my, mr * 4, (60, 40, 20))
        pygame.draw.circle(st, (250, 226, 160), (mx, my), mr)
        for dx, dy, r in ((-6, -4, 5), (7, 3, 4), (-2, 8, 3), (5, -8, 2)):
            pygame.draw.circle(st, (226, 200, 140), (mx + int(dx * k), my + int(dy * k)), max(1, int(r * k)))
        sil = (8, 4, 12)
        hill = [(0, h)]
        for x in range(0, w + 4, 4):
            hill.append((x, int(h * 0.7 - math.exp(-((x - w * 0.3) / (w * 0.22)) ** 2) * h * 0.16 - math.sin(x / w * 7) * h * 0.02)))
        hill.append((w, h))
        pygame.draw.polygon(st, sil, hill)
        hx, hy = int(w * 0.3), int(h * 0.52)
        self.house = (hx, hy)
        self.windows = self._house(st, hx, hy, k, sil)
        self._dead_tree(st, w * 0.08, h * 0.74, -math.pi / 2, h * 0.16, 6, sil, rng)
        self._dead_tree(st, w * 0.86, h * 0.76, -math.pi / 2 - 0.1, h * 0.13, 5, sil, rng)
        for i in range(7):                      # graveyard
            gx = int(w * (0.5 + i * 0.05)) + rng.randint(-3, 3)
            gy = int(h * 0.8) + rng.randint(-2, 2)
            if i % 3 == 0:
                st.fill(sil, (gx, gy - int(12 * k), int(2 * k), int(12 * k)))
                st.fill(sil, (gx - int(3 * k), gy - int(9 * k), int(8 * k), int(2 * k)))
            else:
                st.fill(sil, (gx - int(3 * k), gy - int(9 * k), int(7 * k), int(9 * k)))
                pygame.draw.circle(st, sil, (gx, gy - int(9 * k)), int(3.5 * k))
        for x in range(0, int(w * 0.48), max(3, int(4 * k))):     # crooked fence
            fy = int(h * 0.86)
            st.fill(sil, (x, fy - int(rng.uniform(6, 9) * k), max(1, int(1.5 * k)), int(10 * k)))
        st.fill(sil, (0, int(h * 0.86 - 5 * k), int(w * 0.48), max(1, int(k))))
        st.fill((10, 4, 10), (0, int(h * 0.88), w, h))
        self.pumpkins = [(int(w * fx), int(h * 0.95), s * k, rng.random() * 9) for fx, s in ((0.12, 1.2), (0.42, 0.9), (0.62, 1.4), (0.9, 1.0))]
        self.bats = [{'x': rng.uniform(0, w), 'y': rng.uniform(h * 0.1, h * 0.5), 'vx': rng.choice((-1, 1)) * rng.uniform(15, 30),
                      'ph': rng.random() * 9} for _ in range(9)]
        self.ghost = {'x': w * 0.45, 'y': h * 0.5, 'a': 0.0, 'boo': 0.0}
        fn = np.random.default_rng(13).random((64, 32)).astype(np.float32)
        for _ in range(4):
            fn = (fn + np.roll(fn, 1, 0) + np.roll(fn, 1, 1) + np.roll(fn, -1, 0) + np.roll(fn, -1, 1)) / 5
        fn = (fn - fn.min()) / (fn.max() - fn.min() + 1e-6)
        fog = pygame.Surface((64, 32), pygame.SRCALPHA)
        rgb = np.full((64, 32, 3), (150, 140, 170), np.uint8)
        pygame.surfarray.pixels3d(fog)[:] = rgb
        al = pygame.surfarray.pixels_alpha(fog)
        edge = np.clip(np.sin(np.linspace(0, math.pi, 32, dtype=np.float32)), 0, 1)[None, :] ** 1.5
        al[:] = (np.clip(fn * 1.6 - 0.4, 0, 1) * 80 * edge).astype(np.uint8)
        del al
        self.fog = pygame.transform.smoothscale(fog, (w, int(h * 0.3)))
        self.spider_y = h * 0.15
        self.lightning = 0.0
        self.bolt = []
        self.last_cmd = signals.cmd
        self.seq = signals.letter_seq
        self.flicker = 0.0

    def _house(self, s, x, y, k, col):
        W, H = int(60 * k), int(34 * k)
        s.fill(col, (x - W // 2, y - H, W, H + int(20 * k)))
        pygame.draw.polygon(s, col, [(x - W // 2 - 4 * k, y - H), (x + W // 2 + 4 * k, y - H), (x + 4 * k, y - H - 22 * k)])
        for tx, th in ((x - W // 2 - 2 * k, 46), (x + W // 2 - 8 * k, 56)):
            s.fill(col, (int(tx), int(y - th * k), int(10 * k), int(th * k)))
            pygame.draw.polygon(s, col, [(tx - 3 * k, y - th * k), (tx + 13 * k, y - th * k), (tx + 6 * k, y - th * k - 16 * k)])
        s.fill(col, (int(x + 10 * k), int(y - H - 30 * k), int(4 * k), int(14 * k)))
        wins = []
        for wx, wy in ((-22, -24), (-8, -24), (12, -24), (-22, -10), (12, -10), (-1, -40), (x and 24, -42)):
            r = pygame.Rect(int(x + wx * k), int(y + wy * k), int(5 * k), int(7 * k))
            wins.append(r)
        wins.append(pygame.Rect(int(x - W // 2 + 1 * k), int(y - 40 * k), int(4 * k), int(6 * k)))
        return wins

    def _dead_tree(self, s, x, y, a, L, depth, col, rng):
        if depth == 0 or L < 2:
            return
        ex, ey = x + math.cos(a) * L, y + math.sin(a) * L
        pygame.draw.line(s, col, (x, y), (ex, ey), max(1, depth - 1))
        for _ in range(2):
            self._dead_tree(s, ex, ey, a + rng.uniform(-0.75, 0.75), L * rng.uniform(0.55, 0.75), depth - 1, col, rng)

    def update(self, dt, energy):
        super().update(dt, energy)
        w, h = self.w, self.h
        for b in self.bats:
            b['x'] += b['vx'] * dt
            b['y'] += math.sin(self.t * 2 + b['ph']) * 12 * dt
            if b['x'] < -10 or b['x'] > w + 10:
                b['vx'] = -b['vx']
        g = self.ghost
        g['a'] = max(0.0, min(1.0, g['a'] + (dt * 0.3 if math.sin(self.t * 0.25) > 0 else -dt * 0.3)))
        g['x'] += math.sin(self.t * 0.4) * 10 * dt
        g['boo'] = max(0.0, g['boo'] - dt)
        new, self.seq = signals.take_letters(self.seq)
        if any(l[4] for l in new):
            self.flicker = 0.5
            self.spider_y = min(h * 0.45, self.spider_y + 4)
        else:
            self.spider_y += (h * 0.15 - self.spider_y) * dt * 0.5
        self.flicker = max(0.0, self.flicker - dt)
        if signals.cmd is not self.last_cmd and signals.cmd:
            self.last_cmd = signals.cmd
            if signals.cmd[0]:
                self.lightning = 0.6
                x = random.uniform(w * 0.2, w * 0.9)
                pts = [(x, 0)]
                y = 0
                while y < h * 0.6:
                    y += random.uniform(8, 18) * self.k
                    x += random.uniform(-10, 10) * self.k
                    pts.append((x, y))
                self.bolt = pts
                g['a'] = 1.0
                g['boo'] = 2.0
                signals.shake = 0.35
        self.lightning = max(0.0, self.lightning - dt)

    def draw(self, surf, first):
        w, h, k = self.w, self.h, self.k
        surf.blit(self.static, (0, 0))
        for x, y, tw in self.stars:
            v = int(100 + 80 * math.sin(self.t * 1.3 + tw * 40))
            surf.fill((v, v, v), (int(x), int(y), 1, 1))
        if self.lightning > 0:
            f = self.lightning / 0.6
            if int(self.lightning * 20) % 3:
                surf.fill((int(120 * f), int(110 * f), int(140 * f)), (0, 0, w, h), special_flags=ADD)
                if len(self.bolt) > 1:
                    pygame.draw.lines(surf, (255, 255, 255), False, self.bolt, max(1, int(2 * k)))
        for i, r in enumerate(self.windows):
            fl = math.sin(self.t * (7 + i) + i * 3) * math.sin(self.t * 3.1 + i) + self.flicker
            if i % 3 == 0:
                c = (90, 255, 120) if fl > -0.3 else (20, 60, 30)
            else:
                c = (255, 160, 40) if fl > -0.6 else (90, 50, 20)
            surf.fill(c, r)
            if i == 1 and int(self.t / 3) % 4 == 0:          # someone is watching...
                surf.fill((10, 4, 12), (r.x + 1, r.y + 1, r.w - 2, r.h - 1))
            glow(surf, r.centerx, r.centery, int(6 * k), tuple(v // 6 for v in c))
        # bats
        for b in self.bats:
            up = math.sin(self.t * 14 + b['ph']) > 0
            x, y = int(b['x']), int(b['y'])
            c = (6, 2, 10)
            surf.fill(c, (x - 1, y, 3, 2))
            if up:
                surf.fill(c, (x - 4, y - 2, 3, 1))
                surf.fill(c, (x + 2, y - 2, 3, 1))
                surf.fill(c, (x - 2, y - 1, 1, 1))
                surf.fill(c, (x + 2, y - 1, 1, 1))
            else:
                surf.fill(c, (x - 4, y + 1, 3, 1))
                surf.fill(c, (x + 2, y + 1, 3, 1))
        # ghost
        g = self.ghost
        if g['a'] > 0.02:
            gx, gy = int(g['x']), int(g['y'] + math.sin(self.t * 2) * 4 * k)
            gs = pygame.Surface((int(16 * k), int(20 * k)), pygame.SRCALPHA)
            gs.fill((0, 0, 0, 0))
            pygame.draw.ellipse(gs, (236, 236, 250, 255), (0, 0, int(16 * k), int(16 * k)))
            gs.fill((236, 236, 250, 255), (0, int(8 * k), int(16 * k), int(8 * k)))
            for i in range(4):
                yy = int(16 * k + math.sin(self.t * 6 + i) * 2 * k)
                pygame.draw.circle(gs, (236, 236, 250, 255), (int((2 + i * 4) * k), min(int(18 * k), yy)), int(2.2 * k))
            pygame.draw.ellipse(gs, (20, 20, 30, 255), (int(4 * k), int(5 * k), int(3 * k), int(4 * k)))
            pygame.draw.ellipse(gs, (20, 20, 30, 255), (int(9 * k), int(5 * k), int(3 * k), int(4 * k)))
            pygame.draw.ellipse(gs, (20, 20, 30, 255), (int(6 * k), int(10 * k), int(4 * k), int(4 * k if g['boo'] else 2 * k)))
            gs.set_alpha(int(200 * g['a']))
            surf.blit(gs, (gx, gy))
            if g['boo'] > 0:
                tiny_text(surf, gx + int(16 * k), gy - 2, 'BOO!', (255, 255, 255))
        # spider on its thread
        sx = int(w * 0.93)
        sy = int(self.spider_y + math.sin(self.t * 1.5) * 2)
        pygame.draw.line(surf, (120, 110, 130), (sx, 0), (sx, sy))
        pygame.draw.circle(surf, (10, 6, 12), (sx, sy + int(2 * k)), max(2, int(3 * k)))
        for i in (-1, 1):
            for j in range(3):
                pygame.draw.line(surf, (10, 6, 12), (sx, sy + 2 * k), (sx + i * 5 * k, sy + (j - 0.5) * 2.5 * k))
        # fog drifting along the ground
        fw = self.fog.get_width()
        for i, sp in enumerate((6, 11)):
            off = int(self.t * sp) % fw
            y = int(h * (0.72 + i * 0.08))
            surf.blit(self.fog, (-off, y))
            surf.blit(self.fog, (fw - off, y))
        # jack-o'-lanterns in front
        for x, y, s, ph in self.pumpkins:
            fl = 0.7 + 0.3 * math.sin(self.t * 9 + ph) * math.sin(self.t * 4.3 + ph) + self.flicker * 0.5
            glow(surf, x, y - 4 * s, int(16 * s), (int(70 * fl), int(30 * fl), 0))
            pygame.draw.ellipse(surf, (230, 110, 20), (x - 9 * s, y - 12 * s, 18 * s, 12 * s))
            pygame.draw.ellipse(surf, (200, 86, 14), (x - 4 * s, y - 12 * s, 8 * s, 12 * s))
            surf.fill((70, 100, 30), (int(x - s), int(y - 15 * s), max(1, int(2 * s)), int(3 * s)))
            face = (int(255 * min(1, fl)), int(220 * min(1, fl)), int(80 * min(1, fl)))
            pygame.draw.polygon(surf, face, [(x - 6 * s, y - 8 * s), (x - 3 * s, y - 8 * s), (x - 4.5 * s, y - 10.5 * s)])
            pygame.draw.polygon(surf, face, [(x + 3 * s, y - 8 * s), (x + 6 * s, y - 8 * s), (x + 4.5 * s, y - 10.5 * s)])
            pygame.draw.polygon(surf, face, [(x - 6 * s, y - 5 * s), (x + 6 * s, y - 5 * s), (x + 4 * s, y - 3 * s),
                                             (x + 2 * s, y - 4 * s), (x, y - 2.6 * s), (x - 2 * s, y - 4 * s), (x - 4 * s, y - 3 * s)])


# ============================================================================ winter / northern lights
class Winter(Background):
    name = 'winter'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.k = k = h / 240
        rng = random.Random(77)
        self.lake = int(h * 0.74)
        self.stars = [(rng.uniform(0, w), rng.uniform(0, self.lake * 0.8), rng.random()) for _ in range(140)]
        # mountains + forest silhouette (SRCALPHA)
        self.land = pygame.Surface((w, self.lake), pygame.SRCALPHA)
        self.land.fill((0, 0, 0, 0))
        L = self.land
        for layer, (base, amp, col, snow) in enumerate(((0.52, 0.16, (40, 52, 80), (200, 214, 236)),
                                                         (0.62, 0.10, (24, 32, 52), (160, 176, 206)))):
            pts = [(0, self.lake)]
            peaks = []
            for x in range(0, w + 1):
                ridge = (1 - abs(math.sin(x / w * (5 + layer * 4) + layer * 2))) ** 1.6
                y = h * base - ridge * h * amp - math.sin(x / w * 17 + layer) * h * 0.008
                pts.append((x, int(y)))
                peaks.append(y)
            pts.append((w, self.lake))
            pygame.draw.polygon(L, col + (255,), pts)
            shade = _lerp(snow, col, 0.45)
            for i, (x, y) in enumerate(pts[1:-1]):                 # snow caps near the summits
                line = h * base - h * amp * (0.5 + 0.05 * math.sin(x * 0.09) + 0.03 * math.sin(x * 0.23 + layer))
                if y < line:
                    right = peaks[min(i + 3, len(peaks) - 1)] > peaks[max(i - 3, 0)]   # falling to the right: shady side
                    L.fill((shade if right else snow) + (255,), (x, y, 1, int((line - y)) + 1))
        for _ in range(70):
            x = rng.uniform(0, w)
            s = rng.uniform(5, 13) * k
            y = self.lake - rng.uniform(0, 4) * k
            c = (8, 14, 22, 255)
            for i in range(4):
                ww = s * (0.9 - i * 0.2)
                yy = y - i * s * 0.4
                pygame.draw.polygon(L, c, [(x - ww * 0.5, yy), (x + ww * 0.5, yy), (x, yy - s * 0.6)])
                L.fill((190, 206, 230, 255), (int(x - ww * 0.3), int(yy) - 1, max(1, int(ww * 0.25)), 1))
        cx = int(w * 0.22)                                          # cabin
        self.cabin = (cx, self.lake - int(2 * k))
        L.fill((40, 26, 20, 255), (cx, self.cabin[1] - int(10 * k), int(16 * k), int(10 * k)))
        pygame.draw.polygon(L, (230, 238, 250, 255), [(cx - 2 * k, self.cabin[1] - 10 * k), (cx + 18 * k, self.cabin[1] - 10 * k),
                                                      (cx + 8 * k, self.cabin[1] - 18 * k)])
        L.fill((40, 26, 20, 255), (int(cx + 12 * k), int(self.cabin[1] - 19 * k), int(3 * k), int(6 * k)))
        self.aw = max(64, w // 3)
        self.ah = max(24, int(self.lake * 0.55) // 3)
        self.snow = Dots(1200)
        self.smoke = []
        self.boost = 0.0
        self.seq = signals.letter_seq
        self.last_cmd = signals.cmd

    def _aurora(self):
        """curtains of light: bright lower hem, fading rays upwards, slowly folding"""
        aw, ah, t = self.aw, self.ah, self.t
        x = np.arange(aw, dtype=np.float32)[:, None]
        y = np.arange(ah, dtype=np.float32)[None, :]
        hem = ah * (0.62 + 0.16 * np.sin(x / aw * 5.0 + t * 0.21) + 0.08 * np.sin(x / aw * 13 - t * 0.37))
        inten = (0.55 + 0.45 * np.sin(x / aw * 9 + t * 0.6) * np.sin(x / aw * 3.1 - t * 0.27)) ** 2
        rays = 0.6 + 0.4 * np.sin(x * 0.9 + t * 1.7 + np.sin(x * 0.13 + t) * 3)
        d = hem - y
        prof = np.where(d >= 0, np.exp(-d / (ah * 0.28)), np.exp(d / 1.2))
        a = prof * inten * rays * (0.8 + self.boost)
        g = np.clip(a * 230, 0, 255)
        r = np.clip(a * 60 + np.clip(-d / ah, 0, 1) * 0 + (1 - prof) * a * 160, 0, 255)
        b = np.clip(a * 120 + np.clip(d / ah, 0, 1) * a * 140, 0, 255)
        img = np.stack([r, g, b], -1).astype(np.uint8)
        s = pygame.Surface((aw, ah))
        pygame.surfarray.blit_array(s, img)
        return pygame.transform.smoothscale(s, (self.w, int(self.lake * 0.55)))

    def update(self, dt, energy):
        super().update(dt, energy)
        w, h = self.w, self.h
        new, self.seq = signals.take_letters(self.seq)
        if any(l[4] for l in new):
            self.boost = min(1.0, self.boost + 0.15)
        self.boost = max(0.0, self.boost - dt * 0.25) + energy * 0.01
        if signals.cmd is not self.last_cmd and signals.cmd:
            self.last_cmd = signals.cmd
            if signals.cmd[0] == 0:
                self.boost = 1.0
        n = np.random.poisson(25 * dt)
        if n:
            dpt = np.random.random(n).astype(np.float32)
            self.snow.add(np.random.uniform(0, w, n), np.random.uniform(-5, 0, n), np.random.uniform(-2, 2, n),
                          8 + 14 * dpt, np.full(n, 99.0), np.array([210, 220, 240], np.float32) * (0.5 + 0.5 * dpt[:, None]))
        S = self.snow
        m = S.n
        if m:
            S.vx[:m] = np.sin(self.t * 0.6 + S.y[:m] * 0.04) * 4
            S.life[:m] = np.where(S.y[:m] > h, 0, 99)
        S.step(dt)
        if random.random() < dt * 2:
            self.smoke.append([self.cabin[0] + 13 * self.k, self.cabin[1] - 19 * self.k, 1.2 * self.k, 1.0])
        for p in self.smoke:
            p[0] += 2 * dt
            p[1] -= 6 * dt
            p[2] += 1.4 * dt
            p[3] -= dt * 0.3
        self.smoke = [p for p in self.smoke if p[3] > 0][-40:]

    def draw(self, surf, first):
        w, h, lk, k = self.w, self.h, self.lake, self.k
        surf.blit(gradient(w, lk, (2, 4, 14), (14, 24, 50), self.cache, 'sky'), (0, 0))
        for x, y, tw in self.stars:
            v = int(130 + 100 * math.sin(self.t * 1.4 + tw * 40))
            surf.fill((v, v, min(255, v + 25)), (int(x), int(y), 1, 1))
        aur = self._aurora()
        surf.blit(aur, (0, int(lk * 0.05)), special_flags=ADD)
        surf.blit(self.land, (0, 0))
        cx, cy = self.cabin
        f = 0.85 + 0.15 * math.sin(self.t * 5)
        surf.fill((int(255 * f), int(190 * f), int(90 * f)), (int(cx + 3 * k), int(cy - 7 * k), int(4 * k), int(4 * k)))
        glow(surf, cx + 5 * k, cy - 5 * k, int(10 * k), (50, 30, 10))
        for x, y, r, life in self.smoke:
            v = int(40 * life)
            glow(surf, x, y, max(2, int(r * 1.6)), (v, v, v + 10))
        # frozen lake mirrors sky, aurora and land
        depth = h - lk
        surf.fill((10, 16, 30), (0, lk, w, depth))
        src = surf.subsurface((0, max(0, lk - depth), w, min(depth, lk))).copy()
        src = pygame.transform.flip(src, False, True)
        src.fill((150, 160, 190), special_flags=MULT)
        surf.blit(src, (0, lk))
        for i in range(14):                          # ice cracks / glints
            x = (i * 97) % w
            y = lk + 3 + (i * 37) % max(1, depth - 4)
            surf.fill((50, 60, 80), (x, y, int(10 * k), 1), special_flags=ADD)
        surf.fill((60, 80, 110), (0, lk, w, 1), special_flags=ADD)
        self.snow.draw(surf, fade_pow=0)


SEASONS = {c.name: c for c in (Fireworks, Christmas, Halloween, Winter)}
