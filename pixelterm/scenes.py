"""Living background scenes:

  dollhouse  - a tiny resident lives in a cutaway house on your local time and
               sits down at its own computer whenever you type
  railway    - a cute steam railway: stations, passengers, level crossing,
               windmill, cows, bridge, tunnel, smoke puffs, day & night
  settlers   - a little economy: carriers on roads between flags, woodcutter,
               forester, farm, windmill, bakery, fisher, stonecutter
  discocity  - 80s retro-wave night: neon city & signs, disco ball light spots,
               lasers, scrolling grid, palms, equalizer pulsing to your output

All of them react to the terminal through pixelterm.signals (typing, Enter,
command results, output energy). Original pixel art, drawn procedurally.
"""
from __future__ import annotations

import math
import random
import time

import numpy as np
import pygame

from . import signals
from .backgrounds import Background
from .weather import _lerp, moon_phase, solar_times, tiny_text


# ---------------------------------------------------------------------------- shared helpers
def daylight(lat=52.5, lon=13.4, hour=None):
    if hour is None:
        t = time.localtime()
        hour = t.tm_hour + t.tm_min / 60
    sr, ss = solar_times(lat, lon)
    if hour < sr - 0.8 or hour > ss + 0.8:
        return 0.0, hour, sr, ss
    if hour < sr + 0.8:
        return (hour - (sr - 0.8)) / 1.6, hour, sr, ss
    if hour > ss - 0.8:
        return ((ss + 0.8) - hour) / 1.6, hour, sr, ss
    return 1.0, hour, sr, ss


def sky_colors(day):
    dusk = max(0.0, 1 - abs(day - 0.5) * 2) if 0.02 < day < 0.98 else 0.0
    top = _lerp(_lerp((8, 10, 30), (60, 130, 230), day), (70, 60, 140), dusk * 0.7)
    bot = _lerp(_lerp((25, 28, 70), (170, 215, 250), day), (255, 160, 100), dusk * 0.8)
    return top, bot, dusk


def gradient(w, h, top, bot, cache, key):
    k = (w, h, tuple(int(v) // 4 for v in top + bot), key)
    s = cache.get(k)
    if s is None:
        col = pygame.Surface((1, 32))
        for y in range(32):
            col.set_at((0, y), [int(top[i] + (bot[i] - top[i]) * y / 31) for i in range(3)])
        s = pygame.transform.smoothscale(col, (w, h))
        if len(cache) > 50:
            cache.clear()
        cache[k] = s
    return s


def sprite(rows, pal):
    s = pygame.Surface((len(rows[0]), len(rows)), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c in pal:
                s.set_at((x, y), pal[c])
    return s


_GLOW = {}


def glow(surf, x, y, r, col):
    """soft additive light disc"""
    k = (r, col)
    g = _GLOW.get(k)
    if g is None:
        g = pygame.Surface((2 * r + 1, 2 * r + 1))
        g.fill((0, 0, 0))
        for i in range(r, 0, -1):
            f = 1 - i / (r + 1)
            pygame.draw.circle(g, tuple(int(c * f) for c in col), (r, r), i)
        _GLOW[k] = g
    surf.blit(g, (int(x) - r, int(y) - r), special_flags=pygame.BLEND_RGB_ADD)


def bubble(surf, x, y, emoji_char=None, text=None):
    """small speech bubble with an emoji (pixel emoji module) or tiny text"""
    from . import emoji
    if emoji_char:
        img = emoji.surface(emoji_char, 12, 10, int(time.time() * 8))
        w, h = img.get_width() + 4, img.get_height() + 4
        bx, by = int(x - w // 2), int(y - h - 3)
        surf.fill((255, 255, 255), (bx, by, w, h))
        surf.fill((255, 255, 255), (int(x) - 1, by + h, 2, 2))
        surf.blit(img, (bx + 2, by + 2))
    elif text:
        w, h = len(text) * 4 + 3, 8
        bx, by = int(x - w // 2), int(y - h - 3)
        surf.fill((255, 255, 255), (bx, by, w, h))
        surf.fill((255, 255, 255), (int(x) - 1, by + h, 2, 2))
        tiny_text(surf, bx + 2, by + 2, text, (20, 20, 30))


PERSON_PAL = {'H': (90, 50, 20), 'S': (250, 200, 160), 'T': (220, 60, 60), 'P': (50, 70, 160), 'K': (40, 30, 20),
              'E': (20, 20, 20)}
P_TOP = [".HH..", "HSSH.", ".SE..", "TTTT.", "TTTT."]
P_LEGS = {'stand': [".TT..", ".PP..", ".PP..", ".KK.."],
          'walk1': [".TT..", ".P.P.", "P...P", "K...K"],
          'walk2': [".TT..", ".PP..", ".PP..", ".KK.."],
          'sit': [".TT..", ".PPP.", ".P..P", ".K..K"],
          'type1': ["TTTTT", ".PPP.", ".P..P", ".K..K"],
          'type2': [".TTTT", ".PPP.", ".P..P", ".K..K"]}


class Person:
    """tiny pixel person, any shirt color"""
    cache = {}

    @classmethod
    def img(cls, pose, face, shirt=(220, 60, 60), hair=(90, 50, 20)):
        key = (pose, face, shirt, hair)
        s = cls.cache.get(key)
        if s is None:
            pal = dict(PERSON_PAL, T=shirt, H=hair)
            if pose == 'lie':
                s = pygame.transform.rotate(sprite(P_TOP + P_LEGS['stand'], pal), 90)
            else:
                s = sprite(P_TOP + P_LEGS[pose], pal)
            if face < 0:
                s = pygame.transform.flip(s, True, False)
            cls.cache[key] = s
        return s


# ============================================================================ dollhouse
class Dollhouse(Background):
    name = 'dollhouse'
    opaque = True
    ACTS = {
        'sleep': (2, 'bed', 'lie', '😴'), 'eat': (0, 'table', 'sit', '🍕'), 'cook': (0, 'stove', 'stand', None),
        'type': (1, 'desk', 'type', None), 'tv': (1, 'sofa', 'sit', '😊'), 'piano': (1, 'piano', 'sit', None),
        'water': (1, 'plant', 'stand', None), 'read': (2, 'shelf', 'stand', '🤓'), 'dog': (-1, 'yard', 'stand', '❤'),
        'stretch': (0, 'mid', 'stand', None), 'think': (1, 'desk_side', 'stand', '🤔'), 'dance': (1, 'mid', 'stand', '🥳'),
    }

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.gy = int(h * 0.92)
        hw = max(130, int(w * 0.38))
        self.fh = max(26, int(h * 0.2))
        self.x0 = w - hw - max(4, int(w * 0.03))
        self.x1 = self.x0 + hw
        self.floors = [self.gy - (i + 1) * self.fh for i in range(3)]   # top y of each floor
        X = lambda f: int(self.x0 + 6 + (hw - 12) * f)
        self.spots = {'bed': (2, X(0.68)), 'shelf': (2, X(0.35)), 'stove': (0, X(0.42)), 'table': (0, X(0.68)),
                      'desk': (1, X(0.30)), 'desk_side': (1, X(0.38)), 'sofa': (1, X(0.70)), 'piano': (1, X(0.88)),
                      'plant': (1, X(0.52)), 'mid': (0, X(0.55)), 'yard': (-1, max(10, self.x0 - int(w * 0.12)))}
        self.stair_x = X(0.1)
        self.px, self.floor = float(X(0.5)), 1
        self.face = 1
        self.act = 'tv'
        self.act_t = 0.0
        self.path = []
        self.walk_t = 0.0
        self.climb = None
        self.react = None
        self.last_cmd = None
        self.dogx = float(self.x0 - 30)
        self.dogv = 10.0
        self.smoke = []
        self.notes = []
        self.drops = []
        self.plant_h = 3.0
        self.screen_lines = [random.randint(2, 8) for _ in range(5)]
        self.stars = [(random.uniform(0, w), random.uniform(0, self.gy * 0.7), random.random()) for _ in range(70)]
        self.mail = 0.0

    # ------------------------------------------------------------ brain
    def choose(self, hour):
        if signals.recent(signals.typing, 2.5) and not (self.act == 'sleep' and hour < 6):
            return 'type'
        if 23 <= hour or hour < 7:
            return 'sleep'
        for m in (7.5, 12.5, 19):
            if m <= hour < m + 0.25:
                return 'cook'
            if m + 0.25 <= hour < m + 0.6:
                return 'eat'
        return random.choice(['tv', 'piano', 'water', 'read', 'dog', 'stretch', 'tv', 'read'])

    def plan(self, act):
        floor, spot, pose, emo = self.ACTS[act]
        f, x = self.spots[spot]
        self.path = []
        cur = self.floor
        if f == -1:
            f = 0
        while cur != f:
            self.path.append(('stairs', cur, 1 if f > cur else -1))
            cur += 1 if f > cur else -1
        if self.ACTS[act][0] == -1:
            self.path.append(('walk', self.x0 + 2))
            self.path.append(('out', x))
        else:
            if self.floor == 0 and self.px < self.x0:
                self.path.insert(0, ('in', self.x0 + 8))
            self.path.append(('walk', x))
        self.act = act
        self.act_t = 0.0

    def update(self, dt, energy):
        super().update(dt, energy)
        _, hour, _, _ = daylight()
        self.hour = hour
        # reactions to the terminal
        if signals.cmd and signals.cmd is not self.last_cmd:
            self.last_cmd = signals.cmd
            code, secs, _ = signals.cmd
            if code:
                self.react = ('😱' if code > 1 else '😢', 2.0)
            elif secs >= 2:
                self.react = ('🥳', 2.5)
                self.hop = 2.5
        if signals.recent(signals.bell, 0.2):
            self.mail = 6.0
        self.mail = max(0.0, self.mail - dt)
        if self.react:
            self.react = (self.react[0], self.react[1] - dt) if self.react[1] > dt else None
        self.act_t += dt
        want = self.choose(hour)
        if (want == 'type' and self.act != 'type') or (want == 'sleep' and self.act != 'sleep') \
                or (self.act_t > random.uniform(12, 25) and not self.path and want != self.act and self.act not in ('type',)) \
                or (self.act == 'type' and want != 'type' and not self.path):
            self.plan(want)
        # follow path
        speed = 22.0
        if self.path:
            step = self.path[0]
            if step[0] in ('walk', 'in', 'out'):
                tx = step[1] if step[0] != 'walk' or step[1] > 0 else self.stair_x
                d = tx - self.px
                if abs(d) < 1:
                    self.px = float(tx)
                    self.path.pop(0)
                    if step[0] == 'out':
                        self.floor = -1
                    if step[0] == 'in':
                        self.floor = 0
                else:
                    self.face = 1 if d > 0 else -1
                    self.px += max(-speed * dt, min(speed * dt, d))
                    self.walk_t += dt
            elif step[0] == 'stairs':
                if abs(self.px - self.stair_x) > 1:
                    d = self.stair_x - self.px
                    self.face = 1 if d > 0 else -1
                    self.px += max(-speed * dt, min(speed * dt, d))
                    self.walk_t += dt
                else:
                    if self.climb is None:
                        self.climb = 0.0
                    self.climb += dt / 1.2
                    self.walk_t += dt
                    if self.climb >= 1:
                        self.climb = None
                        self.floor = step[1] + step[2]
                        self.path.pop(0)
        else:
            self.walk_t = 0.0
        # props
        if self.act == 'cook' and not self.path and random.random() < dt * 4:
            self.smoke.append([self.x1 - 18, self.floors[2] - self.fh * 0.6, 2.0, 1.0])
        if (hour < 7 or hour > 20) and random.random() < dt * 1.5:
            self.smoke.append([self.x1 - 18, self.floors[2] - self.fh * 0.6, 2.0, 1.0])
        for p in self.smoke:
            p[0] += (4 + math.sin(self.t + p[1]) * 3) * dt
            p[1] -= 10 * dt
            p[2] += 2 * dt
            p[3] -= dt * 0.35
        self.smoke = [p for p in self.smoke if p[3] > 0]
        if self.act == 'piano' and not self.path and random.random() < dt * 2.5:
            self.notes.append([self.spots['piano'][1], self.floors[1] + self.fh * 0.35, 1.5])
        for n in self.notes:
            n[1] -= 8 * dt
            n[0] += math.sin(self.t * 4 + n[1]) * 6 * dt
            n[2] -= dt
        self.notes = [n for n in self.notes if n[2] > 0]
        if self.act == 'water' and not self.path:
            self.plant_h = min(10.0, self.plant_h + dt * 0.3)
            if random.random() < dt * 12:
                self.drops.append([self.spots['plant'][1] + 2, self.floors[1] + self.fh - 12, 0.5])
        for d in self.drops:
            d[1] += 30 * dt
            d[2] -= dt
        self.drops = [d for d in self.drops if d[2] > 0]
        if self.act == 'type' and random.random() < dt * 10:
            self.screen_lines = self.screen_lines[1:] + [random.randint(1, 8)]
        # dog
        self.dogx += self.dogv * dt
        lo, hi = 6, self.x0 - 10
        if self.act == 'dog' and self.floor == -1:
            tgt = self.px - 10
            self.dogv = max(-25, min(25, (tgt - self.dogx) * 2 + math.sin(self.t * 3) * 15))
        elif self.dogx < lo or self.dogx > hi or random.random() < dt * 0.3:
            self.dogv = random.choice((-1, 1)) * random.uniform(6, 14)
        self.dogx = max(lo, min(hi, self.dogx))

    # ------------------------------------------------------------ render
    def draw(self, surf, first):
        w, h, gy = self.w, self.h, self.gy
        day, hour, sr, ss = daylight()
        top, bot, dusk = sky_colors(day)
        surf.blit(gradient(w, h, top, bot, self.cache, 'sky'), (0, 0))
        if day < 0.4:
            for x, y, tw in self.stars:
                v = max(0, min(255, int(255 * (1 - day / 0.4) * (0.5 + 0.5 * math.sin(self.t * 2 + tw * 30)))))
                surf.fill((v, v, v), (int(x), int(y), 1, 1))
            mx, my, r = int(w * 0.25), int(h * 0.15), max(4, h // 28)
            pygame.draw.circle(surf, (235, 232, 205), (mx, my), r)
            ph = moon_phase()
            off = int((ph - 0.5) * 4 * r) if ph < 0.5 else int((ph - 0.5) * 4 * r)
            if abs(ph - 0.5) > 0.06:
                pygame.draw.circle(surf, top, (mx + off, my), r)
        else:
            f = (hour - sr) / max(0.1, ss - sr)
            sx, sy = int(w * (0.1 + 0.8 * f)), int(gy - math.sin(max(0, min(1, f)) * math.pi) * gy * 0.75)
            pygame.draw.circle(surf, _lerp((255, 240, 170), (255, 150, 70), dusk), (sx, sy), max(4, h // 22))
        # lawn + fence + tree + doghouse
        grass = _lerp((20, 40, 25), (80, 170, 70), day)
        surf.fill(grass, (0, gy, w, h - gy))
        fence = _lerp((40, 40, 45), (230, 225, 210), day)
        for x in range(0, self.x0 - 4, 6):
            surf.fill(fence, (x, gy - 6, 2, 6))
        surf.fill(fence, (0, gy - 5, self.x0 - 4, 1))
        dhx = int(self.x0 * 0.35)
        surf.fill(_lerp((40, 20, 10), (160, 80, 40), day), (dhx, gy - 9, 12, 9))
        pygame.draw.polygon(surf, _lerp((50, 10, 10), (190, 50, 40), day), [(dhx - 2, gy - 9), (dhx + 14, gy - 9), (dhx + 6, gy - 15)])
        surf.fill((10, 5, 5), (dhx + 4, gy - 5, 4, 5))
        # mailbox (flag up on bell)
        mbx = self.x0 - 8
        surf.fill((60, 60, 70), (mbx, gy - 8, 1, 8))
        surf.fill((70, 90, 200), (mbx - 2, gy - 11, 5, 4))
        if self.mail > 0:
            surf.fill((230, 40, 40), (mbx + 3, gy - 14, 1, 4))
            surf.fill((230, 40, 40), (mbx + 4, gy - 14, 2, 2))
        # dog
        dk = int(self.t * 8) % 2
        dog = sprite(["....bb", "bbbbbb", ".b..b." if dk else "b....b"], {'b': _lerp((60, 40, 20), (170, 110, 60), day)})
        if self.dogv < 0:
            dog = pygame.transform.flip(dog, True, False)
        surf.blit(dog, (int(self.dogx), gy - 3))
        # house
        x0, x1, fh = self.x0, self.x1, self.fh
        wall = _lerp((60, 50, 45), (220, 200, 170), day)
        lights = day < 0.5 or self.act != 'sleep'
        papers = [(250, 240, 190), (200, 230, 200), (200, 210, 245)]
        for i, fy in enumerate(self.floors):
            pc = papers[i]
            lit = (day > 0.5) or (self.floor == i or (i == 2 and self.act == 'read')) and lights
            k = 1.0 if day > 0.5 else (0.75 if lit else 0.3)
            col = tuple(int(c * k) for c in pc)
            surf.fill(col, (x0, fy, x1 - x0, fh))
            for yy in range(fy + 3, fy + fh - 3, 5):
                for xx in range(x0 + 4 + (yy // 5) % 2 * 3, x1 - 3, 6):
                    surf.fill(tuple(max(0, c - 18) for c in col), (xx, yy, 1, 1))
            surf.fill(_lerp((50, 30, 15), (140, 90, 50), max(k, 0.3)), (x0, fy + fh - 2, x1 - x0, 2))
            # window with sky
            wy = fy + fh // 4
            surf.fill(wall, (x1 - 3, fy, 3, fh))
            surf.blit(gradient(6, fh // 2, top, bot, self.cache, 'win'), (x1 - 2, wy))
        # outer walls & roof
        surf.fill(wall, (x0 - 3, self.floors[2], 3, gy - self.floors[2]))
        surf.fill(wall, (x1, self.floors[2], 3, gy - self.floors[2]))
        roof = _lerp((60, 15, 15), (180, 60, 45), day)
        rt = self.floors[2]
        pygame.draw.polygon(surf, roof, [(x0 - 8, rt), (x1 + 8, rt), ((x0 + x1) // 2, rt - int(fh * 0.9))])
        surf.fill(roof, (x1 - 22, rt - int(fh * 0.75), 8, int(fh * 0.5)))
        for p in self.smoke:
            v = max(0, min(255, int(150 + 90 * min(1, p[3]))))
            pygame.draw.circle(surf, _lerp((70, 70, 85), (v, v, v), max(day, 0.15)), (int(p[0]), int(p[1])), int(p[2]))
        # door
        surf.fill(_lerp((40, 20, 10), (120, 70, 35), day), (x0 - 3, gy - 14, 3, 14))
        # stairs
        sc = _lerp((40, 25, 15), (150, 100, 60), day)
        for i in range(2):
            fy = self.floors[i]
            for s in range(6):
                surf.fill(sc, (self.stair_x - 6 + s * 2, fy + fh - 2 - s * (fh // 6), 4, 2))
        self._furniture(surf, day)
        # resident
        self._resident(surf)
        # notes, drops
        for n in self.notes:
            surf.fill((40, 40, 60), (int(n[0]), int(n[1]), 1, 3))
            surf.fill((40, 40, 60), (int(n[0]) - 1, int(n[1]) + 2, 2, 1))
        for d in self.drops:
            surf.fill((80, 140, 255), (int(d[0]), int(d[1]), 1, 2))

    def _furniture(self, surf, day):
        fl, fh = self.floors, self.fh
        dark = (40, 30, 30)
        # bedroom
        f, x = self.spots['bed']
        by = fl[2] + fh - 2
        surf.fill((120, 70, 40), (x - 10, by - 6, 20, 4))
        surf.fill((230, 230, 240), (x - 10, by - 8, 5, 2))
        surf.fill((70, 110, 200), (x - 5, by - 8, 15, 3))
        lamp_on = day < 0.5 and self.act != 'sleep'
        surf.fill((200, 180, 100) if lamp_on else (120, 110, 90), (x + 12, by - 9, 3, 2))
        surf.fill(dark, (x + 13, by - 7, 1, 5))
        if lamp_on:
            glow(surf, x + 13, by - 8, 7, (50, 40, 15))
        f, x = self.spots['shelf']
        surf.fill((110, 70, 40), (x - 6, fl[2] + 5, 12, fh - 7))
        for i, c in enumerate([(200, 50, 50), (50, 120, 200), (230, 190, 60), (80, 160, 80), (160, 80, 160)]):
            surf.fill(c, (x - 5 + i * 2, fl[2] + 7, 2, 5))
            surf.fill(c[::-1], (x - 5 + i * 2, fl[2] + 14, 2, 5))
        # living room: desk + computer
        f, x = self.spots['desk']
        dy = fl[1] + fh - 2
        surf.fill((120, 80, 50), (x - 4, dy - 7, 14, 2))
        surf.fill(dark, (x - 3, dy - 5, 1, 5))
        surf.fill(dark, (x + 8, dy - 5, 1, 5))
        surf.fill((200, 200, 190), (x + 1, dy - 15, 9, 7))
        scr = (10, 30, 10)
        surf.fill(scr, (x + 2, dy - 14, 7, 5))
        if self.act == 'type' and not self.path:
            for i, ln in enumerate(self.screen_lines[-4:]):
                surf.fill((80, 255, 120), (x + 2, dy - 14 + i, min(7, ln), 1))
        surf.fill((200, 200, 190), (x + 4, dy - 8, 3, 1))
        # tv + sofa
        f, x = self.spots['sofa']
        surf.fill((150, 60, 70), (x - 6, dy - 6, 14, 4))
        surf.fill((150, 60, 70), (x - 6, dy - 9, 3, 3))
        surf.fill(dark, (x - 16, dy - 12, 9, 7))
        if self.act == 'tv' and not self.path:
            c = [(80, 120, 255), (255, 80, 120), (120, 255, 120), (255, 255, 150)][int(self.t * 3) % 4]
            surf.fill(c, (x - 15, dy - 11, 7, 5))
        else:
            surf.fill((30, 40, 50), (x - 15, dy - 11, 7, 5))
        surf.fill(dark, (x - 13, dy - 5, 3, 3))
        # piano
        f, x = self.spots['piano']
        surf.fill((30, 20, 20), (x - 4, dy - 12, 9, 12))
        surf.fill((240, 240, 240), (x - 4, dy - 7, 9, 2))
        for k in range(0, 9, 2):
            surf.fill((10, 10, 10), (x - 4 + k, dy - 7, 1, 1))
        # plant
        f, x = self.spots['plant']
        surf.fill((180, 90, 50), (x, dy - 4, 5, 4))
        ph = int(self.plant_h)
        surf.fill((60, 160, 60), (x + 2, dy - 4 - ph, 1, ph))
        for i in range(0, ph, 3):
            surf.fill((80, 190, 70), (x + (0 if i % 6 else 3), dy - 4 - i - 1, 2, 1))
        # kitchen
        f, x = self.spots['stove']
        ky = fl[0] + fh - 2
        surf.fill((220, 220, 225), (x - 5, ky - 9, 10, 9))
        surf.fill((40, 40, 45), (x - 4, ky - 7, 8, 5))
        surf.fill((90, 90, 100), (x - 2, ky - 12, 5, 3))
        if self.act == 'cook' and not self.path and int(self.t * 4) % 2:
            surf.fill((230, 230, 230), (x - 1, ky - 15, 1, 2))
            surf.fill((230, 230, 230), (x + 1, ky - 16, 1, 2))
        surf.fill((235, 235, 240), (self.x1 - 14, ky - 18, 9, 18))
        surf.fill((180, 180, 190), (self.x1 - 14, ky - 11, 9, 1))
        f, x = self.spots['table']
        surf.fill((140, 90, 50), (x - 7, ky - 7, 14, 2))
        surf.fill((140, 90, 50), (x - 6, ky - 5, 1, 5))
        surf.fill((140, 90, 50), (x + 5, ky - 5, 1, 5))
        if self.act == 'eat' and not self.path:
            surf.fill((250, 250, 250), (x - 2, ky - 8, 4, 1))
            surf.fill((230, 150, 60), (x - 1, ky - 9, 2, 1))

    def _resident(self, surf):
        fh = self.fh
        if self.floor == -1:
            base_y = self.gy
        else:
            base_y = self.floors[self.floor] + fh - 2
        if self.climb is not None and self.path and self.path[0][0] == 'stairs':
            _, cur, d = self.path[0]
            base_y = self.floors[cur] + fh - 2 - d * self.climb * fh
        pose = 'stand'
        if self.walk_t > 0:
            pose = 'walk1' if int(self.walk_t * 8) % 2 else 'walk2'
        elif not self.path:
            p = self.ACTS[self.act][2]
            if p == 'type':
                pose = 'type1' if int(self.t * 10) % 2 else 'type2'
            else:
                pose = p
        hop = 0
        if self.act == 'stretch' and not self.path:
            hop = int(abs(math.sin(self.t * 5)) * 3)
        if self.react and self.react[0] == '🥳':
            hop = int(abs(math.sin(self.t * 9)) * 4)
        img = Person.img(pose, self.face)
        x = int(self.px) - 2
        y = int(base_y) - img.get_height() - hop
        if pose == 'lie':
            y = int(base_y) - 9
            x = int(self.spots['bed'][1]) - 8
        surf.blit(img, (x, y))
        emo = self.react[0] if self.react else (self.ACTS[self.act][3] if not self.path else None)
        if self.act == 'piano' and not self.path:
            emo = None
        if emo and int(self.t * 0.5) % 3 != 2:
            bubble(surf, x + 3, y, emo)


# ============================================================================ railway
class Railway(Background):
    name = 'railway'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.ty = int(h * 0.74)               # rail top
        self.river = (int(w * 0.30), int(w * 0.40))
        self.tunnel_x = int(w * 0.90)
        self.station = (int(w * 0.52), int(w * 0.70))
        self.crossing_x = int(w * 0.18)
        self.stop_x = self.station[1] - 6
        self.trains = []
        self.spawn_t = 0.5
        self.puffs = []
        self.mill_x, self.mill_y = int(w * 0.10), int(self.ty - h * 0.18)
        self.cows = [[random.uniform(w * 0.42, w * 0.5), random.random() * 6, random.choice((-1, 1)), 0.0] for _ in range(2)]
        self.cows += [[random.uniform(w * 0.72, w * 0.86), random.random() * 6, random.choice((-1, 1)), 0.0]]
        self.people = [[random.uniform(self.station[0] + 8, self.station[1] - 10), random.choice([(220, 60, 60), (60, 120, 220), (230, 190, 50), (90, 180, 90)]), 'wait'] for _ in range(4)]
        self.clouds = [[random.uniform(0, w), random.uniform(5, h * 0.3), random.uniform(0.6, 1.4)] for _ in range(5)]
        self.stars = [(random.uniform(0, w), random.uniform(0, h * 0.6), random.random()) for _ in range(80)]
        self.birds = []
        rng = random.Random(5)
        xs = np.arange(w)
        self.hill = (self.ty - h * 0.20 - np.sin(xs / w * 6 + 1) * h * 0.05 - np.sin(xs / w * 15) * h * 0.02).astype(int)
        self.trees = [(rng.uniform(0, w), rng.uniform(0.6, 1.0)) for _ in range(14)]
        self.last_cmd = None
        self.toot = 0.0

    def new_train(self):
        kind = random.choice(['passenger', 'passenger', 'freight'])
        body = random.choice([(200, 40, 40), (40, 140, 80), (40, 80, 180)])
        cars = []
        n = random.randint(2, 4)
        for i in range(n):
            if kind == 'passenger':
                cars.append(('coach', random.choice([(200, 160, 60), (190, 60, 60), (60, 120, 190), (90, 160, 90)])))
            else:
                cars.append(random.choice([('logs', None), ('box', random.choice([(220, 120, 40), (60, 140, 200), (200, 60, 80)])),
                                           ('tank', (180, 180, 190))]))
        L = 26 + 10 + n * 24
        return {'x': -10.0, 'v': 0.0, 'vmax': random.uniform(26, 36), 'kind': kind, 'body': body, 'cars': cars,
                'len': L, 'state': 'run', 'dwell': 0.0, 'wheel': 0.0, 'chuff': 0.0, 'stopped_once': False}

    def update(self, dt, energy):
        super().update(dt, energy)
        w, h, ty = self.w, self.h, self.ty
        boost = 1 + energy * 0.8
        if signals.cmd and signals.cmd is not self.last_cmd:
            self.last_cmd = signals.cmd
            self.toot = 1.0
        self.toot = max(0.0, self.toot - dt)
        self.spawn_t -= dt
        if self.spawn_t <= 0 and len(self.trains) < 2:
            if not self.trains or self.trains[-1]['x'] - self.trains[-1]['len'] > w * 0.5:
                self.trains.append(self.new_train())
            self.spawn_t = random.uniform(4, 10)
        for tr in self.trains:
            front = tr['x']
            if tr['state'] == 'run':
                if tr['kind'] == 'passenger' and not tr['stopped_once'] and front > self.stop_x - 40:
                    tr['state'] = 'brake'
                tr['v'] = min(tr['vmax'] * boost, tr['v'] + 12 * dt)
            elif tr['state'] == 'brake':
                d = self.stop_x - front
                tr['v'] = max(2.0, min(tr['v'], d * 0.9))
                if d < 0.5:
                    tr['v'] = 0
                    tr['state'] = 'dwell'
                    tr['dwell'] = 5.0
                    tr['stopped_once'] = True
            elif tr['state'] == 'dwell':
                tr['dwell'] -= dt
                for p in self.people:
                    if p[2] == 'wait' and tr['dwell'] < 4:
                        p[2] = 'board'
                if tr['dwell'] <= 0:
                    tr['state'] = 'run'
                    for p in self.people:
                        if p[2] == 'gone':
                            p[2] = 'arrive'
                            p[0] = self.stop_x - 30
            tr['x'] += tr['v'] * dt
            tr['wheel'] += tr['v'] * dt / 3.0
            tr['chuff'] -= dt * max(0.3, tr['v'] / 8)
            if tr['v'] > 0.5 and tr['chuff'] <= 0 and front < self.tunnel_x:
                tr['chuff'] = 1.0
                self.puffs.append([front - 8, ty - 22, 2.0, 1.0, -tr['v'] * 0.3])
            if self.toot > 0.9 and front < self.tunnel_x:
                self.puffs.append([front - 12, ty - 24, 3.0, 1.2, 0.0])
        self.trains = [t for t in self.trains if t['x'] - t['len'] < w + 20]
        for p in self.puffs:
            p[0] += (p[4] + 3) * dt
            p[1] -= 9 * dt
            p[2] += 3 * dt
            p[3] -= dt * 0.4
        self.puffs = [p for p in self.puffs if p[3] > 0][-120:]
        # passengers
        for p in self.people:
            if p[2] == 'board':
                p[0] += (self.stop_x - 30 - p[0]) * min(1, dt * 1.5)
                if abs(self.stop_x - 30 - p[0]) < 2:
                    p[2] = 'gone'
            elif p[2] == 'arrive':
                p[0] -= 12 * dt
                if p[0] < self.station[0] + 6:
                    p[2] = 'wait'
                    p[0] = random.uniform(self.station[0] + 8, self.station[1] - 10)
        for c in self.cows:
            c[1] += dt
            c[3] = max(0.0, c[3] - dt)
            if random.random() < dt * 0.05:
                c[3] = 1.5
            if random.random() < dt * 0.2:
                c[2] = -c[2]
            c[0] += c[2] * 1.5 * dt
        for c in self.clouds:
            c[0] = (c[0] + 4 * c[2] * dt) % (w + 60)
        if random.random() < dt * 0.05 and not self.birds:
            self.birds = [[-10 - i * 6, h * 0.2 + random.uniform(-8, 8), random.random() * 6] for i in range(4)]
        for b in self.birds:
            b[0] += 20 * dt
        self.birds = [b for b in self.birds if b[0] < w + 10]

    def crossing_closed(self):
        for tr in self.trains:
            if tr['x'] > self.crossing_x - 70 and tr['x'] - tr['len'] < self.crossing_x + 10:
                return True
        return False

    def draw(self, surf, first):
        w, h, ty = self.w, self.h, self.ty
        day, hour, sr, ss = daylight()
        top, bot, dusk = sky_colors(day)
        surf.blit(gradient(w, h, top, bot, self.cache, 'sky'), (0, 0))
        if day < 0.4:
            for x, y, tw in self.stars:
                v = max(0, min(255, int(255 * (1 - day / 0.4) * (0.5 + 0.5 * math.sin(self.t * 2 + tw * 30)))))
                surf.fill((v, v, v), (int(x), int(y), 1, 1))
        else:
            f = (hour - sr) / max(0.1, ss - sr)
            pygame.draw.circle(surf, _lerp((255, 240, 170), (255, 150, 70), dusk),
                               (int(w * (0.1 + 0.8 * f)), int(ty - math.sin(max(0, min(1, f)) * math.pi) * ty * 0.8)), max(4, h // 24))
        cl = _lerp((60, 60, 80), (255, 255, 255), day)
        for x, y, s in self.clouds:
            for i in range(4):
                pygame.draw.circle(surf, cl, (int(x - 30 + i * 7 * s), int(y + (i % 2) * 2)), int(5 * s + (i % 2) * 2))
        for b in self.birds:
            up = int(math.sin(self.t * 9 + b[2]) > 0)
            surf.fill((30, 30, 40), (int(b[0]), int(b[1]), 1, 1))
            surf.fill((30, 30, 40), (int(b[0]) - 1, int(b[1]) - up, 1, 1))
            surf.fill((30, 30, 40), (int(b[0]) + 1, int(b[1]) - up, 1, 1))
        # hills, trees
        hill_c = _lerp((20, 40, 30), (90, 160, 80), day)
        far_c = _lerp(hill_c, bot, 0.45)
        for x in range(w):
            surf.fill(far_c, (x, self.hill[x] - 8, 1, 4))
            surf.fill(hill_c, (x, self.hill[x] - 4, 1, ty - self.hill[x] + 4))
        tree_c = _lerp((10, 25, 15), (40, 110, 50), day)
        for tx, s in self.trees:
            if self.river[0] - 6 < tx < self.river[1] + 6:
                continue
            y = int(self.hill[int(tx) % w])
            pygame.draw.circle(surf, tree_c, (int(tx), y - int(5 * s)), int(4 * s))
            surf.fill(_lerp((30, 20, 10), (100, 60, 30), day), (int(tx), y - int(2 * s), 1, int(3 * s)))
        # windmill
        mx, my = self.mill_x, self.mill_y
        mc = _lerp((60, 55, 50), (230, 220, 200), day)
        pygame.draw.polygon(surf, mc, [(mx - 4, my + 20), (mx + 4, my + 20), (mx + 2, my), (mx - 2, my)])
        for i in range(4):
            a = self.t * 1.5 + i * math.pi / 2
            ex, ey = mx + math.cos(a) * 12, my + math.sin(a) * 12
            pygame.draw.line(surf, _lerp((40, 30, 20), (120, 80, 50), day), (mx, my), (ex, ey))
            pygame.draw.line(surf, mc, ((mx + ex) / 2, (my + ey) / 2), (ex, ey), 2)
        # meadow, river, road
        meadow = _lerp((15, 35, 20), (100, 180, 80), day)
        surf.fill(meadow, (0, ty, w, h - ty))
        r0, r1 = self.river
        water = _lerp((10, 20, 50), (70, 140, 220), day)
        surf.fill(water, (r0, ty, r1 - r0, h - ty))
        for i in range(10):
            yy = ty + 4 + i * (h - ty) // 10
            surf.fill(_lerp(water, (255, 255, 255), 0.4), (r0 + int((self.t * 8 + i * 13) % (r1 - r0)), yy, 4, 1))
        cx = self.crossing_x
        road = _lerp((30, 30, 35), (110, 110, 115), day)
        pygame.draw.polygon(surf, road, [(cx - 6, ty), (cx + 6, ty), (cx + 22, h), (cx - 22, h)])
        # cows
        for x, ph, d, moo in self.cows:
            cow = sprite(["..kww.", "wwkkww", "wkwwkw", "w.ww.w"] if int(ph * 2) % 2 else ["..kww.", "wwkkww", "wkwwkw", ".w..w."],
                         {'w': _lerp((60, 60, 60), (245, 245, 245), day), 'k': (30, 30, 30)})
            if d < 0:
                cow = pygame.transform.flip(cow, True, False)
            surf.blit(cow, (int(x), ty + 10))
            if moo > 0:
                bubble(surf, int(x) + 3, ty + 10, text='MOO')
        # station
        s0, s1 = self.station
        plat = _lerp((60, 60, 65), (170, 165, 160), day)
        surf.fill(plat, (s0, ty - 3, s1 - s0, 3))
        bx = s0 + 6
        surf.fill(_lerp((50, 30, 25), (190, 110, 80), day), (bx, ty - 22, 26, 19))
        pygame.draw.polygon(surf, _lerp((40, 15, 15), (150, 50, 40), day), [(bx - 3, ty - 22), (bx + 29, ty - 22), (bx + 13, ty - 30)])
        lit = day < 0.5
        win = (255, 220, 130) if lit else (120, 170, 220)
        surf.fill(win, (bx + 3, ty - 17, 5, 5))
        surf.fill(win, (bx + 18, ty - 17, 5, 5))
        surf.fill((240, 240, 240), (bx + 11, ty - 20, 4, 4))
        a = (hour % 12) / 12 * 2 * math.pi
        surf.fill((20, 20, 20), (bx + 12 + int(math.sin(a) * 1.5), ty - 19 - int(math.cos(a) * 1.5), 1, 1))
        lx = s1 - 4
        surf.fill((30, 30, 35), (lx, ty - 18, 1, 15))
        if lit:
            surf.fill((255, 230, 150), (lx - 1, ty - 19, 3, 2))
            glow(surf, lx, ty - 14, 8, (60, 50, 20))
        for x, col, st in self.people:
            if st in ('wait', 'board', 'arrive'):
                img = Person.img('walk1' if st != 'wait' and int(self.t * 8) % 2 else 'stand', -1 if st == 'arrive' else 1, col)
                surf.blit(img, (int(x), ty - 3 - img.get_height()))
        # signal
        sx = s0 - 10
        surf.fill((30, 30, 35), (sx, ty - 20, 1, 20))
        stopped = any(t['state'] == 'dwell' for t in self.trains)
        surf.fill((255, 40, 40) if stopped else (40, 255, 80), (sx - 1, ty - 22, 3, 3))
        # track
        rail = _lerp((40, 40, 45), (120, 110, 100), day)
        sleeper = _lerp((30, 20, 15), (100, 70, 45), day)
        for x in range(0, w, 4):
            surf.fill(sleeper, (x, ty + 1, 3, 2))
        surf.fill(rail, (0, ty, w, 1))
        # bridge over the river
        bc = _lerp((40, 30, 30), (150, 70, 50), day)
        surf.fill(bc, (r0 - 4, ty + 2, r1 - r0 + 8, 2))
        for i in range(r0 - 2, r1 + 2, 6):
            pygame.draw.line(surf, bc, (i, ty + 3), (i + 3, ty + 9))
            pygame.draw.line(surf, bc, (i + 6, ty + 3), (i + 3, ty + 9))
        # crossing barrier
        closed = self.crossing_closed()
        surf.fill((240, 240, 240), (cx + 8, ty - 10, 1, 10))
        if closed:
            surf.fill((230, 40, 40), (cx - 10, ty - 8, 18, 1))
            if int(self.t * 3) % 2:
                surf.fill((255, 40, 40), (cx + 7, ty - 12, 1, 1))
            else:
                surf.fill((255, 40, 40), (cx + 9, ty - 12, 1, 1))
            # a waiting car
            surf.fill((60, 120, 200), (cx - 6, ty + 8, 12, 4))
            surf.fill((150, 200, 240), (cx - 4, ty + 6, 8, 2))
            if lit:
                surf.fill((255, 250, 200), (cx - 5, ty + 9, 2, 1))
                surf.fill((255, 250, 200), (cx + 3, ty + 9, 2, 1))
        else:
            pygame.draw.line(surf, (230, 40, 40), (cx + 8, ty - 10), (cx + 6, ty - 26))
        # trains
        for tr in self.trains:
            self._train(surf, tr, lit)
        # smoke
        for p in self.puffs:
            v = max(0, min(255, int(160 + 90 * min(1, p[3]))))
            vv = _lerp((60, 60, 70), (v, v, v), day)
            pygame.draw.circle(surf, vv, (int(p[0]), int(p[1])), int(p[2]))
        # tunnel portal (in front of trains)
        tx = self.tunnel_x
        hillc = _lerp((20, 40, 30), (80, 140, 70), day)
        clip = surf.get_clip()
        surf.set_clip(pygame.Rect(0, 0, w, ty + 1))
        pygame.draw.ellipse(surf, hillc, (tx - 6, ty - 40, w - tx + 60, 90))
        surf.set_clip(clip)
        pygame.draw.ellipse(surf, _lerp((40, 35, 35), (130, 120, 110), day), (tx - 3, ty - 22, 20, 30))
        pygame.draw.ellipse(surf, (8, 8, 10), (tx, ty - 19, 14, 26))

    def _train(self, surf, tr, lit):
        ty = self.ty
        x = int(tr['x'])
        tx = self.tunnel_x + 6
        clip = surf.get_clip()
        surf.set_clip(pygame.Rect(0, 0, tx, self.h))
        body = tr['body']
        ang = tr['wheel']
        # locomotive (front at x, facing right)
        lx = x - 26
        surf.fill((30, 30, 35), (lx, ty - 6, 26, 3))
        surf.fill(body, (lx + 8, ty - 14, 16, 8))           # boiler
        surf.fill(tuple(min(255, c + 60) for c in body), (lx + 8, ty - 14, 16, 1))
        surf.fill((230, 190, 60), (lx + 14, ty - 14, 1, 8))
        surf.fill((230, 190, 60), (lx + 19, ty - 14, 1, 8))
        surf.fill((30, 30, 35), (lx + 20, ty - 20, 3, 6))   # chimney
        surf.fill((230, 190, 60), (lx + 14, ty - 17, 3, 3))  # dome
        surf.fill(body, (lx, ty - 18, 9, 12))                # cab
        surf.fill((30, 30, 35), (lx - 1, ty - 19, 11, 2))
        surf.fill((255, 220, 130) if lit else (150, 200, 230), (lx + 2, ty - 15, 4, 3))
        surf.fill((255, 250, 210) if lit else (220, 220, 200), (lx + 24, ty - 12, 2, 2))
        pygame.draw.polygon(surf, (40, 40, 45), [(lx + 24, ty - 4), (lx + 28, ty), (lx + 24, ty)])
        for i, wx in enumerate((lx + 6, lx + 13, lx + 20)):
            pygame.draw.circle(surf, (25, 25, 30), (wx, ty - 3), 3)
            a = ang + i * 0.7
            surf.fill((200, 200, 205), (wx + int(math.cos(a) * 2), ty - 3 + int(math.sin(a) * 2), 1, 1))
        ca = ang
        p1 = (lx + 6 + math.cos(ca) * 2, ty - 3 + math.sin(ca) * 2)
        p2 = (lx + 20 + math.cos(ca) * 2, ty - 3 + math.sin(ca) * 2)
        pygame.draw.line(surf, (200, 200, 205), p1, p2)
        # tender
        tx0 = lx - 12
        surf.fill(body, (tx0, ty - 12, 11, 7))
        surf.fill((20, 20, 20), (tx0 + 1, ty - 13, 9, 2))
        for wx in (tx0 + 3, tx0 + 8):
            pygame.draw.circle(surf, (25, 25, 30), (wx, ty - 3), 2)
        cx = tx0 - 2
        for kind, col in tr['cars']:
            cx -= 23
            if kind == 'coach':
                surf.fill(col, (cx, ty - 14, 22, 9))
                surf.fill((40, 40, 45), (cx - 1, ty - 15, 24, 2))
                for wx in range(cx + 2, cx + 20, 5):
                    surf.fill((255, 220, 130) if lit else (150, 200, 230), (wx, ty - 12, 3, 3))
            elif kind == 'logs':
                surf.fill((70, 60, 50), (cx, ty - 7, 22, 2))
                for i in range(4):
                    pygame.draw.circle(surf, (130, 85, 45), (cx + 3 + i * 5, ty - 10), 2)
                    pygame.draw.circle(surf, (130, 85, 45), (cx + 5 + i * 5, ty - 13), 2)
            elif kind == 'box':
                surf.fill(col, (cx + 1, ty - 15, 20, 9))
                for i in range(cx + 3, cx + 21, 3):
                    surf.fill(tuple(max(0, c - 40) for c in col), (i, ty - 15, 1, 9))
                surf.fill((70, 60, 50), (cx, ty - 7, 22, 2))
            else:
                pygame.draw.ellipse(surf, col, (cx + 1, ty - 14, 20, 8))
                surf.fill((70, 60, 50), (cx, ty - 7, 22, 2))
            surf.fill((30, 30, 35), (cx + 22, ty - 8, 1, 1))
            for wx in (cx + 4, cx + 18):
                pygame.draw.circle(surf, (25, 25, 30), (wx, ty - 3), 2)
        surf.set_clip(clip)


# ============================================================================ settlers
class Settlers(Background):
    name = 'settlers'
    opaque = True
    NODES = {'hq': (0.55, 0.45), 'f1': (0.40, 0.47), 'wood': (0.27, 0.58), 'forest': (0.15, 0.42),
             'farm': (0.70, 0.66), 'mill': (0.84, 0.56), 'stone': (0.82, 0.28), 'bake': (0.66, 0.30),
             'fish': (0.40, 0.76)}
    EDGES = [('hq', 'f1'), ('f1', 'wood'), ('wood', 'forest'), ('hq', 'farm'), ('farm', 'mill'), ('hq', 'bake'),
             ('bake', 'stone'), ('f1', 'fish')]
    WARE = {'log': (130, 85, 45), 'stone': (160, 160, 165), 'fish': (120, 180, 230), 'wheat': (230, 200, 70),
            'flour': (245, 245, 235), 'bread': (200, 130, 60), 'plank': (210, 170, 110)}
    ROUTES = {'wood': ('log', 'hq'), 'stone': ('stone', 'hq'), 'fish': ('fish', 'hq'), 'farm': ('wheat', 'mill'),
              'mill': ('flour', 'bake'), 'bake': ('bread', 'hq')}
    ROOF = {'hq': (40, 80, 200), 'wood': (120, 70, 30), 'forest': (60, 120, 40), 'farm': (200, 150, 50),
            'mill': (200, 200, 200), 'stone': (110, 110, 120), 'bake': (190, 70, 40), 'fish': (60, 140, 200)}

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.pos = {k: (int(x * w), int(y * h)) for k, (x, y) in self.NODES.items()}
        self.adj = {k: [] for k in self.NODES}
        for a, b in self.EDGES:
            self.adj[a].append(b)
            self.adj[b].append(a)
        self.queues = {k: [] for k in self.NODES}
        self.carriers = {e: {'edge': e, 'p': 0.5, 'ware': None, 'target': None, 'walk': 0.0} for e in self.EDGES}
        self.prod_t = {k: random.uniform(2, 8) for k in self.ROUTES}
        rng = random.Random(9)
        self.trees = [{'x': rng.uniform(0.04, 0.32) * w, 'y': rng.uniform(0.2, 0.62) * h, 'g': rng.uniform(0.5, 1.0)}
                      for _ in range(26)]
        self.fields = [{'x': self.pos['farm'][0] + dx * 9 - 18, 'y': self.pos['farm'][1] + 8 + dy * 6, 'g': rng.random()}
                       for dx in range(4) for dy in range(2)]
        self.cutter = {'x': float(self.pos['wood'][0]), 'y': float(self.pos['wood'][1]), 'state': 'home', 'tree': None, 't': 0.0}
        self.forester = {'x': float(self.pos['forest'][0]), 'y': float(self.pos['forest'][1]), 'state': 'home', 'tgt': None, 't': 0.0}
        self.smoke = []
        self.grass = self._grass()
        self.last_cmd = None
        self.flags_wave = 0.0
        self.sites = []

    def _grass(self):
        w, h = self.w, self.h
        g = np.random.default_rng(4).random((w, h))
        base = np.array([86, 150, 60], np.float32)
        img = base[None, None, :] * (0.88 + 0.2 * g[..., None])
        # lake bottom left, mountains top right
        X, Y = np.meshgrid(np.arange(w), np.arange(h), indexing='ij')
        lake = ((X - w * 0.25) / (w * 0.22)) ** 2 + ((Y - h * 0.95) / (h * 0.18)) ** 2 < 1
        img[lake] = np.array([60, 120, 200]) * (0.9 + 0.1 * g[lake][:, None])
        shore = (((X - w * 0.25) / (w * 0.235)) ** 2 + ((Y - h * 0.95) / (h * 0.2)) ** 2 < 1) & ~lake
        img[shore] = (220, 200, 140)
        edge = 1 + 0.12 * np.sin(X * 0.35) * np.cos(Y * 0.4)
        rock = ((X - w * 0.95) / (w * 0.26)) ** 2 + ((Y + h * 0.02) / (h * 0.24)) ** 2 < edge
        img[rock] = np.array([128, 122, 112]) * (0.85 + 0.25 * g[rock][:, None])
        self.lake = lake
        s = pygame.Surface((w, h))
        pygame.surfarray.blit_array(s, np.clip(img, 0, 255).astype(np.uint8))
        rng = random.Random(3)
        peaks = sorted(((rng.uniform(0.76, 0.99) * w, rng.uniform(0.07, 0.17) * h, rng.uniform(0.04, 0.07) * w)
                        for _ in range(6)), key=lambda p: p[1])
        for px, py, pw in peaks:
            ph = pw * 1.3
            pygame.draw.polygon(s, (150, 145, 135), [(px - pw, py + ph * 0.5), (px, py - ph * 0.5), (px, py + ph * 0.5)])
            pygame.draw.polygon(s, (95, 90, 85), [(px, py - ph * 0.5), (px + pw, py + ph * 0.5), (px, py + ph * 0.5)])
            sk = 0.35
            pygame.draw.polygon(s, (245, 245, 250), [(px - pw * sk, py - ph * 0.5 + ph * sk), (px, py - ph * 0.5),
                                                     (px + pw * sk, py - ph * 0.5 + ph * sk), (px, py - ph * 0.5 + ph * sk * 0.8)])
        return s

    def route(self, a, b):
        prev = {a: None}
        q = [a]
        while q:
            n = q.pop(0)
            if n == b:
                break
            for m in self.adj[n]:
                if m not in prev:
                    prev[m] = n
                    q.append(m)
        path, n = [], b
        while n is not None:
            path.append(n)
            n = prev.get(n)
        return path[::-1]

    def update(self, dt, energy):
        speed = 1 + energy * 2.5
        dt2 = dt * speed
        super().update(dt, energy)
        if signals.cmd and signals.cmd is not self.last_cmd:
            self.last_cmd = signals.cmd
            if signals.cmd[0] == 0:
                # success: a new building site appears and gets built
                n = random.choice(list(self.NODES))
                x, y = self.pos[n]
                self.sites.append({'x': x + random.randint(-25, 25), 'y': y + random.randint(-18, 18), 'p': 0.0})
                self.flags_wave = 3.0
        self.flags_wave = max(0.0, self.flags_wave - dt)
        for s in self.sites:
            s['p'] = min(1.0, s['p'] + dt2 * 0.08)
        self.sites = self.sites[-8:]
        # production
        for node, (ware, dest) in self.ROUTES.items():
            if node == 'wood':
                continue   # the woodcutter produces logs by actually chopping trees
            if node == 'farm':
                ripe = [f for f in self.fields if f['g'] >= 1]
                if ripe and random.random() < dt2 * 0.3:
                    random.choice(ripe)['g'] = 0.0
                    self._ware(node, ware, dest)
                continue
            if node in ('mill', 'bake'):
                if self.prod_t.get(node + '_in', 0) > 0:
                    self.prod_t[node + '_in'] -= 1
                    self._ware(node, ware, dest)
                    self.smoke.append([self.pos[node][0] + 3, self.pos[node][1] - 14, 1.5, 1.0])
                continue
            self.prod_t[node] -= dt2
            if self.prod_t[node] <= 0:
                self.prod_t[node] = random.uniform(6, 12)
                self._ware(node, ware, dest)
                self.smoke.append([self.pos[node][0] + 3, self.pos[node][1] - 14, 1.5, 1.0])
        for f in self.fields:
            f['g'] = min(1.0, f['g'] + dt2 * 0.03)
        for t in self.trees:
            t['g'] = min(1.0, t['g'] + dt2 * 0.01)
        self._woodcutter(dt2)
        self._forester(dt2)
        # carriers
        for e, c in self.carriers.items():
            a, b = e
            pa, pb = self.pos[a], self.pos[b]
            if c['ware'] is None and c['target'] is None:
                for end, other in ((a, b), (b, a)):
                    q = self.queues[end]
                    for wv in q:
                        if wv['route'][wv['i'] + 1] == other:
                            c['target'] = end
                            break
                    if c['target']:
                        break
            if c['target'] is not None:
                goal = 0.0 if c['target'] == a else 1.0
                d = goal - c['p']
                step = dt2 * 20 / max(10, math.dist(pa, pb))
                if abs(d) <= step:
                    c['p'] = goal
                    end = c['target']
                    if c['ware'] is None:
                        other = b if end == a else a
                        q = self.queues[end]
                        for wv in q:
                            if wv['route'][wv['i'] + 1] == other:
                                q.remove(wv)
                                c['ware'] = wv
                                c['target'] = other
                                break
                        else:
                            c['target'] = None
                    else:
                        wv = c['ware']
                        wv['i'] += 1
                        c['ware'] = None
                        c['target'] = None
                        if wv['i'] < len(wv['route']) - 1:
                            self.queues[end].append(wv)
                        else:
                            self._arrive(end, wv)
                else:
                    c['p'] += step if d > 0 else -step
                    c['walk'] += dt2
            else:
                c['walk'] = 0.0
                c['p'] += (0.5 - c['p']) * min(1, dt2 * 0.5)
        for p in self.smoke:
            p[1] -= 6 * dt
            p[0] += 2 * dt
            p[2] += 1.5 * dt
            p[3] -= dt * 0.4
        self.smoke = [p for p in self.smoke if p[3] > 0][-80:]

    def _ware(self, node, ware, dest):
        if len(self.queues[node]) > 6:
            return
        self.queues[node].append({'type': ware, 'route': self.route(node, dest), 'i': 0})

    def _arrive(self, node, wv):
        if node == 'mill' and wv['type'] == 'wheat':
            self.prod_t['mill_in'] = self.prod_t.get('mill_in', 0) + 1
        if node == 'bake' and wv['type'] == 'flour':
            self.prod_t['bake_in'] = self.prod_t.get('bake_in', 0) + 1

    def _walk(self, p, tx, ty, dt, sp=16):
        d = math.dist((p['x'], p['y']), (tx, ty))
        if d < 1:
            return True
        k = min(1, sp * dt / d)
        p['x'] += (tx - p['x']) * k
        p['y'] += (ty - p['y']) * k
        return False

    def _woodcutter(self, dt):
        c = self.cutter
        hx, hy = self.pos['wood']
        if c['state'] == 'home':
            c['t'] -= dt
            grown = [t for t in self.trees if t['g'] >= 1]
            if c['t'] <= 0 and grown:
                c['tree'] = min(grown, key=lambda t: math.dist((t['x'], t['y']), (hx, hy)))
                c['state'] = 'go'
        elif c['state'] == 'go':
            t = c['tree']
            if t not in self.trees:
                c['state'] = 'back'
            elif self._walk(c, t['x'] + 3, t['y'], dt):
                c['state'] = 'chop'
                c['t'] = 3.0
        elif c['state'] == 'chop':
            c['t'] -= dt
            if c['t'] <= 0:
                if c['tree'] in self.trees:
                    self.trees.remove(c['tree'])
                c['state'] = 'back'
        elif c['state'] == 'back':
            if self._walk(c, hx, hy, dt):
                c['state'] = 'home'
                c['t'] = 2.0
                self._ware('wood', 'log', 'hq')

    def _forester(self, dt):
        f = self.forester
        hx, hy = self.pos['forest']
        if f['state'] == 'home':
            f['t'] -= dt
            if f['t'] <= 0 and len(self.trees) < 30:
                f['tgt'] = (hx + random.uniform(-50, 40), hy + random.uniform(-30, 50))
                f['state'] = 'go'
        elif f['state'] == 'go':
            if self._walk(f, *f['tgt'], dt):
                f['state'] = 'plant'
                f['t'] = 2.0
        elif f['state'] == 'plant':
            f['t'] -= dt
            if f['t'] <= 0:
                self.trees.append({'x': f['tgt'][0], 'y': f['tgt'][1], 'g': 0.05})
                f['state'] = 'back'
        elif f['state'] == 'back':
            if self._walk(f, hx, hy, dt):
                f['state'] = 'home'
                f['t'] = 4.0

    # ------------------------------------------------------------ draw
    def draw(self, surf, first):
        surf.blit(self.grass, (0, 0))
        # lake shimmer
        if int(self.t * 2) % 2 == 0:
            pass
        # roads
        for a, b in self.EDGES:
            pygame.draw.line(surf, (170, 140, 90), self.pos[a], self.pos[b], 3)
        for a, b in self.EDGES:
            pygame.draw.line(surf, (195, 165, 110), self.pos[a], self.pos[b], 1)
        # fields
        for f in self.fields:
            g = f['g']
            col = _lerp((90, 70, 40), _lerp((90, 170, 60), (230, 200, 70), max(0, g * 1.4 - 0.4)), min(1, g * 2))
            surf.fill(col, (f['x'], f['y'], 8, 5))
            if g > 0.6:
                sway = int(math.sin(self.t * 2 + f['x']) > 0.3)
                for i in range(0, 8, 2):
                    surf.fill(_lerp(col, (255, 240, 150), 0.3), (f['x'] + i + sway, f['y'] - 1, 1, 1))
        # trees
        for t in sorted(self.trees, key=lambda t: t['y']):
            g = t['g']
            r = max(1, int(1 + g * 4))
            surf.fill((90, 60, 30), (int(t['x']), int(t['y']) - r, 1, r + 1))
            pygame.draw.circle(surf, (30 + int(30 * g), 100 + int(20 * g), 40), (int(t['x']), int(t['y']) - r - 1), r)
            if r > 2:
                surf.fill((70, 150, 60), (int(t['x']) - 1, int(t['y']) - 2 * r, 2, 1))
        # building sites
        for s in self.sites:
            x, y, p = int(s['x']), int(s['y']), s['p']
            surf.fill((160, 120, 70), (x - 6, y - 1, 12, 2))
            hgt = int(9 * p)
            if hgt:
                surf.fill((210, 190, 150), (x - 5, y - hgt, 10, hgt))
            if p >= 1:
                pygame.draw.polygon(surf, (180, 60, 40), [(x - 7, y - 9), (x + 7, y - 9), (x, y - 15)])
            else:
                surf.fill((230, 230, 230), (x + 6, y - 12, 1, 12))
        # buildings
        for n, (x, y) in self.pos.items():
            if n == 'f1':
                continue
            roof = self.ROOF[n]
            big = n == 'hq'
            bw, bh = (16, 12) if big else (11, 8)
            bx, by = x - bw // 2, y - bh - 3
            surf.fill((40, 30, 20), (bx + 1, by + 1, bw, bh))
            surf.fill((215, 195, 160), (bx, by, bw, bh))
            pygame.draw.polygon(surf, roof, [(bx - 2, by), (bx + bw + 2, by), (bx + bw // 2, by - (8 if big else 6))])
            surf.fill((80, 50, 30), (x - 1, by + bh - 4, 3, 4))
            if big:
                for tx in (bx - 2, bx + bw - 1):
                    surf.fill((200, 190, 170), (tx, by - 6, 3, bh + 6))
                    surf.fill(roof, (tx - 1, by - 8, 5, 2))
                surf.fill((40, 40, 40), (x, by - 16, 1, 8))
                wave = math.sin(self.t * (8 if self.flags_wave else 3))
                surf.fill((220, 40, 40), (x + 1, by - 16 + int(wave), 5, 3))
            if n == 'mill':
                cx, cy = x, by - 3
                for i in range(4):
                    a = self.t * (1 + self.prod_t.get('mill_in', 0) * 0.5) + i * math.pi / 2
                    pygame.draw.line(surf, (240, 240, 240), (cx, cy), (cx + math.cos(a) * 9, cy + math.sin(a) * 9), 2)
        # flags & queued wares
        for n, (x, y) in self.pos.items():
            surf.fill((40, 40, 40), (x, y - 6, 1, 6))
            surf.fill((40, 80, 220), (x + 1, y - 6, 3, 2))
            for i, wv in enumerate(self.queues[n][:6]):
                surf.fill(self.WARE[wv['type']], (x - 4 + (i % 3) * 3, y + 1 + (i // 3) * 3, 2, 2))
        for p in self.smoke:
            v = max(0, min(255, int(150 + 90 * min(1, p[3]))))
            pygame.draw.circle(surf, (v, v, v), (int(p[0]), int(p[1])), int(p[2]))
        # people
        for e, c in self.carriers.items():
            a, b = e
            pa, pb = self.pos[a], self.pos[b]
            x = pa[0] + (pb[0] - pa[0]) * c['p']
            y = pa[1] + (pb[1] - pa[1]) * c['p']
            face = 1 if (pb[0] - pa[0]) * (1 if c['target'] == b else -1) >= 0 else -1
            self._settler(surf, x, y, (230, 200, 60), c['walk'], face, c['ware'])
        cu = self.cutter
        self._settler(surf, cu['x'], cu['y'], (90, 160, 70), 0.2 if cu['state'] in ('go', 'back') else 0, 1, None)
        if cu['state'] == 'chop':
            a = math.sin(self.t * 12)
            pygame.draw.line(surf, (150, 150, 160), (cu['x'] + 2, cu['y'] - 5), (cu['x'] + 4, cu['y'] - 5 + a * 3))
        fo = self.forester
        self._settler(surf, fo['x'], fo['y'], (60, 120, 50), 0.2 if fo['state'] in ('go', 'back') else 0, 1, None)

    def _settler(self, surf, x, y, col, walk, face, ware):
        x, y = int(x), int(y)
        step = int(walk * 8) % 2 if walk else 0
        surf.fill((250, 200, 160), (x, y - 6, 2, 2))
        surf.fill(col, (x, y - 4, 2, 3))
        surf.fill((60, 50, 40), (x + (step if face > 0 else -step), y - 1, 1, 1))
        surf.fill((60, 50, 40), (x + 1 - (step if face > 0 else -step), y - 1, 1, 1))
        surf.fill((120, 60, 30), (x - 1, y - 7, 4, 1))
        if ware:
            surf.fill(self.WARE[ware['type']], (x, y - 9, 2, 2))


# ============================================================================ disco city
class DiscoCity(Background):
    name = 'discocity'
    opaque = True
    SIGNS = ['DISCO', 'ARCADE', 'HOTEL', 'VIDEO', 'DANCE', 'NEON', '80S', 'SYNTH']

    def resize(self, w, h):
        super().resize(w, h)
        self.cache = {}
        self.hz = int(h * 0.58)
        rng = random.Random(11)
        self.buildings = []
        x = 0
        while x < w:
            bw = rng.randint(8, 22)
            mid = abs(x + bw / 2 - w / 2) / (w / 2)
            bh = int(h * rng.uniform(0.06, 0.16 + 0.22 * mid))
            self.buildings.append((x, bw, bh, rng.choice([(255, 60, 200), (60, 230, 255), (255, 200, 60)])))
            x += bw + rng.randint(0, 3)
        self.windows = []
        for bx, bw, bh, col in self.buildings:
            for wx in range(bx + 2, bx + bw - 1, 3):
                for wy in range(self.hz - bh + 3, self.hz - 2, 3):
                    if rng.random() < 0.35:
                        self.windows.append((wx, wy, col, rng.random()))
        self.signs = []
        for i in range(5):
            b = rng.choice(self.buildings)
            self.signs.append({'x': b[0] + 1, 'y': self.hz - b[2] - 8, 'text': rng.choice(self.SIGNS),
                               'col': rng.choice([(255, 50, 180), (50, 230, 255), (255, 230, 60), (120, 255, 120)]),
                               'flick': rng.random()})
        self.stars = [(rng.uniform(0, w), rng.uniform(0, self.hz * 0.8), rng.random()) for _ in range(90)]
        self.eq = np.zeros(32, np.float32)
        self.spots = [(rng.uniform(0, 6.28), rng.uniform(-0.9, 0.9), rng.choice([(255, 60, 200), (60, 230, 255), (255, 255, 120), (140, 255, 140)]))
                      for _ in range(40)]
        self.sun = self._sun()
        # driving: lateral car position (road half-width = 1), steering, boost
        self.carx = 0.0
        self.carv = 0.0
        self.camx = 0.0
        self.bend = 0.0
        self.dist = 0.0
        self.boost = 0.0
        self.last_boost = signals.boost
        self.flames = []
        self.streaks = []
        self.energy_now = 0.0

    def steer_input(self):
        d = 0
        now = time.time()
        if now - signals.left < 0.12:
            d -= 1
        if now - signals.right < 0.12:
            d += 1
        try:                                     # held arrow keys (window focused)
            if pygame.key.get_focused():
                k = pygame.key.get_pressed()
                mods = pygame.key.get_mods()
                if not mods & (pygame.KMOD_CTRL | pygame.KMOD_ALT):
                    d = max(-1, min(1, d - k[pygame.K_LEFT] + k[pygame.K_RIGHT])) if (k[pygame.K_LEFT] or k[pygame.K_RIGHT]) else d
        except Exception:
            pass
        return d

    def _sun(self):
        r = int(min(self.w, self.h) * 0.30)
        s = pygame.Surface((2 * r, r), pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        for y in range(r):
            k = y / r
            col = (255, int(230 - 160 * k), int(90 + 110 * k), 255)
            dx = int(math.sqrt(max(0, r * r - (r - y) ** 2)))
            band = int(1 + k * 4)
            if k > 0.45 and (y // band) % 3 == 0:
                continue
            pygame.draw.line(s, col, (r - dx, y), (r + dx, y))
        return s

    def update(self, dt, energy):
        super().update(dt, energy)
        e = min(2.0, energy + (0.6 if signals.recent(signals.typing, 0.5) else 0))
        target = np.abs(np.sin(np.arange(32) * 0.7 + self.t * (3 + e * 4)) * np.sin(np.arange(32) * 0.23 + self.t * 1.3)) * (0.35 + e * 0.5)
        target += np.random.uniform(0, 0.15 + e * 0.2, 32)
        self.eq += (target.astype(np.float32) - self.eq) * min(1, dt * 12)
        self.energy_now = e
        # ---- driving
        if signals.boost != self.last_boost:
            self.last_boost = signals.boost
            self.boost = 1.0
            self.eq = np.minimum(1.3, self.eq + 0.6)
        self.boost = max(0.0, self.boost - dt * 0.45)
        speed = 0.7 + e * 0.6 + self.boost * 3.0
        self.speed = speed
        self.dist += speed * dt
        d = self.steer_input()
        grip = 6.0
        self.carv += (d * (2.2 + self.boost) - self.carv) * min(1, dt * grip)
        self.carx += self.carv * dt
        if abs(self.carx) > 1.25:                 # bump back from the kerb
            self.carx = math.copysign(1.25, self.carx)
            self.carv *= -0.4
        if d == 0:
            self.carx += (-self.carx * 0.15) * dt  # gently drift back to the lane
        self.camx += (self.carx * 0.55 - self.camx) * min(1, dt * 3)
        self.bend += (self.carv * 0.25 - self.bend) * min(1, dt * 2.5)
        self.lean = self.carv / 2.2
        # exhaust flames & speed streaks while boosting
        if self.boost > 0.05:
            for side in (-1, 1):
                for _ in range(2):
                    self.flames.append([side, random.uniform(-1, 1), 0.0, random.uniform(0.15, 0.35) * (0.5 + self.boost)])
            if random.random() < self.boost * dt * 60:
                a = random.uniform(0, math.tau)
                self.streaks.append([a, 0.05, random.uniform(1.5, 3.0)])
        for f in self.flames:
            f[2] += dt
        self.flames = [f for f in self.flames if f[2] < f[3]][-80:]
        for st in self.streaks:
            st[1] += dt * st[2] * (1 + self.boost * 2)
        self.streaks = [st for st in self.streaks if st[1] < 1.2]

    def draw(self, surf, first):
        w, h, hz = self.w, self.h, self.hz
        surf.blit(gradient(w, hz, (14, 2, 34), (190, 40, 120), self.cache, 'sky'), (0, 0))
        for x, y, tw in self.stars:
            v = int(200 * (0.6 + 0.4 * math.sin(self.t * 2 + tw * 40)))
            surf.fill((v, v, min(255, v + 40)), (int(x), int(y), 1, 1))
        sun = self.sun
        glow(surf, w // 2, hz - sun.get_height() // 2, sun.get_height() + 8, (70, 20, 50))
        surf.blit(sun, (w // 2 - sun.get_width() // 2, hz - sun.get_height() - int(h * 0.04)))
        # skyline
        for bx, bw, bh, col in self.buildings:
            surf.fill((24, 6, 40), (bx, hz - bh, bw, bh))
            surf.fill(tuple(c // 5 for c in col), (bx, hz - bh, bw, 1))
        for i, (x, y, col, p) in enumerate(self.windows):
            if (int(self.t * 0.7 + p * 10) + i) % 11:
                k = 0.45 + 0.35 * p
                surf.fill((int(col[0] * k), int(col[1] * k), int(col[2] * k)), (x, y, 1, 1))
        # neon signs with flicker + glow
        for s in self.signs:
            on = not (math.sin(self.t * 13 + s['flick'] * 50) > 0.92 or (int(self.t * 3 + s['flick'] * 7) % 17 == 0))
            col = s['col'] if on else tuple(c // 4 for c in s['col'])
            if on:
                gc = tuple(c // 3 for c in col)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    tiny_text(surf, s['x'] + dx, s['y'] + dy, s['text'], gc)
            tiny_text(surf, s['x'], s['y'], s['text'], col)
        # equalizer on the horizon
        bw = max(2, w // 64)
        for i, v in enumerate(self.eq):
            hgt = int(v * h * 0.12)
            x = w // 2 - 16 * (bw + 1) + i * (bw + 1)
            for k in range(0, hgt, 2):
                c = _lerp((60, 230, 255), (255, 50, 180), min(1.0, k / max(1, h * 0.12)))
                surf.fill(c, (x, hz - 2 - k, bw, 1))
        # grid floor (pseudo 3D: camera follows the car sideways, the road bends with the steering)
        surf.fill((16, 0, 30), (0, hz, w, h - hz))
        bst = self.boost
        col = _lerp((255, 40, 200), (120, 230, 255), bst * 0.8)
        half = w * 0.18                                  # road half width at the bottom row
        D = h - hz

        def cx_at(y):                                    # road centre x at screen row y
            p = (y - hz) / D
            return w / 2 - self.camx * half * p + self.bend * w * 0.5 * (1 - p) ** 2

        for i in range(-22, 23):
            pygame.draw.line(surf, col, (cx_at(hz) + i * w / 44, hz), (cx_at(h) + i * w / 3.5, h))
        off = self.dist % 1
        for j in range(16):
            z = j + 1 - off
            y = hz + D * (1 / z) ** 0.9
            if hz < y < h:
                pygame.draw.line(surf, col, (0, y), (w, y))
        surf.fill(_lerp((255, 120, 220), (200, 250, 255), bst), (0, hz, w, 1))
        # road as horizontal spans
        kerb = (255, 230, 120)
        for y in range(hz + 1, h):
            p = (y - hz) / D
            c = cx_at(y)
            hw = max(1.0, 3 + half * p)
            surf.fill((30, 10, 50), (int(c - hw), y, int(hw * 2) + 1, 1))
            z = 1 / max(0.02, p) ** (1 / 0.9)            # depth of this row
            if int(z - off + 100) % 2 == 0:
                surf.fill((255, 60, 200), (int(c - hw) - 1, y, 2, 1))
                surf.fill((255, 60, 200), (int(c + hw), y, 2, 1))
                if (int(z - off + 100) // 2) % 2 == 0:
                    surf.fill(kerb, (int(c), y, max(1, int(p * 2)), 1))
        # roadside neon posts rushing past
        for j in range(10):
            z = j + 1 - (self.dist * 0.5) % 1
            p = (1 / z) ** 0.9
            y = hz + D * p
            if hz < y < h:
                c = cx_at(y)
                for side, pc in ((-1, (60, 230, 255)), (1, (255, 60, 200))):
                    x = c + side * (half * p * 1.5 + 4)
                    ph = max(2, int(p * h * 0.25))
                    surf.fill(tuple(v // 3 for v in pc), (int(x) - 1, int(y) - ph, 3, ph), special_flags=pygame.BLEND_RGB_ADD)
                    surf.fill(pc, (int(x), int(y) - ph, 1, ph))
        # speed streaks from the vanishing point
        for a, r, _ in self.streaks:
            vx, vy = cx_at(hz), hz
            x0, y0 = vx + math.cos(a) * w * r * 0.6, vy + math.sin(a) * h * r * 0.6
            x1, y1 = vx + math.cos(a) * w * (r + 0.12) * 0.6, vy + math.sin(a) * h * (r + 0.12) * 0.6
            pygame.draw.line(surf, (180, 240, 255), (x0, y0), (x1, y1))
        # the car (rear view), leaning into the turn
        lean = max(-1.0, min(1.0, getattr(self, 'lean', 0.0)))
        cy = int(h * 0.86) + int(math.sin(self.t * (6 + bst * 20)) * (0.6 + bst))
        cx = int(cx_at(cy) + (self.carx - self.camx) * half * ((cy - hz) / D))
        sh = int(round(lean * 2))                         # roof shifts toward the turn
        side = int(round(abs(lean) * 3))
        if side:                                         # visible flank
            sx = cx + 14 if lean < 0 else cx - 14 - side
            surf.fill((50, 25, 70), (sx, cy - 6, side, 7))
        glow(surf, cx, cy + 3, 16, (40, 10, 50))
        surf.fill((20, 10, 30), (cx - 14, cy - 6, 28, 8))
        surf.fill((255, 60, 200), (cx - 14, cy - 6, 28, 1))
        surf.fill((40, 20, 60), (cx - 10 + sh, cy - 10, 20, 5))
        surf.fill((90, 200, 255), (cx - 9 + sh, cy - 9, 18, 2))
        tl = (255, 40, 60) if bst < 0.05 else (255, 120, 80)
        surf.fill(tl, (cx - 13, cy - 4, 6, 2))
        surf.fill(tl, (cx + 7, cy - 4, 6, 2))
        surf.fill((120, 30, 40), (cx - 13, cy - 2, 26, 1), special_flags=pygame.BLEND_RGB_ADD)
        surf.fill((10, 5, 15), (cx - 13, cy + 2, 5, 2))
        surf.fill((10, 5, 15), (cx + 8, cy + 2, 5, 2))
        # boost flames from the exhausts
        for sd, jit, age, life in self.flames:
            k = age / life
            fx = cx + sd * 6 + int(jit * 1.5)
            fy = cy + 2 + int(k * (10 + 8 * bst))
            colf = _lerp((255, 255, 200), (255, 60, 200), k) if k < 0.5 else _lerp((255, 60, 200), (60, 20, 120), (k - 0.5) * 2)
            r = max(1, int((3 + 2 * bst) * (1 - k)))
            surf.fill(colf, (fx - r // 2, fy, r, r), special_flags=pygame.BLEND_RGB_ADD)
        if bst > 0.5 and int(self.t * 8) % 2:
            tiny_text(surf, cx - 9, cy - 18, 'BOOST', (120, 255, 255))
        # palm trees on the sides
        for px, d in ((int(w * 0.06), 1), (int(w * 0.94), -1)):
            pts = [(px + d * int(math.sin(k / 8) * 6), h - k) for k in range(0, int(h * 0.5), 2)]
            pygame.draw.lines(surf, (10, 0, 20), False, pts, 3)
            tx, tyy = pts[-1]
            for a in range(7):
                ang = -math.pi / 2 + (a - 3) * 0.55 + math.sin(self.t * 1.2 + a) * 0.05
                for k in range(16):
                    x = tx + math.cos(ang) * k * 1.8
                    y = tyy + math.sin(ang) * k * 1.8 + k * k * 0.06
                    surf.fill((10, 0, 20), (int(x), int(y), 2, 2))
        # lasers from the bottom corners
        e = getattr(self, 'energy_now', 0)
        for i, (x0, colr) in enumerate(((0, (60, 255, 120)), (w, (255, 60, 200)))):
            for k in range(3):
                ang = -math.pi / 2 + math.sin(self.t * (0.8 + e) + i * 2 + k * 0.4) * 0.9
                ex, ey = x0 + math.cos(ang) * h * 1.5, h + math.sin(ang) * h * 1.5
                pygame.draw.line(surf, tuple(c // 3 for c in colr), (x0, h), (ex, ey), 3)
                pygame.draw.line(surf, colr, (x0, h), (ex, ey), 1)
        # disco ball + light spots
        bx, by, br = w // 2, int(h * 0.09), max(6, h // 20)
        surf.fill((120, 120, 140), (bx, 0, 1, by - br))
        rot = self.t * 1.3
        for yy in range(-br, br + 1, 2):
            rr = int(math.sqrt(max(0, br * br - yy * yy)))
            for xx in range(-rr, rr + 1, 2):
                v = 0.5 + 0.5 * math.sin(xx * 0.9 + yy * 0.5 + rot * 3 + (xx * xx) * 0.05)
                c = int(110 + 145 * v)
                surf.fill((c, c, min(255, c + 30)), (bx + xx, by + yy, 2, 2))
        for a, elev, colr in self.spots:
            ang = a + rot
            if math.cos(ang) < -0.2:
                continue
            x = bx + math.sin(ang) * w * 0.6
            y = by + (elev + 1) * h * 0.5
            if 0 <= x < w and 0 <= y < h:
                surf.fill(tuple(c // 2 for c in colr), (int(x) - 1, int(y) - 1, 4, 4), special_flags=pygame.BLEND_RGB_ADD)
                surf.fill(colr, (int(x), int(y), 2, 2), special_flags=pygame.BLEND_RGB_ADD)



# ============================================================================ neon signs
# letters whose pixel shapes make poor tubes get real stroke paths (3x5 grid, (x, y) points)
TUBE_PATHS = {
    'M': [[(0, 4), (0, 0), (1, 2), (2, 0), (2, 4)]],
    'N': [[(0, 4), (0, 0), (2, 4), (2, 0)]],
    'W': [[(0, 0), (0, 4), (1, 2), (2, 4), (2, 0)]],
    'V': [[(0, 0), (0, 3), (1, 4), (2, 3), (2, 0)]],
    'K': [[(0, 0), (0, 4)], [(2, 0), (0, 2), (2, 4)]],
    'X': [[(0, 0), (2, 4)], [(2, 0), (0, 4)]],
    'Y': [[(0, 0), (1, 2), (2, 0)], [(1, 2), (1, 4)]],
    'Z': [[(0, 0), (2, 0), (0, 4), (2, 4)]],
}


def _text_strokes(text, k):
    """turn the 3x5 pixel font into tube segments (pixel centres joined)"""
    from .weather import _F
    segs = []
    x0 = 0
    for ch in text.upper():
        if ch in TUBE_PATHS:
            for path in TUBE_PATHS[ch]:
                for (ax, ay), (bx, by) in zip(path, path[1:]):
                    segs.append((((x0 + ax) * k, ay * k), ((x0 + bx) * k, by * k)))
            x0 += 4
            continue
        g = _F.get(ch, _F[' '])
        on = lambda x, y: 0 <= x < 3 and 0 <= y < 5 and g[y * 3 + x] == '#'
        for y in range(5):
            for x in range(3):
                if not on(x, y):
                    continue
                p = ((x0 + x) * k, y * k)
                if on(x + 1, y):
                    segs.append((p, ((x0 + x + 1) * k, y * k)))
                if on(x, y + 1):
                    segs.append((p, ((x0 + x) * k, (y + 1) * k)))
                for dx in (1, -1):                  # diagonal joints where there is no square path
                    if on(x + dx, y + 1) and not on(x + dx, y) and not on(x, y + 1):
                        segs.append((p, ((x0 + x + dx) * k, (y + 1) * k)))
                if not any(on(x + a, y + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b):
                    segs.append((p, (p[0] + 1, p[1])))
        x0 += 4
    return segs, (x0 - 1) * k, 4 * k


def _shape(name, k):
    """outline shapes as polylines, size about 10k x 10k"""
    S = []
    if name == 'heart':
        pts = [(5 + 4.5 * math.sin(a) ** 3, 5 - (3.6 * math.cos(a) - 1.4 * math.cos(2 * a) - 0.6 * math.cos(3 * a) - 0.3 * math.cos(4 * a)))
               for a in [i / 24 * math.tau for i in range(25)]]
        S.append([(x * k, y * k) for x, y in pts])
    elif name == 'glass':
        S.append([(1 * k, 1 * k), (9 * k, 1 * k), (5 * k, 5.5 * k), (1 * k, 1 * k)])
        S.append([(5 * k, 5.5 * k), (5 * k, 9 * k)])
        S.append([(3 * k, 9 * k), (7 * k, 9 * k)])
        S.append([(6.5 * k, 2.6 * k), (8.5 * k, -0.5 * k)])
        S.append([(7.6 * k + math.cos(i / 8 * math.tau) * 0.7 * k, 0.2 * k + math.sin(i / 8 * math.tau) * 0.7 * k) for i in range(9)])
    elif name == 'star':
        pts = []
        for i in range(11):
            r = 5 if i % 2 == 0 else 2.2
            a = -math.pi / 2 + i * math.pi / 5
            pts.append(((5 + math.cos(a) * r) * k, (5 + math.sin(a) * r) * k))
        S.append(pts)
    elif name == 'arrow':
        S.append([(0, 4 * k), (7 * k, 4 * k), (7 * k, 1.5 * k), (11 * k, 5 * k), (7 * k, 8.5 * k), (7 * k, 6 * k), (0, 6 * k), (0, 4 * k)])
    elif name == 'wave':
        S.append([(i * 0.5 * k, (3 + math.sin(i * 0.5) * 2.5) * k) for i in range(25)])
        S.append([(i * 0.5 * k, (7 + math.sin(i * 0.5 + 1.5) * 2.5) * k) for i in range(25)])
    elif name == 'note':
        S.append([(3 * k, 8 * k), (3 * k, 1 * k), (9 * k, 0), (9 * k, 7 * k)])
        S.append([(1.5 * k + math.cos(i / 10 * math.tau) * 1.5 * k, 8 * k + math.sin(i / 10 * math.tau) * 1.1 * k) for i in range(11)])
        S.append([(7.5 * k + math.cos(i / 10 * math.tau) * 1.5 * k, 7 * k + math.sin(i / 10 * math.tau) * 1.1 * k) for i in range(11)])
    elif name == 'moon':
        S.append([((5 + math.cos(a) * 4.5) * k, (5 + math.sin(a) * 4.5) * k) for a in [math.pi * 0.35 + i / 20 * math.pi * 1.3 for i in range(21)]]
                 + [((6.8 + math.cos(a) * 3.4) * k, (4.2 + math.sin(a) * 3.4) * k) for a in [math.pi * 1.0 - i / 20 * math.pi * 0.95 for i in range(21)]])
    return S


class NeonSigns(Background):
    """a rainy alley wall full of buzzing neon signs, reflected in the wet ground.
    Signs flicker and stutter, brighten with output, flash on BEL, short-circuit
    with sparks when a command fails and run a chase when a long one succeeds."""
    name = 'neonsigns'
    opaque = True
    # kind, what, color, position (fraction of w, h), tube scale (pixels per unit at 240 px height)
    SIGNS = [('text', 'OPEN', (255, 40, 120), (0.05, 0.07), 4),
             ('shape', 'moon', (255, 240, 170), (0.30, 0.05), 3),
             ('text', 'BAR', (80, 120, 255), (0.46, 0.08), 4),
             ('shape', 'glass', (60, 230, 255), (0.82, 0.05), 4),
             ('shape', 'arrow', (80, 255, 120), (0.05, 0.36), 3),
             ('text', '24H', (255, 220, 60), (0.24, 0.33), 4),
             ('shape', 'heart', (255, 50, 70), (0.58, 0.27), 4),
             ('shape', 'star', (200, 80, 255), (0.85, 0.38), 3),
             ('shape', 'wave', (255, 140, 40), (0.40, 0.50), 3),
             ('shape', 'note', (60, 255, 220), (0.72, 0.55), 3),
             ('text', 'TERMINAL', (255, 60, 200), (0.07, 0.60), 3)]

    def resize(self, w, h):
        super().resize(w, h)
        self.floor_y = int(h * 0.74)
        self.wall = self._wall()
        unit = min(h, w * 0.6) / 240
        self.signs = []
        for kind, what, col, (fx, fy), ks in self.SIGNS:
            k = max(1, int(round(ks * unit)))
            if kind == 'text':
                segs, sw, sh = _text_strokes(what, k)
                lines = [list(sg) for sg in segs]
            else:
                lines = _shape(what, k)
                sw = sh = int(11 * k)
            pad = 2 * k + 4
            x, y = int(fx * w), int(fy * h)
            if y + sh + pad > self.floor_y or x + sw + pad > w:
                continue
            on = self._render(lines, sw, sh, pad, col, 1.0)
            dim = self._render(lines, sw, sh, pad, col, 0.12)
            halo = pygame.transform.smoothscale(pygame.transform.smoothscale(on, (max(1, on.get_width() // 8), max(1, on.get_height() // 8))),
                                                (on.get_width() * 2, on.get_height() * 2))
            halo.fill((110, 110, 110), special_flags=pygame.BLEND_RGB_MULT)
            self.signs.append({'on': on, 'dim': dim, 'halo': halo, 'x': x - pad, 'y': y - pad, 'col': col,
                               'state': 1.0, 'off': 0.0, 'stutter': 0, 'broken': random.random() < 0.18,
                               'chase': 0.0, 'buzz': random.random() * 9})
        self.sparks = []
        self.drops = [[random.uniform(0, w), random.uniform(0, h), random.uniform(90, 140)] for _ in range(70)]
        self.ripples = []
        self.last_cmd = signals.cmd
        self.last_bell = signals.bell
        self.flash = 0.0
        self.chase_t = -1.0

    def _wall(self):
        w, h = self.w, self.h
        s = pygame.Surface((w, h))
        s.fill((14, 10, 18))
        rng = random.Random(7)
        bh = max(4, h // 34)
        bw = bh * 2 + bh // 2
        for row, y in enumerate(range(0, self.floor_y, bh)):
            off = (row % 2) * bw // 2
            for x in range(-off, w, bw):
                v = rng.randint(16, 30)
                s.fill((v + 6, v - 2, v + 4), (x + 1, y + 1, bw - 1, bh - 1))
        s.fill((8, 6, 12), (0, self.floor_y, w, h - self.floor_y))
        s.fill((30, 24, 34), (0, self.floor_y, w, 1))
        return s

    def _render(self, lines, sw, sh, pad, col, k):
        surf = pygame.Surface((sw + 2 * pad, sh + 2 * pad))
        surf.fill((0, 0, 0))
        c = tuple(int(v * k) for v in col)
        passes = [(pad, tuple(v // 10 for v in c)), (max(3, pad // 2), tuple(v // 5 for v in c)),
                  (3, tuple(v // 2 for v in c)), (1, tuple(min(255, int(v + (255 - v) * 0.6 * k)) for v in c))]
        for width, pc in passes:
            for ln in lines:
                pts = [(px + pad, py + pad) for px, py in ln]
                if len(pts) > 1:
                    pygame.draw.lines(surf, pc, False, pts, width)
                for p in pts if width > 2 else ():
                    pygame.draw.circle(surf, pc, (int(p[0]), int(p[1])), width // 2)
        return surf

    def update(self, dt, energy):
        super().update(dt, energy)
        self.energy_now = energy
        if signals.cmd is not self.last_cmd and signals.cmd:
            self.last_cmd = signals.cmd
            code, secs, _ = signals.cmd
            if code and self.signs:
                sg = random.choice(self.signs)
                sg['off'] = 2.5
                sg['stutter'] = 6
                cx, cy = sg['x'] + sg['on'].get_width() / 2, sg['y'] + sg['on'].get_height() / 2
                for _ in range(40):
                    a = random.uniform(0, math.tau)
                    sp = random.uniform(30, 110)
                    self.sparks.append([cx, cy, math.cos(a) * sp, math.sin(a) * sp - 40, random.uniform(0.4, 1.0)])
            elif secs >= 2:
                self.chase_t = 0.0
        if signals.bell != self.last_bell:
            self.last_bell = signals.bell
            self.flash = 0.35
        self.flash = max(0.0, self.flash - dt)
        if self.chase_t >= 0:
            self.chase_t += dt
            if self.chase_t > 0.12 * len(self.signs) + 0.6:
                self.chase_t = -1.0
        typing = signals.recent(signals.typing, 0.3)
        for i, sg in enumerate(self.signs):
            if sg['off'] > 0:
                sg['off'] -= dt
                sg['state'] = 0.0 if sg['off'] > 0.4 else float(random.random() < 0.5)
                continue
            if sg['stutter'] > 0:
                if random.random() < dt * 25:
                    sg['stutter'] -= 1
                    sg['state'] = float(sg['stutter'] % 2 == 0)
                continue
            st = 1.0
            if random.random() < dt * (0.08 + energy * 0.3):
                sg['stutter'] = random.choice((2, 4, 6))
            if sg['broken'] and math.sin(self.t * 23 + sg['buzz']) * math.sin(self.t * 7.1 + sg['buzz']) > 0.6:
                st = 0.0
            if typing and random.random() < dt * 0.6:
                st = 0.0
            if self.chase_t >= 0:
                st = 1.0 if int(self.chase_t / 0.12) == i else 0.25
            if self.flash > 0:
                st = 0.0 if self.flash > 0.2 else 1.0
            sg['state'] = st
        for sp in self.sparks:
            sp[2] *= 1 - dt
            sp[3] += 260 * dt
            sp[0] += sp[2] * dt
            sp[1] += sp[3] * dt
            sp[4] -= dt
            if sp[1] > self.floor_y:
                sp[1] = self.floor_y
                sp[3] *= -0.3
        self.sparks = [sp for sp in self.sparks if sp[4] > 0]
        for d in self.drops:
            d[1] += d[2] * dt
            d[0] -= d[2] * 0.15 * dt
            if d[1] > self.h:
                if random.random() < 0.5:
                    self.ripples.append([d[0], random.uniform(self.floor_y + 2, self.h - 1), 0.0])
                d[1] = random.uniform(-20, 0)
                d[0] = random.uniform(0, self.w + 20)
        for r in self.ripples:
            r[2] += dt
        self.ripples = [r for r in self.ripples if r[2] < 0.6][-40:]

    def draw(self, surf, first):
        w, h, fy = self.w, self.h, self.floor_y
        surf.blit(self.wall, (0, 0))
        boost = 0.85 + min(0.4, getattr(self, 'energy_now', 0) * 0.3)
        add = pygame.BLEND_RGB_ADD
        for sg in self.signs:
            if sg['state'] > 0.5:
                hl = sg['halo']
                surf.blit(hl, (sg['x'] - hl.get_width() // 4, sg['y'] - hl.get_height() // 4), special_flags=add)
        for sg in self.signs:
            img = sg['on'] if sg['state'] > 0.5 else sg['dim']
            if sg['state'] > 0.5 and boost > 1.0:
                surf.blit(sg['dim'], (sg['x'], sg['y']), special_flags=add)
            surf.blit(img, (sg['x'], sg['y']), special_flags=add)
        for x, y, vx, vy, life in self.sparks:
            c = _lerp((255, 255, 220), (255, 120, 30), 1 - min(1, life))
            surf.fill(c, (int(x), int(y), 1, 1))
            surf.fill(tuple(int(v * 0.5) for v in c), (int(x - vx * 0.01), int(y - vy * 0.01), 1, 1))
        # wet ground: darkened, rippled mirror of the wall
        rh = h - fy
        if rh > 2:
            src = surf.subsurface((0, max(0, fy - rh), w, min(rh, fy))).copy()
            src = pygame.transform.flip(src, False, True)
            src.fill((95, 95, 110), special_flags=pygame.BLEND_RGB_MULT)
            for yy in range(0, src.get_height(), 2):
                dx = int(math.sin(self.t * 3 + yy * 0.7) * (1 + yy / 12))
                surf.blit(src, (dx, fy + yy), (0, yy, w, 2))
            surf.fill((40, 30, 50), (0, fy, w, 1), special_flags=add)
            for x, y, a in self.ripples:
                r = 1 + a * 10
                pygame.draw.ellipse(surf, (60, 60, 80), (x - r, y - r * 0.3, 2 * r, r * 0.6), 1)
        # rain
        for x, y, v in self.drops:
            surf.fill((70, 70, 95), (int(x), int(y), 1, 3))


SCENES = {c.name: c for c in (Dollhouse, Railway, Settlers, DiscoCity, NeonSigns)}
