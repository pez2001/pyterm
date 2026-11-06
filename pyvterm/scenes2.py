"""More living scenes:

  aquarium      fish tank: curious fish follow your cursor, typed letters sink to the sand,
                bubbles, caustics, a turtle on success, murky water on failure, fish sleep when idle
  spacestation  cockpit window: planets drift by, every typed letter fires a laser at the
                asteroids, warp speed from output, red alert + hull shake on failure
  garden        every typed letter is a seed that grows into a flower; bees and butterflies
                by day, fireflies at night (real clock)
  pinball       a ball bounces through your text and lights up the letters it hits,
                bumpers, flippers on Enter, score
  c64load       endless tape loading screen: flickering raster stripes, a picture loading
                line by line, ?LOAD ERROR when a command fails
  beach         sunset beach on your clock: waves roll in, crabs carry your letters around,
                seagulls, palm, lighthouse at night, Enter sends a big wave

All react through pyvterm.signals (letters, typing, Enter, command results, energy).
"""
from __future__ import annotations

import math
import random
import time

import numpy as np
import pygame

from . import signals
from .backgrounds import Background
from .scenes import daylight, glow, gradient, sky_colors, sprite
from .weather import _lerp, moon_phase, tiny_text

ADD = pygame.BLEND_RGB_ADD


def _ch(c):
    """a char the tiny 3x5 font can draw"""
    c = c.upper()
    from .weather import _F
    return c if c in _F else random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')


def _letter(surf, x, y, c, col):
    tiny_text(surf, int(x) - 1, int(y) - 2, _ch(c), col)


# ============================================================================ aquarium
FISH = [
    (["..oo..", ".ooooo", "oooEoo", ".ooooo", "..oo.."], {'o': (255, 140, 40), 'E': (20, 20, 20)}),          # goldfish
    ([".bbb.", "bwbEb", ".bbb."], {'b': (60, 170, 255), 'w': (255, 255, 255), 'E': (10, 10, 10)}),              # neon
    (["..y...", ".yyyy.", "yyyyEy", ".yyyy.", "..y..."], {'y': (255, 230, 60), 'E': (10, 10, 10)}),             # yellow tang
    ([".pp..", "ppppE", ".pp.."], {'p': (255, 90, 180), 'E': (10, 10, 10)}),                                     # tiny pink
    (["...s....", ".ssssss.", "ssswsssE", ".ssssss.", "...s...."], {'s': (180, 190, 210), 'w': (255, 255, 255), 'E': (10, 10, 10)}),
]


class Aquarium(Background):
    name = 'aquarium'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.sand_y = int(h * 0.86)
        rng = random.Random(4)
        self.sand = pygame.Surface((w, h - self.sand_y))
        g = np.random.default_rng(2).random((w, h - self.sand_y))
        base = np.array([200, 170, 110], np.float32)
        img = base[None, None] * (0.8 + 0.3 * g[..., None])
        pygame.surfarray.blit_array(self.sand, np.clip(img, 0, 255).astype(np.uint8))
        for _ in range(w // 8):
            self.sand.fill(rng.choice([(150, 140, 130), (230, 220, 200), (120, 110, 100)]),
                           (rng.randrange(w), rng.randrange(max(1, h - self.sand_y)), 2, 1))
        cn = np.random.default_rng(7).random((64, 64)).astype(np.float32)
        for _ in range(3):
            cn = (cn + np.roll(cn, 1, 0) + np.roll(cn, 1, 1) + np.roll(cn, -1, 0) + np.roll(cn, -1, 1)) / 5
        cn = (cn - cn.min()) / (cn.max() - cn.min() + 1e-6)
        lines = np.clip(1 - np.abs(cn - 0.5) * 9, 0, 1) ** 2      # caustic web
        ca = (lines * 34).astype(np.uint8)
        cs = pygame.Surface((64, 64))
        pygame.surfarray.blit_array(cs, np.stack([ca // 2, ca, ca], -1))
        self.caustic = pygame.transform.smoothscale(cs, (max(64, w // 2), max(64, w // 2)))
        self.plants = [(rng.uniform(0, w), rng.randint(int(h * 0.12), int(h * 0.35)), rng.choice([(40, 160, 70), (70, 190, 60), (30, 130, 90)]),
                        rng.random() * 6) for _ in range(9)]
        self.castle_x = int(w * 0.68)
        self.diver_x = int(w * 0.22)
        self.fish = []
        for i in range(7):
            rows, pal = FISH[i % len(FISH)]
            img = sprite(rows, pal)
            fk = 2 if h >= 200 else 1
            if fk > 1:
                img = pygame.transform.scale(img, (img.get_width() * fk, img.get_height() * fk))
            self.fish.append({'img': img, 'flip': pygame.transform.flip(img, True, False), 'x': rng.uniform(0, w),
                              'y': rng.uniform(h * 0.15, self.sand_y - 10), 'vx': rng.choice((-1, 1)) * rng.uniform(8, 18),
                              'vy': 0.0, 'tx': None, 'ty': None, 'ph': rng.random() * 6})
        self.bubbles = []
        self.sinking = []          # [char, x, y, vy, rot]
        self.piled = []            # [char, x, y, age, col]
        self.seq = signals.letter_seq
        self.last_enter = signals.enter
        self.last_cmd = signals.cmd
        self.murk = 0.0
        self.turtle = None
        self.idle = 0.0

    def update(self, dt, energy):
        super().update(dt, energy)
        w, h = self.w, self.h
        new, self.seq = signals.take_letters(self.seq)
        for _, c, x, y, typed in new[-12:]:
            if typed or random.random() < 0.06:          # your letters (and the odd one from output)
                self.sinking.append([c, x, y, 10.0, random.uniform(-1, 1)])
        typing = signals.recent(signals.typing, 1.5)
        self.idle = 0.0 if (typing or new) else self.idle + dt
        if signals.enter != self.last_enter:
            self.last_enter = signals.enter
            for f in self.fish:                       # Enter: the school scatters
                a = random.uniform(0, math.tau)
                f['vx'], f['vy'] = math.cos(a) * 60, math.sin(a) * 40
        if signals.cmd is not self.last_cmd and signals.cmd:
            self.last_cmd = signals.cmd
            if signals.cmd[0]:
                self.murk = 1.0
            elif signals.cmd[1] >= 2 and self.turtle is None:
                self.turtle = [-30.0, random.uniform(h * 0.25, h * 0.6)]
        self.murk = max(0.0, self.murk - dt * 0.4)
        sleepy = self.idle > 60
        cx, cy = signals.cursor_x, signals.cursor_y
        for f in self.fish:
            sp = 0.3 if sleepy else 1.0
            if typing and cx is not None and not sleepy:
                tx, ty = cx + math.sin(self.t + f['ph']) * 25, (cy or h / 2) + 14 + math.cos(self.t * 1.3 + f['ph']) * 8
                f['vx'] += (max(-30, min(30, tx - f['x'])) - f['vx'] * 0.3) * dt * 2
                f['vy'] += (max(-20, min(20, ty - f['y'])) - f['vy'] * 0.5) * dt * 2
            else:
                if random.random() < dt * 0.3:
                    f['vx'] = random.choice((-1, 1)) * random.uniform(6, 16)
                f['vy'] += (math.sin(self.t * 0.7 + f['ph']) * 4 - f['vy']) * dt
            f['x'] += f['vx'] * dt * sp
            f['y'] += f['vy'] * dt * sp
            if f['x'] < -10 or f['x'] > w + 10:
                f['vx'] = -f['vx']
                f['x'] = max(-10, min(w + 10, f['x']))
            f['y'] = max(h * 0.08, min(self.sand_y - 8, f['y']))
            f['vx'] *= 1 - dt * 0.2
            if abs(f['vx']) < 3:
                f['vx'] = math.copysign(5, f['vx'] or 1)
        if random.random() < dt * (6 + energy * 10):
            self.bubbles.append([self.diver_x + 4 + random.uniform(-1, 1), self.sand_y - 16, random.uniform(1, 2.2)])
        if random.random() < dt * 1.5:
            self.bubbles.append([self.castle_x + random.uniform(0, 20), self.sand_y - 22, 1.0])
        for b in self.bubbles:
            b[1] -= (14 + b[2] * 6) * dt
            b[0] += math.sin(self.t * 3 + b[1] * 0.1) * 6 * dt
        self.bubbles = [b for b in self.bubbles if b[1] > 0][-160:]
        for s in self.sinking:
            s[3] = min(28.0, s[3] + 10 * dt)
            s[2] += s[3] * dt
            s[1] += math.sin(self.t * 2 + s[2] * 0.1) * 5 * dt
            if s[2] >= self.sand_y + random.uniform(1, 6):
                self.piled.append([s[0], s[1], s[2], 0.0, random.choice([(255, 230, 120), (180, 230, 255), (255, 180, 200), (200, 255, 190)])])
                s[2] = -1e9
        self.sinking = [s for s in self.sinking if s[2] > -1e8]
        for p in self.piled:
            p[3] += dt
        self.piled = [p for p in self.piled if p[3] < 90][-160:]
        if self.turtle:
            self.turtle[0] += 14 * dt
            if self.turtle[0] > w + 30:
                self.turtle = None

    def draw(self, surf, first):
        w, h, sy = self.w, self.h, self.sand_y
        dim = 0.55 if self.idle > 60 else 1.0
        top = tuple(int(c * dim) for c in (20, 110, 170))
        bot = tuple(int(c * dim) for c in (6, 40, 80))
        surf.blit(gradient(w, h, top, bot, self.cache, 'water'), (0, 0))
        # light rays from the surface
        rays = pygame.Surface((w, sy))
        rays.fill((0, 0, 0))
        for i in range(5):
            x = (i * w / 4 + math.sin(self.t * 0.2 + i) * w * 0.05) % (w + 40) - 20
            pygame.draw.polygon(rays, (int(10 * dim), int(20 * dim), int(24 * dim)),
                                [(x, 0), (x + w * 0.05, 0), (x + w * 0.12, sy), (x + w * 0.02, sy)])
        surf.blit(rays, (0, 0), special_flags=ADD)
        surf.blit(self.sand, (0, sy))
        # caustics shimmer over everything
        cw = self.caustic.get_width()
        ox = int(self.t * 6) % cw
        oy = int(self.t * 3) % cw
        for xx in range(-ox, w, cw):
            for yy in range(-oy, h, cw):
                surf.blit(self.caustic, (xx, yy), special_flags=ADD)
        # plants
        for x, ph, col, sd in self.plants:
            pts = []
            for k in range(0, ph, 3):
                pts.append((x + math.sin(self.t * 1.2 + sd + k * 0.06) * k * 0.12, sy + 2 - k))
            if len(pts) > 1:
                pygame.draw.lines(surf, col, False, pts, 3)
                for i in range(2, len(pts), 3):
                    px, py = pts[i]
                    pygame.draw.line(surf, _lerp(col, (200, 255, 150), 0.3), (px, py), (px + (5 if i % 2 else -5), py - 3), 2)
        # castle
        cx = self.castle_x
        stone = (150, 140, 150)
        surf.fill(stone, (cx, sy - 20, 26, 22))
        surf.fill(stone, (cx - 4, sy - 30, 8, 32))
        surf.fill(stone, (cx + 22, sy - 30, 8, 32))
        for tx in (cx - 4, cx + 22):
            for k in range(0, 8, 3):
                surf.fill(stone, (tx + k, sy - 33, 2, 3))
        surf.fill((30, 30, 50), (cx + 9, sy - 10, 8, 12))
        surf.fill((30, 30, 50), (cx - 1, sy - 26, 2, 4))
        surf.fill((230, 60, 60), (cx + 26, sy - 40, 5, 3))
        surf.fill((60, 60, 60), (cx + 25, sy - 40, 1, 10))
        # diver
        dx = self.diver_x
        surf.fill((240, 200, 40), (dx, sy - 12, 6, 6))
        surf.fill((150, 220, 255), (dx + 1, sy - 11, 3, 3))
        surf.fill((60, 60, 90), (dx, sy - 6, 6, 6))
        surf.fill((90, 90, 110), (dx - 3, sy - 10, 3, 7))
        # piled + sinking letters
        for c, x, y, age, col in self.piled:
            k = 1 - max(0.0, (age - 70) / 20)
            _letter(surf, x, y, c, tuple(int(v * k) for v in col))
        for c, x, y, v, r in self.sinking:
            _letter(surf, x, y, c, (230, 245, 255))
        # turtle
        if self.turtle:
            tx, ty = self.turtle
            sw = int(self.t * 4) % 2
            surf.fill((60, 140, 70), (int(tx), int(ty), 16, 7))
            surf.fill((110, 170, 80), (int(tx) + 2, int(ty) - 2, 12, 3))
            surf.fill((140, 190, 110), (int(tx) + 16, int(ty) + 1, 5, 4))
            surf.fill((10, 10, 10), (int(tx) + 19, int(ty) + 2, 1, 1))
            surf.fill((110, 170, 90), (int(tx) + 2 - sw, int(ty) + 7, 4, 2))
            surf.fill((110, 170, 90), (int(tx) + 11 + sw, int(ty) + 7, 4, 2))
        # fish
        for f in self.fish:
            img = f['img'] if f['vx'] >= 0 else f['flip']
            surf.blit(img, (int(f['x']), int(f['y'] + math.sin(self.t * 3 + f['ph']) * 0.8)))
            if self.idle > 60 and int(self.t + f['ph']) % 5 == 0:
                tiny_text(surf, int(f['x']) + 6, int(f['y']) - 7, 'Z', (200, 220, 255))
        for x, y, r in self.bubbles:
            pygame.draw.circle(surf, (170, 220, 255), (int(x), int(y)), int(r), 1)
        if self.murk > 0.01:
            m = pygame.Surface((w, h))
            m.fill((int(60 * self.murk), int(50 * self.murk), int(20 * self.murk)))
            surf.blit(m, (0, 0), special_flags=ADD)
        surf.fill((140, 210, 255), (0, 0, w, 1))


# ============================================================================ space station
class SpaceStation(Background):
    name = 'spacestation'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        rng = random.Random(5)
        self.stars = np.array([[rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(0.1, 1)] for _ in range(260)], np.float32)
        self.asteroids = []
        self.shots = []
        self.booms = []
        self.planet = None
        self.next_planet = 1.0
        self.seq = signals.letter_seq
        self.last_cmd = signals.cmd
        self.alert = 0.0
        self.warp = 0.0
        self.kills = 0
        self.hull = 100

    def _new_planet(self):
        w, h = self.w, self.h
        r = random.uniform(h * 0.12, h * 0.35)
        col = random.choice([(200, 120, 70), (80, 140, 220), (170, 90, 200), (90, 190, 140), (220, 200, 150)])
        s = pygame.Surface((int(r * 2.8), int(r * 2.2)), pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        cx, cy = s.get_width() // 2, s.get_height() // 2
        for yy in range(-int(r), int(r)):
            hw = int(math.sqrt(max(0, r * r - yy * yy)))
            band = 0.85 + 0.15 * math.sin(yy / r * 9)
            for xx in range(-hw, hw, 2):
                light = max(0.15, 1 - ((xx + r * 0.4) ** 2 + (yy + r * 0.4) ** 2) / (r * r * 2.2))
                c = tuple(int(min(255, v * light * band)) for v in col)
                s.fill(c + (255,), (cx + xx, cy + yy, 2, 1))
        if random.random() < 0.5:
            pygame.draw.ellipse(s, (230, 220, 190, 160), (cx - r * 1.35, cy - r * 0.25, r * 2.7, r * 0.5), 2)
        self.planet = [w + s.get_width() / 2, random.uniform(h * 0.2, h * 0.6), s]

    def update(self, dt, energy):
        super().update(dt, energy)
        w, h = self.w, self.h
        self.warp += ((0.15 + energy * 1.2) - self.warp) * min(1, dt * 2)
        z = self.stars[:, 2]
        z -= dt * (0.08 + self.warp)
        dead = z <= 0.05
        z[dead] = 1.0
        self.stars[dead, :2] = np.random.uniform(-1, 1, (int(dead.sum()), 2))
        self.next_planet -= dt
        if self.planet is None and self.next_planet <= 0:
            self._new_planet()
        if self.planet:
            self.planet[0] -= dt * (4 + self.warp * 10)
            if self.planet[0] < -self.planet[2].get_width():
                self.planet = None
                self.next_planet = random.uniform(10, 25)
        if random.random() < dt * 0.8 and len(self.asteroids) < 8:
            r = random.uniform(3, 9)
            pts = [(math.cos(a) * r * random.uniform(0.7, 1.1), math.sin(a) * r * random.uniform(0.7, 1.1))
                   for a in np.linspace(0, math.tau, 9)[:-1]]
            self.asteroids.append({'x': w + 10, 'y': random.uniform(h * 0.08, h * 0.65), 'vx': -random.uniform(10, 30),
                                   'vy': random.uniform(-4, 4), 'r': r, 'pts': pts, 'rot': 0.0, 'vr': random.uniform(-1, 1)})
        new, self.seq = signals.take_letters(self.seq)
        for l in [l for l in new if l[4]][-6:]:
            if self.asteroids:
                tgt = min(self.asteroids, key=lambda a: a['x'])
                self.shots.append([w / 2 + random.choice((-w * 0.18, w * 0.18)), h * 0.95, tgt, 0.0])
        for s in self.shots:
            s[3] += dt * 4
        for s in [s for s in self.shots if s[3] >= 1]:
            a = s[2]
            if a in self.asteroids:
                self.asteroids.remove(a)
                self.kills += 1
                for _ in range(16):
                    ang = random.uniform(0, math.tau)
                    sp = random.uniform(10, 60)
                    self.booms.append([a['x'], a['y'], math.cos(ang) * sp, math.sin(ang) * sp, random.uniform(0.3, 0.8)])
        self.shots = [s for s in self.shots if s[3] < 1]
        for a in self.asteroids:
            a['x'] += a['vx'] * dt * (1 + self.warp)
            a['y'] += a['vy'] * dt
            a['rot'] += a['vr'] * dt
        self.asteroids = [a for a in self.asteroids if a['x'] > -20]
        for b in self.booms:
            b[0] += b[2] * dt
            b[1] += b[3] * dt
            b[4] -= dt
        self.booms = [b for b in self.booms if b[4] > 0]
        if signals.cmd is not self.last_cmd and signals.cmd:
            self.last_cmd = signals.cmd
            if signals.cmd[0]:
                self.alert = 2.5
                self.hull = max(5, self.hull - random.randint(3, 9))
                signals.shake = 0.5
        self.alert = max(0.0, self.alert - dt)
        if self.alert <= 0 and random.random() < dt * 0.1:
            self.hull = min(100, self.hull + 1)

    def draw(self, surf, first):
        w, h = self.w, self.h
        surf.fill((2, 2, 10))
        cx, cy = w / 2, h * 0.42
        st = self.stars
        sx = cx + st[:, 0] / st[:, 2] * w * 0.5
        sy = cy + st[:, 1] / st[:, 2] * h * 0.5
        streak = min(1.0, self.warp)
        for x, y, z, X, Y in zip(st[:, 0], st[:, 1], st[:, 2], sx, sy):
            if 0 <= X < w and 0 <= Y < h:
                v = max(0, min(255, int(255 * min(1, (1.1 - z)))))
                if streak > 0.3:
                    z2 = z + 0.04 * streak
                    X2, Y2 = float(cx + x / z2 * w * 0.5), float(cy + y / z2 * h * 0.5)
                    pygame.draw.line(surf, (v // 2, v // 2, v), (X2, Y2), (float(X), float(Y)))
                surf.fill((v, v, v), (int(X), int(Y), 1, 1))
        if self.planet:
            px, py, ps = self.planet
            surf.blit(ps, (int(px - ps.get_width() / 2), int(py - ps.get_height() / 2)))
        for a in self.asteroids:
            ca, sa = math.cos(a['rot']), math.sin(a['rot'])
            pts = [(a['x'] + x * ca - y * sa, a['y'] + x * sa + y * ca) for x, y in a['pts']]
            pygame.draw.polygon(surf, (110, 95, 85), pts)
            pygame.draw.polygon(surf, (160, 145, 130), pts, 1)
        for x0, y0, a, k in self.shots:
            tx, ty = a['x'], a['y']
            x, y = x0 + (tx - x0) * k, y0 + (ty - y0) * k
            x1, y1 = x0 + (tx - x0) * max(0, k - 0.15), y0 + (ty - y0) * max(0, k - 0.15)
            pygame.draw.line(surf, (255, 60, 80), (x1, y1), (x, y), 2)
            pygame.draw.line(surf, (255, 220, 220), (x1, y1), (x, y), 1)
        for x, y, vx, vy, life in self.booms:
            c = _lerp((255, 240, 180), (255, 80, 20), 1 - min(1, life * 1.5))
            surf.fill(c, (int(x), int(y), 2, 2))
        # cockpit frame + HUD
        frame = (28, 30, 40)
        pygame.draw.polygon(surf, frame, [(0, 0), (w * 0.08, 0), (0, h * 0.3)])
        pygame.draw.polygon(surf, frame, [(w, 0), (w * 0.92, 0), (w, h * 0.3)])
        pygame.draw.polygon(surf, frame, [(0, h), (0, h * 0.78), (w * 0.15, h * 0.9), (w * 0.85, h * 0.9), (w, h * 0.78), (w, h)])
        hud = (60, 255, 160) if self.alert <= 0 else (255, 70, 60)
        k = 10
        for (x, y, dx, dy) in ((w * 0.1, h * 0.06, 1, 1), (w * 0.9, h * 0.06, -1, 1), (w * 0.1, h * 0.84, 1, -1), (w * 0.9, h * 0.84, -1, -1)):
            pygame.draw.line(surf, hud, (x, y), (x + dx * k, y))
            pygame.draw.line(surf, hud, (x, y), (x, y + dy * k))
        pygame.draw.circle(surf, tuple(c // 2 for c in hud), (int(cx), int(cy)), 9, 1)
        surf.fill(hud, (int(cx) - 14, int(cy), 6, 1))
        surf.fill(hud, (int(cx) + 9, int(cy), 6, 1))
        tm = time.strftime('%H:%M')
        tiny_text(surf, int(w * 0.17), int(h * 0.92), 'SPD %03d' % int(self.warp * 300), hud)
        tiny_text(surf, int(w * 0.37), int(h * 0.92), 'HULL %d%%' % self.hull, hud)
        tiny_text(surf, int(w * 0.57), int(h * 0.92), 'HITS %d' % self.kills, hud)
        tiny_text(surf, int(w * 0.75), int(h * 0.92), tm, hud)
        if self.alert > 0:
            if int(self.t * 4) % 2:
                tiny_text(surf, int(cx) - 10, int(h * 0.12), 'ALERT', (255, 60, 60))
            red = pygame.Surface((w, h))
            red.fill((int(70 * min(1, self.alert)), 0, 0))
            surf.blit(red, (0, 0), special_flags=ADD)
        # panel lights
        for i in range(8):
            on = (int(self.t * 3) + i * 3) % 5 != 0
            surf.fill(((255, 80, 60), (60, 255, 120), (255, 220, 60), (80, 160, 255))[i % 4] if on else (40, 40, 50),
                      (int(w * 0.3 + i * w * 0.05), int(h * 0.965), 3, 2))


# ============================================================================ garden
FLOWER_COLS = [(255, 90, 120), (255, 200, 60), (180, 110, 255), (255, 255, 255), (255, 140, 40), (110, 170, 255)]


class Garden(Background):
    name = 'garden'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.gy = int(h * 0.82)
        rng = random.Random(8)
        self.grass = [(rng.uniform(0, w), rng.randint(2, 6), rng.random() * 6) for _ in range(w // 2)]
        self.plants = []
        self.seeds = []
        for _ in range(10):               # a few flowers to start with
            self._plant(rng.uniform(0, w), grown=rng.uniform(0.6, 1.0))
        self.bees = [[rng.uniform(0, w), rng.uniform(h * 0.4, self.gy - 20), None, rng.random() * 6] for _ in range(3)]
        self.butterfly = [rng.uniform(0, w), h * 0.4, rng.random() * 6, rng.choice(FLOWER_COLS)]
        self.flies = [[rng.uniform(0, w), rng.uniform(h * 0.3, self.gy), rng.random() * 6] for _ in range(14)]
        self.seq = signals.letter_seq
        self.clouds = [[rng.uniform(0, w), rng.uniform(4, h * 0.25), rng.uniform(0.6, 1.3)] for _ in range(4)]

    def _plant(self, x, grown=0.0):
        self.plants.append({'x': x, 'g': grown, 'h': random.randint(int(self.h * 0.06), int(self.h * 0.2)),
                            'col': random.choice(FLOWER_COLS), 'kind': random.choice(('daisy', 'tulip', 'sun', 'bell')),
                            'age': 0.0, 'ph': random.random() * 6})
        self.plants = self.plants[-70:]

    def update(self, dt, energy):
        super().update(dt, energy)
        w, h = self.w, self.h
        new, self.seq = signals.take_letters(self.seq)
        for _, c, x, y, typed in new[-8:]:
            if typed or random.random() < 0.04:
                self.seeds.append([x, y, 0.0])
        for s in self.seeds:
            s[2] += 40 * dt
            s[1] += s[2] * dt
            s[0] += math.sin(self.t * 3 + s[1] * 0.05) * 6 * dt
            if s[1] >= self.gy:
                self._plant(s[0])
                s[1] = 1e9
        self.seeds = [s for s in self.seeds if s[1] < 1e8]
        for p in self.plants:
            p['g'] = min(1.0, p['g'] + dt / 25 * (1 + energy))
            p['age'] += dt
        open_ = [p for p in self.plants if p['g'] >= 1]
        for b in self.bees:
            if b[2] is None or b[2] not in self.plants or random.random() < dt * 0.15:
                b[2] = random.choice(open_) if open_ else None
            if b[2]:
                tx, ty = b[2]['x'], self.gy - b[2]['h'] - 4
                b[0] += (tx - b[0]) * min(1, dt * 0.9) + math.sin(self.t * 9 + b[3]) * 10 * dt
                b[1] += (ty - b[1]) * min(1, dt * 0.9) + math.cos(self.t * 7 + b[3]) * 10 * dt
        bf = self.butterfly
        bf[0] = (bf[0] + 12 * dt) % (w + 20)
        bf[1] = h * 0.45 + math.sin(self.t * 0.8 + bf[2]) * h * 0.15
        for f in self.flies:
            f[0] += math.sin(self.t * 0.7 + f[2]) * 6 * dt
            f[1] += math.cos(self.t * 0.9 + f[2] * 2) * 4 * dt
        for c in self.clouds:
            c[0] = (c[0] + 3 * c[2] * dt) % (w + 60)

    def draw(self, surf, first):
        w, h, gy = self.w, self.h, self.gy
        day, hour, sr, ss = daylight()
        top, bot, dusk = sky_colors(day)
        surf.blit(gradient(w, h, top, bot, self.cache, 'sky'), (0, 0))
        if day > 0.3:
            f = (hour - sr) / max(0.1, ss - sr)
            pygame.draw.circle(surf, _lerp((255, 240, 170), (255, 150, 70), dusk),
                               (int(w * (0.1 + 0.8 * f)), int(gy - math.sin(max(0, min(1, f)) * math.pi) * gy * 0.8)), max(4, h // 24))
        cl = _lerp((60, 60, 80), (255, 255, 255), day)
        for x, y, s in self.clouds:
            for i in range(4):
                pygame.draw.circle(surf, cl, (int(x - 30 + i * 7 * s), int(y + (i % 2) * 2)), int(5 * s + (i % 2) * 2))
        hill = _lerp((15, 30, 20), (110, 180, 90), day)
        pygame.draw.ellipse(surf, _lerp(hill, bot, 0.3), (-w * 0.2, gy - h * 0.18, w * 0.8, h * 0.4))
        pygame.draw.ellipse(surf, _lerp(hill, bot, 0.15), (w * 0.4, gy - h * 0.14, w * 0.9, h * 0.35))
        surf.fill(_lerp((30, 20, 10), (110, 75, 45), day), (0, gy, w, h - gy))
        surf.fill(_lerp((15, 40, 20), (80, 160, 60), day), (0, gy, w, 2))
        gcol = _lerp((15, 45, 20), (70, 170, 60), day)
        for x, gh, ph in self.grass:
            sw = math.sin(self.t * 1.5 + ph + x * 0.02) * 1.2
            pygame.draw.line(surf, gcol, (x, gy + 1), (x + sw, gy + 1 - gh))
        night = day < 0.3
        for p in self.plants:
            g = p['g']
            stem_h = int(p['h'] * min(1, g * 1.3))
            x = p['x'] + math.sin(self.t * 1.2 + p['ph']) * stem_h * 0.03
            stem = _lerp((20, 50, 20), (60, 150, 60), day)
            if stem_h > 1:
                pygame.draw.line(surf, stem, (p['x'], gy), (x, gy - stem_h))
                if stem_h > 6:
                    surf.fill(stem, (int(p['x'] + 1), gy - stem_h // 2, 3, 1))
            if g < 0.75:
                surf.fill(_lerp(stem, (140, 220, 120), 0.4), (int(x) - 1, gy - stem_h - 1, 2, 2))
                continue
            k = min(1.0, (g - 0.75) * 4) * (0.75 if night else 1.0)
            col = _lerp((40, 40, 50), p['col'], k)
            fx, fy = int(x), gy - stem_h
            r = 1 + int(2 * k) if not night else 2
            if p['kind'] == 'daisy':
                for a in range(6):
                    ang = a * math.pi / 3
                    surf.fill(col, (fx + int(math.cos(ang) * r) - 1, fy + int(math.sin(ang) * r) - 1, 2, 2))
                surf.fill((255, 220, 60), (fx - 1, fy - 1, 2, 2))
            elif p['kind'] == 'tulip':
                surf.fill(col, (fx - 2, fy - 3, 5, 4))
                surf.fill(col, (fx - 2, fy - 5, 1, 2))
                surf.fill(col, (fx + 2, fy - 5, 1, 2))
                surf.fill(col, (fx, fy - 5, 1, 2))
            elif p['kind'] == 'sun':
                pygame.draw.circle(surf, (255, 210, 40) if not night else (120, 100, 30), (fx, fy), r + 2)
                pygame.draw.circle(surf, (110, 70, 30), (fx, fy), max(1, r))
            else:
                for i in range(3):
                    surf.fill(col, (fx - 3 + i * 3, fy + (i % 2), 2, 3))
        for s in self.seeds:
            surf.fill((160, 120, 60), (int(s[0]), int(s[1]), 1, 2))
        if not night:
            for b in self.bees:
                wing = int(self.t * 20) % 2
                surf.fill((250, 210, 40), (int(b[0]), int(b[1]), 3, 2))
                surf.fill((30, 30, 30), (int(b[0]) + 1, int(b[1]), 1, 2))
                surf.fill((230, 240, 255), (int(b[0]) + 1, int(b[1]) - 1 - wing, 1, 1))
            bf = self.butterfly
            flap = abs(math.sin(self.t * 10))
            wing = max(1, int(3 * flap))
            surf.fill(bf[3], (int(bf[0]) - wing, int(bf[1]) - 1, wing, 3))
            surf.fill(bf[3], (int(bf[0]) + 1, int(bf[1]) - 1, wing, 3))
            surf.fill((30, 30, 30), (int(bf[0]), int(bf[1]) - 1, 1, 3))
        else:
            for x, y, ph in self.flies:
                v = max(0.0, math.sin(self.t * 2 + ph * 3))
                if v > 0.2:
                    glow(surf, x, y, 4, (int(60 * v), int(80 * v), int(10 * v)))
                    surf.fill((int(200 * v), int(255 * v), int(80 * v)), (int(x), int(y), 1, 1))
            mx, my, r = int(w * 0.8), int(h * 0.15), max(3, h // 30)
            pygame.draw.circle(surf, (235, 232, 205), (mx, my), r)


# ============================================================================ pinball
class Pinball(Background):
    """the ball collides with the actual terminal text (wants_text)"""
    name = 'pinball'
    opaque = True
    wants_text = True

    def resize(self, w, h):
        super().resize(w, h)
        self.text_layers = []
        self.bumpers = [[w * 0.3, h * 0.25, max(6, h // 28), 0.0], [w * 0.55, h * 0.18, max(6, h // 28), 0.0],
                        [w * 0.75, h * 0.32, max(6, h // 28), 0.0], [w * 0.45, h * 0.42, max(5, h // 34), 0.0]]
        self.fy = h * 0.9
        # walls: top corner deflectors, plunger lane, inlane guides towards the flippers
        self.walls = [((w * 0.88, 2), (w * 0.98, h * 0.1)), ((w * 0.12, 2), (w * 0.02, h * 0.1)),
                      ((w * 0.93, h * 0.22), (w * 0.93, h)),
                      ((w * 0.02, h * 0.72), (w * 0.36, self.fy - 1)), ((w * 0.93, h * 0.72), (w * 0.64, self.fy - 1))]
        self.flip = [0.0, 0.0]          # 0 rest .. 1 up
        self.flip_t = [0.0, 0.0]
        self.score = 0
        self.balls = 3
        self.lit = []                   # [x, y, age]
        self.last_enter = signals.enter
        self.seq = signals.letter_seq
        self.text_mask = None
        self._serve()

    def _serve(self):
        self.bx, self.by = self.w * 0.955, self.h * 0.85
        self.vx, self.vy = 0.0, -random.uniform(300, 380)

    def _mask(self):
        """combined alpha of the text layers, 1/2 resolution, rebuilt each update"""
        m = np.zeros((self.w // 2 + 1, self.h // 2 + 1), bool)
        for ts, (px, py) in self.text_layers:
            try:
                a = pygame.surfarray.pixels_alpha(ts)
            except Exception:
                continue
            sub = a[::2, ::2] > 128
            del a
            x0, y0 = px // 2, py // 2
            x1, y1 = min(m.shape[0], x0 + sub.shape[0]), min(m.shape[1], y0 + sub.shape[1])
            if x1 > x0 and y1 > y0:
                m[x0:x1, y0:y1] |= sub[:x1 - x0, :y1 - y0]
        return m

    def text_at(self, x, y):
        m = self.text_mask
        if m is None:
            return False
        xi, yi = int(x) // 2, int(y) // 2
        return 0 <= xi < m.shape[0] and 0 <= yi < m.shape[1] and m[xi, yi]

    def flippers(self):
        w = self.w
        L = w * 0.12
        out = []
        for side in (0, 1):
            px = w * (0.36 if side == 0 else 0.64)
            a = (0.45 - self.flip[side] * 0.9) * (1 if side == 0 else -1)
            ex = px + math.cos(a) * L * (1 if side == 0 else -1)
            ey = self.fy + math.sin(abs(a)) * L * (1 if a > 0 else -1) if side == 0 else self.fy + math.sin(-a) * L
            out.append(((px, self.fy), (ex, ey)))
        return out

    def update(self, dt, energy):
        super().update(dt, energy)
        w, h = self.w, self.h
        self.text_mask = self._mask() if self.text_layers else None
        if signals.enter != self.last_enter:
            self.last_enter = signals.enter
            self.flip_t = [0.25, 0.25]
        new, self.seq = signals.take_letters(self.seq)
        self.score += 10 * len(new)
        near = self.by > self.fy - h * 0.12 and self.vy > 0
        if near and random.random() < 0.7:            # the machine plays along
            side = 0 if self.bx < w / 2 else 1
            self.flip_t[side] = max(self.flip_t[side], 0.18)
        for s in (0, 1):
            self.flip_t[s] -= dt
            tgt = 1.0 if self.flip_t[s] > 0 else 0.0
            self.flip[s] += (tgt - self.flip[s]) * min(1, dt * (30 if tgt else 10))
        steps = 4
        for _ in range(steps):
            d = dt / steps
            self.vy += 260 * d
            nx, ny = self.bx + self.vx * d, self.by + self.vy * d
            if nx < 3 or nx > w - 3:
                self.vx = -self.vx * 0.9
                nx = max(3, min(w - 3, nx))
            if ny < 3:
                self.vy = abs(self.vy) * 0.9
                ny = 3
            if self.text_at(nx, ny):                 # bounce off a letter
                hx = self.text_at(nx, self.by)
                hy = self.text_at(self.bx, ny)
                if hx or not hy:
                    self.vx = -self.vx * 0.85
                if hy or not hx:
                    self.vy = -self.vy * 0.85
                self.score += 25
                self.lit.append([nx, ny, 0.0])
                nx, ny = self.bx, self.by
            for (ax, ay), (bx2, by2) in self.walls:
                ex, ey = bx2 - ax, by2 - ay
                L2 = ex * ex + ey * ey
                t = max(0, min(1, ((nx - ax) * ex + (ny - ay) * ey) / (L2 or 1)))
                qx, qy = ax + ex * t, ay + ey * t
                dd = math.hypot(nx - qx, ny - qy)
                if dd < 3.5:
                    nxn, nyn = (nx - qx) / (dd or 1), (ny - qy) / (dd or 1)
                    vn = self.vx * nxn + self.vy * nyn
                    if vn < 0:
                        self.vx -= 1.85 * vn * nxn
                        self.vy -= 1.85 * vn * nyn
                    nx, ny = qx + nxn * 3.6, qy + nyn * 3.6
            for b in self.bumpers:
                dx, dy = nx - b[0], ny - b[1]
                dd = math.hypot(dx, dy)
                if dd < b[2] + 2:
                    nxn, nyn = dx / (dd or 1), dy / (dd or 1)
                    sp = max(180, math.hypot(self.vx, self.vy))
                    self.vx, self.vy = nxn * sp, nyn * sp
                    nx, ny = b[0] + nxn * (b[2] + 3), b[1] + nyn * (b[2] + 3)
                    b[3] = 0.3
                    self.score += 100
            for side, (p0, p1) in enumerate(self.flippers()):
                ax, ay = p0
                bx, by = p1
                ex, ey = bx - ax, by - ay
                L2 = ex * ex + ey * ey
                t = max(0, min(1, ((nx - ax) * ex + (ny - ay) * ey) / (L2 or 1)))
                qx, qy = ax + ex * t, ay + ey * t
                if math.hypot(nx - qx, ny - qy) < 3 and self.vy > -50:
                    kick = 1 if self.flip_t[side] > 0 else 0
                    self.vy = -(abs(self.vy) * 0.5 + kick * (250 + 150 * t))
                    self.vx += (t - 0.5) * 80 * (1 if side == 0 else -1) + (side - 0.5) * -60
                    ny = qy - 4
            self.bx, self.by = nx, ny
        sp = math.hypot(self.vx, self.vy)
        if sp > 520:
            self.vx, self.vy = self.vx * 520 / sp, self.vy * 520 / sp
        if self.by > h + 5:
            self.balls -= 1
            if self.balls <= 0:
                self.balls, self.score = 3, 0
            self._serve()
        for b in self.bumpers:
            b[3] = max(0.0, b[3] - dt)
        for l in self.lit:
            l[2] += dt
        self.lit = [l for l in self.lit if l[2] < 0.6][-40:]

    def draw(self, surf, first):
        w, h = self.w, self.h
        surf.fill((10, 6, 24))
        for i in range(0, w, 16):
            surf.fill((18, 10, 40), (i, 0, 1, h))
        pygame.draw.lines(surf, (70, 50, 140), False, [(w * 0.02, h), (w * 0.02, h * 0.1), (w * 0.12, 2), (w * 0.88, 2),
                                                       (w * 0.98, h * 0.1), (w * 0.98, h)], 2)
        for p0, p1 in self.walls:
            pygame.draw.line(surf, (110, 80, 200), p0, p1, 2)
        for i, x in enumerate((0.2, 0.35, 0.5, 0.65, 0.8)):
            on = (int(self.t * 3) + i) % 5 == 0
            pygame.draw.polygon(surf, (255, 200, 60) if on else (70, 50, 30),
                                [(w * x, h * 0.6), (w * x - 4, h * 0.6 + 6), (w * x + 4, h * 0.6 + 6)])
        for x, y, r, flash in self.bumpers:
            c = (255, 255, 200) if flash > 0 else (255, 60, 140)
            glow(surf, x, y, int(r * 2), (60, 10, 40) if not flash else (120, 100, 40))
            pygame.draw.circle(surf, c, (int(x), int(y)), int(r))
            pygame.draw.circle(surf, (40, 10, 30), (int(x), int(y)), int(r * 0.5))
        for l in self.lit:
            k = 1 - l[2] / 0.6
            glow(surf, l[0], l[1], 7, (int(120 * k), int(100 * k), int(20 * k)))
        for side, (p0, p1) in enumerate(self.flippers()):
            pygame.draw.line(surf, (255, 220, 80), p0, p1, 4)
            pygame.draw.circle(surf, (255, 240, 160), (int(p0[0]), int(p0[1])), 3)
        glow(surf, self.bx, self.by, 8, (60, 60, 70))
        pygame.draw.circle(surf, (230, 230, 240), (int(self.bx), int(self.by)), 3)
        surf.fill((255, 255, 255), (int(self.bx) - 1, int(self.by) - 2, 1, 1))
        tiny_text(surf, int(w * 0.7), int(h * 0.04), 'SCORE %07d' % self.score, (255, 220, 80))
        tiny_text(surf, int(w * 0.14), int(h * 0.04), 'BALL %d' % (4 - self.balls), (255, 120, 180))


# ============================================================================ C64 tape loading
C64 = [(0, 0, 0), (255, 255, 255), (136, 57, 50), (103, 182, 189), (139, 63, 150), (85, 160, 73), (64, 49, 141),
       (191, 206, 114), (139, 84, 41), (87, 66, 0), (184, 105, 98), (80, 80, 80), (120, 120, 120), (148, 224, 137),
       (120, 105, 196), (159, 159, 159)]


def _c64_picture(kind, W=160, H=100):
    """a small procedural loading-screen picture, C64 palette, wide pixels"""
    img = np.zeros((W, H), np.uint8)
    X, Y = np.meshgrid(np.arange(W), np.arange(H), indexing='ij')
    if kind == 0:   # sunset mountains + title
        img[:] = 6
        img[Y > 20] = 4
        img[Y > 38] = 10
        img[Y > 50] = 8
        sun = (X - 80) ** 2 + ((Y - 60) * 2) ** 2 < 26 ** 2
        img[sun & (Y < 62)] = 7
        img[sun & (Y < 62) & ((Y // 3) % 2 == 0) & (Y > 50)] = 8
        mount = Y > 62 - np.abs(np.sin(X / 13)) * 18 - np.abs(np.sin(X / 5.3)) * 4
        img[mount] = 9
        img[mount & (Y > 75)] = 11
        img[Y > 88] = 6
        img[(Y > 88) & ((X + Y) % 7 == 0)] = 14
    elif kind == 1:  # planet + spaceship
        img[:] = 0
        rng = np.random.default_rng(3)
        for _ in range(60):
            img[rng.integers(0, W), rng.integers(0, H)] = rng.choice([1, 15, 12])
        pl = (X - 110) ** 2 + ((Y - 60) * 1.0) ** 2 < 34 ** 2
        img[pl] = 14
        img[pl & ((X - 100) ** 2 + (Y - 50) ** 2 > 30 ** 2)] = 6
        img[pl & (np.sin(Y / 4 + X / 30) > 0.6)] = 3
        ring = np.abs(((X - 110) / 50) ** 2 + ((Y - 60) / 9) ** 2 - 1) < 0.08
        img[ring & ~(pl & (Y < 60))] = 7
        ship = (np.abs(Y - 35) < (X - 25) * 0.25) & (X > 25) & (X < 65)
        img[ship] = 15
        img[ship & (np.abs(Y - 35) < 2)] = 1
        img[(X > 18) & (X < 26) & (np.abs(Y - 35) < 3)] = 2
        img[(X > 12) & (X < 19) & (np.abs(Y - 35) < 1 + (X % 3))] = 7
    else:            # castle at night
        img[:] = 6
        img[Y > 70] = 5
        img[(Y > 70) & ((X * 3 + Y) % 11 == 0)] = 13
        moon = (X - 130) ** 2 + ((Y - 20) * 1.2) ** 2 < 10 ** 2
        img[moon] = 1
        wall = (X > 40) & (X < 120) & (Y > 40) & (Y <= 70)
        img[wall] = 12
        for tx in (35, 72, 110):
            img[(X > tx) & (X < tx + 14) & (Y > 22) & (Y <= 70)] = 11
            img[(X > tx) & (X < tx + 14) & (Y > 18) & (Y <= 22) & ((X - tx) % 4 < 2)] = 11
        img[wall & ((X // 6 + Y // 4) % 2 == 0) & (Y % 4 == 0)] = 15
        img[(X > 74) & (X < 84) & (Y > 55) & (Y <= 70)] = 0
        img[(X > 76) & (X < 80) & (Y > 30) & (Y < 36)] = 7
        img[(X > 39) & (X < 43) & (Y > 32) & (Y < 37)] = 7
    return img


class C64Load(Background):
    name = 'c64load'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.pic_i = 0
        self._new_picture()
        self.last_cmd = signals.cmd
        self.err = 0.0
        self.rng = random.Random(1)

    def _new_picture(self):
        W, H = 160, 100
        img = _c64_picture(self.pic_i % 3, W, H)
        rgb = np.array(C64, np.uint8)[img]                    # (W, H, 3)
        s = pygame.Surface((W, H))
        pygame.surfarray.blit_array(s, rgb)
        self.pic = s
        self.lines = 0.0            # loaded lines (C64 bitmap order: char rows interleaved)
        self.hold = 0.0
        self.loaded = pygame.Surface((W, H))
        self.loaded.fill(C64[6])
        self.shown = 0
        self.scaled = None
        self.order = [r * 8 + k for k in range(8) for r in range(H // 8 + 1) if r * 8 + k < H]
        self.pic_i += 1

    def update(self, dt, energy):
        super().update(dt, energy)
        if self.hold > 0:
            self.hold -= dt
            if self.hold <= 0:
                self._new_picture()
        else:
            self.lines += dt * (5 + energy * 25)
            if self.lines >= len(self.order):
                self.hold = 8.0
        if signals.cmd is not self.last_cmd and signals.cmd:
            self.last_cmd = signals.cmd
            if signals.cmd[0]:
                self.err = 3.0
        self.err = max(0.0, self.err - dt)

    def draw(self, surf, first):
        w, h = self.w, self.h
        loading = self.hold <= 0
        mode = self.p('stripes', 'calm')          # calm | authentic | off
        sw, sh = int(w * 0.8), int(h * 0.8)
        sx, sy = (w - sw) // 2, (h - sh) // 2
        if mode == 'off':
            surf.fill(C64[14], (0, 0, w, h))
        elif mode == 'authentic':
            # the real thing: new random raster bars every frame while data comes in
            rng = random.Random(int(self.t * 50))
            y = 0
            while y < h:
                hh = rng.randint(1, 4) if loading else rng.randint(6, 10)
                col = C64[rng.choice((2, 3, 4, 5, 6, 7, 8, 10, 13, 14))] if loading else C64[rng.choice((3, 2))]
                surf.fill(col, (0, y, w, hh))
                y += hh
        else:
            # calm: soft bands that drift slowly, a gentle nod to the loading stripes
            pal = [C64[i] for i in ((6, 14, 3, 14, 6, 4) if loading else (6, 14, 6, 14))]
            band = max(4, h // 18)
            off = (self.t * (14 if loading else 5)) % (band * len(pal))
            y = -int(off)
            i = 0
            while y < h:
                c = pal[i % len(pal)]
                surf.fill(tuple(int(v * 0.75) for v in c), (0, y, w, band))
                y += band
                i += 1
        # the screen
        pic = self.pic
        PW, PH = pic.get_size()
        done = min(int(self.lines), len(self.order))
        if done != self.shown or self.scaled is None or self.scaled.get_size() != (sw, sh):
            for i in range(self.shown, done):              # only the newly loaded lines
                r = self.order[i]
                self.loaded.blit(pic, (0, r), (0, r, PW, 1))
            self.shown = done
            self.scaled = pygame.transform.scale(self.loaded, (sw, sh))
        surf.blit(self.scaled, (sx, sy))
        if self.err > 0:
            tiny_text(surf, sx + 4, sy + 4, '?LOAD ERROR', C64[14] if int(self.t * 3) % 2 else C64[1])
            tiny_text(surf, sx + 4, sy + 10, 'READY.', C64[14])
        elif loading:
            pct = int(100 * done / max(1, len(self.order)))
            tiny_text(surf, sx + 4, sy + sh - 8, 'LOADING %d%%' % pct, C64[14])
        else:
            tiny_text(surf, sx + 4, sy + sh - 8, 'PRESS PLAY ON TAPE', C64[14])


# ============================================================================ beach
class Beach(Background):
    name = 'beach'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.hz = int(h * 0.55)          # horizon
        self.shore = int(h * 0.74)
        rng = random.Random(12)
        self.stars = [(rng.uniform(0, w), rng.uniform(0, self.hz * 0.9), rng.random()) for _ in range(80)]
        self.gulls = []
        self.crabs = [{'x': rng.uniform(w * 0.1, w * 0.9), 'v': rng.choice((-1, 1)) * 6, 'carry': None, 'ph': rng.random() * 6}
                      for _ in range(3)]
        self.letters = []                # on the sand: [char, x, y, vy, landed]
        self.wave = 0.0                  # extra swell height 0..1
        self.splash = []
        self.seq = signals.letter_seq
        self.last_enter = signals.enter
        self.palm_x = int(w * 0.12)
        self.clouds = [[rng.uniform(0, w), rng.uniform(4, self.hz * 0.5), rng.uniform(0.6, 1.4)] for _ in range(4)]

    def surf_line(self):
        """current water edge (y) on the sand"""
        base = self.shore + 4 + math.sin(self.t * 0.6) * 4
        return base + self.wave * (self.h - self.shore) * 0.7

    def update(self, dt, energy):
        super().update(dt, energy)
        w, h = self.w, self.h
        new, self.seq = signals.take_letters(self.seq)
        for _, c, x, y, typed in new[-8:]:
            if typed or random.random() < 0.05:
                self.letters.append([c, x, y, 0.0, False])
        self.letters = self.letters[-90:]
        sand_lo = self.surf_line() + 3
        for l in self.letters:
            if not l[4]:
                l[3] += 120 * dt
                l[2] += l[3] * dt
                ground = max(sand_lo, h * 0.8 + (hash(l[1]) % 10))
                if l[2] >= min(h - 4, ground):
                    l[2] = min(h - 4, ground)
                    l[4] = True
        if signals.enter != self.last_enter:
            self.last_enter = signals.enter
            self.wave = 1.0
            for _ in range(40):
                self.splash.append([random.uniform(0, w), self.shore + random.uniform(0, 20), random.uniform(-30, 30),
                                    random.uniform(-90, -30), random.uniform(0.5, 1.0)])
        self.wave = max(0.0, self.wave - dt * 0.6)
        edge = self.surf_line()
        if self.wave > 0.3:                   # the big wave takes the letters it reaches
            for l in self.letters:
                if l[4] and l[2] < edge:
                    l[0] = None
            self.letters = [l for l in self.letters if l[0] is not None]
        for s in self.splash:
            s[3] += 160 * dt
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[4] -= dt
        self.splash = [s for s in self.splash if s[4] > 0]
        for c in self.crabs:
            if c['carry'] is None:
                free = [l for l in self.letters if l[4] and not any(o['carry'] is l for o in self.crabs)]
                if free and random.random() < dt * 0.5:
                    c['target'] = random.choice(free)
                tgt = c.get('target')
                if tgt is not None and tgt in self.letters:
                    c['v'] = 10 if tgt[1] > c['x'] else -10
                    if abs(tgt[1] - c['x']) < 2:
                        c['carry'] = tgt
                        c['target'] = None
                        c['v'] = random.choice((-1, 1)) * 8
            elif random.random() < dt * 0.15:
                c['carry'][1] = c['x']
                c['carry'][2] = h * 0.82 + random.uniform(0, h * 0.12)
                c['carry'] = None
            if random.random() < dt * 0.1 and c['carry'] is None and c.get('target') is None:
                c['v'] = random.choice((-1, 1)) * random.uniform(3, 8)
            c['x'] += c['v'] * dt
            if c['x'] < 6 or c['x'] > w - 6:
                c['v'] = -c['v']
                c['x'] = max(6, min(w - 6, c['x']))
            if c['carry'] is not None:
                c['carry'][1], c['carry'][2] = c['x'], h * 0.9 - 9
        if random.random() < dt * 0.06 and len(self.gulls) < 3:
            self.gulls.append([-10.0, random.uniform(h * 0.1, self.hz * 0.7), random.uniform(14, 24), random.random() * 6])
        for g in self.gulls:
            g[0] += g[2] * dt
        self.gulls = [g for g in self.gulls if g[0] < w + 10]
        for c in self.clouds:
            c[0] = (c[0] + 3 * c[2] * dt) % (w + 60)

    def draw(self, surf, first):
        w, h, hz = self.w, self.h, self.hz
        day, hour, sr, ss = daylight()
        top, bot, dusk = sky_colors(day)
        surf.blit(gradient(w, hz, top, bot, self.cache, 'sky'), (0, 0))
        if day < 0.4:
            for x, y, tw in self.stars:
                v = max(0, min(255, int(255 * (1 - day / 0.4) * (0.5 + 0.5 * math.sin(self.t * 2 + tw * 30)))))
                surf.fill((v, v, v), (int(x), int(y), 1, 1))
        cl = _lerp(_lerp((60, 60, 80), (255, 255, 255), day), (255, 170, 140), dusk * 0.7)
        for x, y, s in self.clouds:
            for i in range(4):
                pygame.draw.circle(surf, cl, (int(x - 30 + i * 7 * s), int(y + (i % 2) * 2)), int(5 * s + (i % 2) * 2))
        # sun or moon on the horizon line, with its glitter path
        if day > 0.05:
            f = (hour - sr) / max(0.1, ss - sr)
            sx = int(w * (0.1 + 0.8 * f))
            syy = int(hz - math.sin(max(0, min(1, f)) * math.pi) * hz * 0.85) + 2
            col = _lerp((255, 240, 170), (255, 120, 60), dusk)
            glow(surf, sx, syy, max(10, h // 9), tuple(int(c * 0.25) for c in col))
            pygame.draw.circle(surf, col, (sx, syy), max(5, h // 20))
            path_x, path_c = sx, col
        else:
            path_x, path_c = int(w * 0.7), (220, 220, 200)
            r = max(4, h // 28)
            pygame.draw.circle(surf, (235, 232, 205), (path_x, int(hz * 0.3)), r)
            ph = moon_phase()
            if abs(ph - 0.5) > 0.06:
                pygame.draw.circle(surf, top, (path_x + int((ph - 0.5) * 4 * r), int(hz * 0.3)), r)
        # sea
        sea_t = _lerp(_lerp((8, 20, 50), (40, 120, 190), day), (120, 80, 120), dusk * 0.6)
        sea_b = _lerp((10, 30, 60), (60, 160, 200), day)
        surf.blit(gradient(w, self.shore - hz, sea_t, sea_b, self.cache, 'sea'), (0, hz))
        rnd = random.Random(int(self.t * 5))
        for _ in range(40):
            yy = hz + int(rnd.random() ** 1.6 * (self.shore - hz))
            spread = 4 + (yy - hz) * 0.5
            x = path_x + rnd.gauss(0, spread)
            v = 0.7 * (1 - (yy - hz) / max(1, self.shore - hz) * 0.6)
            surf.fill(tuple(int(c * v) for c in path_c), (int(x), yy, rnd.randint(2, 5), 1), special_flags=ADD)
        for i in range(6):
            yy = hz + 3 + i * (self.shore - hz) // 6
            for x in range(int((self.t * (4 + i * 2)) % 24) - 24, w, 24):
                surf.fill(_lerp(sea_b, (255, 255, 255), 0.25), (x, yy, 6 + i, 1))
        # sand, wet sand, foam line
        sand = _lerp((40, 35, 30), (235, 210, 150), max(day, 0.15))
        surf.fill(sand, (0, self.shore, w, h - self.shore))
        edge = self.surf_line()
        wet = _lerp(sand, sea_b, 0.35)
        pts = [(x, edge + math.sin(x * 0.08 + self.t * 2) * 2) for x in range(0, w + 8, 8)]
        pygame.draw.polygon(surf, wet, [(0, self.shore)] + pts + [(w, self.shore)])
        pygame.draw.polygon(surf, _lerp(sea_b, (180, 220, 240), 0.2),
                            [(0, self.shore)] + [(x, y - 2) for x, y in pts] + [(w, self.shore)])
        pygame.draw.lines(surf, (240, 250, 255), False, pts, 2)
        self._lighthouse(surf, day)
        self._beach_details(surf, day)
        self._palm(surf, day)
        # letters on the sand, crabs, splash, gulls
        for c, x, y, vy, landed in self.letters:
            _letter(surf, x, y, c, _lerp((80, 70, 60), (90, 60, 40), 0.5) if landed else (255, 255, 255))
        for c in self.crabs:
            x, y = int(c['x']), int(h * 0.9)
            leg = int(self.t * 10 + c['ph']) % 2
            red = (220, 70, 50) if day > 0.2 else (120, 40, 30)
            surf.fill(red, (x - 3, y - 3, 7, 3))
            surf.fill(red, (x - 5, y - 5 - leg, 2, 2))
            surf.fill(red, (x + 4, y - 5 - (1 - leg), 2, 2))
            surf.fill((20, 20, 20), (x - 1, y - 4, 1, 1))
            surf.fill((20, 20, 20), (x + 1, y - 4, 1, 1))
            for i in (-3, -1, 1, 3):
                surf.fill(red, (x + i, y, 1, 1 + (leg if i % 4 else 1 - leg)))
        for x, y, vx, vy, life in self.splash:
            surf.fill((235, 245, 255), (int(x), int(y), 2, 2))
        for g in self.gulls:
            up = math.sin(self.t * 8 + g[3]) > 0
            col = (240, 240, 240) if day > 0.3 else (90, 90, 100)
            x, y = int(g[0]), int(g[1])
            surf.fill(col, (x, y, 1, 1))
            surf.fill(col, (x - 2, y - (1 if up else -1), 2, 1))
            surf.fill(col, (x + 1, y - (1 if up else -1), 2, 1))


    # ------------------------------------------------------------ palm
    def _palm(self, surf, day):
        h = self.h
        k = h / 240
        lit = max(day, 0.12)
        H = h * 0.64
        bx, by = self.palm_x, h + 2
        tx, ty = bx + h * 0.11, h - H
        cx, cy = bx - h * 0.07, h - H * 0.45
        wind = math.sin(self.t * 0.7) * 0.05 + math.sin(self.t * 1.9) * 0.015
        tx += wind * h * 0.15
        dark = _lerp((14, 10, 8), (96, 64, 36), lit)
        mid = _lerp((22, 16, 10), (138, 96, 56), lit)
        hi = _lerp((30, 22, 14), (182, 138, 86), lit)
        n = int(H / max(1, k))
        prev = None
        for i in range(n + 1):
            t = i / n
            x = (1 - t) ** 2 * bx + 2 * (1 - t) * t * cx + t * t * tx
            y = (1 - t) ** 2 * by + 2 * (1 - t) * t * cy + t * t * ty
            r = (4.6 - 2.2 * t) * k
            ring = (i // max(1, int(3 * k))) % 2
            pygame.draw.circle(surf, dark if ring else mid, (int(x), int(y)), max(1, int(r)))
            surf.fill(hi, (int(x - r * 0.6), int(y), max(1, int(r * 0.5)), 1))
            prev = (x, y)
        topx, topy = prev
        # fronds: back ones darker, drawn first
        fronds = [(-2.6, 1.05, 0), (-0.5, 1.05, 0), (-1.6, 0.6, 0), (-3.3, 0.9, 0), (0.15, 0.9, 0),
                  (-2.15, 0.95, 1), (-0.95, 0.95, 1), (-2.95, 0.85, 1), (-0.15, 0.85, 1), (-1.85, 0.7, 1), (-1.3, 0.7, 1)]
        for j, (a0, ln, front) in enumerate(fronds):
            base = _lerp((6, 16, 8), (34, 110, 46), lit) if not front else _lerp((10, 24, 12), (58, 156, 64), lit)
            tip = _lerp(base, _lerp((20, 30, 15), (150, 200, 90), lit), 0.55)
            a = a0 + math.sin(self.t * 1.3 + j * 1.7) * 0.035 + wind * 1.4
            L = h * 0.23 * ln
            steps = int(16 * ln) + 4
            pts = []
            for i in range(steps + 1):
                q = i / steps
                pts.append((topx + math.cos(a) * L * q, topy + math.sin(a) * L * q + (q * q) * L * 0.85))
            for i in range(1, len(pts)):
                q = i / steps
                x0, y0 = pts[i - 1]
                x1, y1 = pts[i]
                pygame.draw.line(surf, base, (x0, y0), (x1, y1), max(1, int(2 * k)))
                dx, dy = x1 - x0, y1 - y0
                dl = math.hypot(dx, dy) or 1
                nx, ny = -dy / dl, dx / dl
                ll = (1 - q * 0.7) * h * 0.042
                col = _lerp(base, tip, q)
                for sd in (-1, 1):
                    ex = x1 + nx * ll * sd - dx / dl * ll * 0.6
                    ey = y1 + ny * ll * sd - dy / dl * ll * 0.6 + ll * 0.8
                    pygame.draw.line(surf, col, (x1, y1), (ex, ey), 1)
        nut = _lerp((12, 8, 4), (92, 60, 28), lit)
        for dx, dy in ((-2, 3), (2, 4), (0, 6)):
            pygame.draw.circle(surf, nut, (int(topx + dx * k), int(topy + dy * k)), max(2, int(2.4 * k)))
            surf.fill(_lerp(nut, (200, 160, 110), 0.35), (int(topx + dx * k) - 1, int(topy + dy * k) - 1, 1, 1))

    # ------------------------------------------------------------ lighthouse
    def _beach_details(self, surf, day):
        """shells, starfish and a little sand castle"""
        h = self.h
        k = h / 240
        lit = max(day, 0.15)
        rng = random.Random(31)
        for _ in range(12):
            x, y = rng.uniform(0, self.w), rng.uniform(h * 0.84, h * 0.99)
            kind = rng.random()
            if kind < 0.3:          # starfish
                c = _lerp((40, 20, 15), (236, 120, 80), lit)
                for a in range(5):
                    ang = a * math.tau / 5 - math.pi / 2
                    for r in range(1, int(3 * k) + 1):
                        surf.fill(c, (int(x + math.cos(ang) * r), int(y + math.sin(ang) * r), 1, 1))
                surf.fill(c, (int(x), int(y), 1, 1))
            else:                   # shell
                c = _lerp((40, 36, 34), rng.choice([(250, 236, 220), (240, 200, 190), (220, 210, 240)]), lit)
                surf.fill(c, (int(x), int(y), int(3 * k), int(2 * k)))
                surf.fill(_lerp(c, (0, 0, 0), 0.3), (int(x + k), int(y), 1, int(2 * k)))
        # sand castle
        sx, sy = int(self.w * 0.44), int(h * 0.93)
        sand = _lerp((34, 30, 24), (214, 186, 126), lit)
        shade = _lerp(sand, (0, 0, 0), 0.25)
        surf.fill(sand, (sx, sy - int(6 * k), int(16 * k), int(6 * k)))
        for tx in (sx, sx + int(12 * k)):
            surf.fill(sand, (tx, sy - int(11 * k), int(4 * k), int(5 * k)))
            surf.fill(shade, (tx + int(3 * k), sy - int(11 * k), max(1, int(k)), int(11 * k)))
        surf.fill(sand, (sx + int(5 * k), sy - int(14 * k), int(6 * k), int(8 * k)))
        surf.fill(shade, (sx + int(7 * k), sy - int(4 * k), int(2 * k), int(4 * k)))
        surf.fill(_lerp((40, 10, 10), (220, 50, 50), lit), (sx + int(8 * k), sy - int(19 * k), int(3 * k), int(2 * k)))
        surf.fill(shade, (sx + int(8 * k), sy - int(19 * k), 1, int(5 * k)))

    def _lighthouse(self, surf, day):
        w, h, hz = self.w, self.h, self.hz
        k = h / 240
        lit = max(day, 0.15)
        lx = int(w * 0.86)
        base_y = hz + int(3 * k)
        # rocky islet with foam
        rw = int(h * 0.14)
        rng = random.Random(77)
        rock_pts = [(lx - rw, base_y + 2)]
        for i in range(9):
            x = lx - rw + (2 * rw) * (i + 0.5) / 9
            rock_pts.append((x, base_y - int(rng.uniform(2, 9) * k * (1 - abs(i - 4) / 6))))
        rock_pts.append((lx + rw, base_y + 2))
        pygame.draw.polygon(surf, _lerp((18, 18, 24), (96, 92, 98), lit), rock_pts)
        for i in range(1, len(rock_pts) - 2, 2):
            x, y = rock_pts[i]
            surf.fill(_lerp((26, 26, 32), (138, 132, 136), lit), (int(x), int(y), int(3 * k), 1))
        for i in range(7):
            fx = lx - rw + (i + 0.5) * 2 * rw / 7 + math.sin(self.t * 2 + i) * 2
            if math.sin(self.t * 2.6 + i * 1.9) > 0.2:
                surf.fill((235, 245, 255) if day > 0.2 else (120, 130, 150), (int(fx), base_y + 1, int(3 * k), 1))
        # tapered striped tower with shading
        th = int(h * 0.19)
        bw, tw = h * 0.034, h * 0.022
        top = base_y - int(4 * k) - th
        red = _lerp((40, 10, 10), (206, 44, 40), lit)
        white = _lerp((50, 50, 60), (244, 240, 232), lit)
        for i in range(th):
            y = base_y - int(4 * k) - i
            q = i / th
            hw = bw + (tw - bw) * q
            band = int(q * 5) % 2
            c = red if band else white
            surf.fill(_lerp(c, (0, 0, 0), 0.32), (int(lx - hw), y, int(hw * 2) + 1, 1))
            surf.fill(c, (int(lx - hw), y, int(hw * 1.25), 1))
            surf.fill(_lerp(c, (255, 255, 255), 0.35), (int(lx - hw * 0.7), y, max(1, int(hw * 0.3)), 1))
        door = _lerp((10, 8, 8), (60, 40, 30), lit)
        surf.fill(door, (lx - int(2 * k), base_y - int(4 * k) - int(6 * k), int(4 * k), int(6 * k)))
        for q in (0.45, 0.72):
            wy = base_y - int(4 * k) - int(th * q)
            surf.fill((255, 220, 140) if day < 0.5 else (60, 70, 90), (lx - int(k), wy, max(1, int(2 * k)), max(2, int(3 * k))))
        # gallery, lantern room, dome
        gy = top
        gw = int(tw + 3 * k)
        rail = _lerp((10, 10, 14), (50, 50, 60), lit)
        surf.fill(rail, (lx - gw, gy, gw * 2 + 1, max(1, int(2 * k))))
        for x in range(lx - gw, lx + gw + 1, max(2, int(3 * k))):
            surf.fill(rail, (x, gy - int(3 * k), 1, int(3 * k)))
        surf.fill(rail, (lx - gw, gy - int(3 * k), gw * 2 + 1, 1))
        lw, lh = int(tw * 0.9), int(6 * k)
        ly = gy - lh
        night = day < 0.5
        glass = (255, 236, 160) if night else _lerp((90, 110, 140), (170, 210, 235), lit)
        surf.fill(glass, (lx - lw, ly, lw * 2 + 1, lh))
        for x in (lx - lw, lx, lx + lw):
            surf.fill(rail, (x, ly, 1, lh))
        dome = _lerp((30, 8, 8), (170, 36, 32), lit)
        pygame.draw.ellipse(surf, dome, (lx - lw - 1, ly - int(4 * k), lw * 2 + 3, int(7 * k)))
        surf.fill(rail, (lx, ly - int(7 * k), 1, int(4 * k)))
        lamp_y = ly + lh // 2
        if night:
            a = self.t * 0.9
            facing = max(0.0, math.sin(a))
            reach = math.cos(a)
            glow(surf, lx, lamp_y, int(6 * k + 14 * k * facing), (int(70 + 120 * facing), int(60 + 100 * facing), int(25 + 40 * facing)))
            L = int(w * 0.5 * abs(reach))
            if L > 4:
                key = ('beam', L, int(h))
                beam = self.cache.get(key)
                if beam is None:
                    bh = int(h * 0.05)
                    beam = pygame.Surface((L, bh * 2 + 1))
                    beam.fill((0, 0, 0))
                    for x in range(L):
                        q = x / L
                        half = int(1 + bh * q)
                        v = (1 - q) ** 1.4
                        for yy in range(-half, half + 1):
                            e = 1 - abs(yy) / (half + 1)
                            c = (int(90 * v * e), int(80 * v * e), int(40 * v * e))
                            beam.set_at((x, bh + yy), c)
                    if len(self.cache) > 80:
                        self.cache = {kk: vv for kk, vv in self.cache.items() if kk[0] != 'beam'}
                    self.cache[key] = beam
                img = beam if reach > 0 else pygame.transform.flip(beam, True, False)
                bx = lx if reach > 0 else lx - L
                surf.blit(img, (bx, lamp_y - img.get_height() // 2), special_flags=ADD)
                # its streak on the water
                ry = base_y + int(6 * k)
                for i in range(0, L, 3):
                    v = int(40 * (1 - i / L) * (0.6 + 0.4 * math.sin(self.t * 5 + i)))
                    x = lx + i if reach > 0 else lx - i
                    surf.fill((v, v, int(v * 0.6)), (x, ry + (i % 7), 2, 1), special_flags=ADD)
        else:
            glow(surf, lx, lamp_y, int(4 * k), (20, 20, 14))


SCENES2 = {c.name: c for c in (Aquarium, SpaceStation, Garden, Pinball, C64Load, Beach)}
