"""The miner cursor: a tiny animated pixel character that *is* the cursor.

It stands in the cursor cell, walks (smoothly) wherever the cursor goes,
swings its pickaxe at the letters you type, hops on Enter, shows little
speech bubbles (! on bell, ? on failed commands, ♥ on success), blinks,
looks around, taps its pickaxe - and falls asleep (z z z) when you leave it
alone. In EMERALD MINE mode it digs the letters out of the earth.

Enable anywhere with   cursor_style: miner   (theme)."""
from __future__ import annotations

import math
import random

import numpy as np
import pygame

from . import particles as P

PAL = {'Y': (255, 200, 30), 'L': (255, 255, 210), 'S': (240, 180, 130), 'O': (20, 12, 12),
       'B': (40, 110, 230), 'b': (28, 56, 130), 'K': (110, 60, 22), 'P': (255, 140, 160)}

# 6 x 10, facing right. Hand (pickaxe pivot) at HAND.
HEAD = [".YYY..",
        "YYYYL.",
        ".SSO..",
        ".SSSP."]
HEAD_BLINK = [".YYY..",
              "YYYYL.",
              ".SSS..",
              ".SSSP."]
HEAD_SLEEP = [".YYY..",
              "YYYYL.",
              ".SOO..",
              ".SSS.."]
BODY = [".BBB..",
        "BBBBS.",
        ".BBB.."]
LEGS = {'stand': [".b.b..", "KK.KK."],
        'walk1': ["b...b.", "K...KK"],
        'walk2': ["..bb..", ".KKK.."],
        'hop': ["b...b.", "K...K."],
        'sit': ["bbbb..", "KK.KK."]}
HAND = (4, 5)
W, H = 6, 10


SKINS = {
    'miner': {},
    # jump'n'run hero: orange hood, teal shirt, no lamp, no pickaxe
    'hero': {'Y': (255, 110, 40), 'L': (255, 110, 40), 'B': (40, 200, 170), 'b': (30, 90, 120), 'P': (255, 120, 120)},
    # settler: brown cap, green tunic - swings a hammer
    'settler': {'Y': (140, 85, 40), 'L': (140, 85, 40), 'B': (70, 150, 60), 'b': (120, 85, 45), 'P': (255, 150, 140)},
    'train': {},
}
# the train skin: a tiny steam locomotive (6 x 10, facing right)
TRAIN = ["......",
         "......",
         "....K.",
         "RR..K.",
         "RWGGGG",
         "RRGGGG",
         "RRGGGY",
         "KKKKKK",
         ".O..O.",
         "......"]
TRAIN_PAL = {'R': (220, 50, 50), 'W': (255, 230, 150), 'G': (40, 160, 90), 'K': (40, 40, 50), 'Y': (255, 240, 120),
             'O': (30, 30, 30), 'o': (170, 170, 180)}


def _sprite(rows, k, helmet, pal=None):
    pal = dict(PAL, **(pal or {}))
    s = pygame.Surface((W, len(rows)), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c != '.':
                s.set_at((x, y), helmet if (c == 'Y' and helmet) else pal[c])
    return pygame.transform.scale(s, (W * k, len(rows) * k)) if k > 1 else s


class MinerCursor:
    def __init__(self, cw, ch, helmet=None, skin='miner'):
        self.cw, self.ch = cw, ch
        self.skin = skin if skin in SKINS else 'miner'
        self.tool = self.skin in ('miner', 'settler')
        self.k = max(1, ch // 10)
        k = self.k
        self.frames = {}
        for hname, head in (('open', HEAD), ('blink', HEAD_BLINK), ('sleep', HEAD_SLEEP)):
            for lname, legs in LEGS.items():
                img = _sprite(head + BODY + legs[:1] + legs[1:], k, helmet, SKINS[self.skin])
                # legs list is 2 rows; pad to 10 rows total (head 4 + body 3 + legs 2 = 9) -> add blank top row
                full = pygame.Surface((W * k, H * k), pygame.SRCALPHA)
                full.fill((0, 0, 0, 0))
                full.blit(img, (0, k))
                self.frames[(hname, lname)] = (full, pygame.transform.flip(full, True, False))
        if self.skin == 'train':
            for key in list(self.frames):
                rows = list(TRAIN)
                if key[1] in ('walk1', 'hop'):
                    rows[8] = ".o..o."
                s = pygame.Surface((W, H), pygame.SRCALPHA)
                s.fill((0, 0, 0, 0))
                for y, r in enumerate(rows):
                    for x, ch2 in enumerate(r):
                        if ch2 != '.':
                            s.set_at((x, y), TRAIN_PAL[ch2])
                if k > 1:
                    s = pygame.transform.scale(s, (W * k, H * k))
                self.frames[key] = (s, pygame.transform.flip(s, True, False))
        self.x = self.y = None
        self.face = 1
        self.state = 'idle'
        self.t = 0.0
        self.walk_t = 0.0
        self.swing = -1.0
        self.swing_dur = 0.16
        self.swing_face = -1
        self.hop = 0.0
        self.idle_t = 0.0
        self.blink = 0.0
        self.next_idle = random.uniform(1.5, 4)
        self.look = 0.0
        self.bubble = None      # (text, seconds_left, color)
        self.zz = 0.0
        self.lamp = self._make_lamp()
        self.hits = 0           # swings landed this frame (for the mine)

    def _make_lamp(self):
        r = max(6, int(self.ch * 1.6))
        s = pygame.Surface((r * 2, r * 2))
        s.fill((0, 0, 0))
        for i in range(r, 0, -1):
            k = (1 - i / r) ** 2
            pygame.draw.circle(s, (int(70 * k), int(55 * k), int(25 * k)), (r, r), i)
        return s

    # ------------------------------------------------------------ triggers
    def wake(self):
        self.idle_t = 0.0
        if self.state == 'sleep':
            self.state = 'idle'
            self.say('!', 0.6)

    def strike(self, face=-1, dur=0.16):
        self.wake()
        if not self.tool:          # the hero jumps instead of swinging
            self.face = face if face else self.face
            if self.hop <= 0.05:
                self.hop = 0.2
                self.hits += 1
            return
        if self.swing < 0:
            self.swing = 0.0
            self.swing_dur = dur
            self.swing_face = face

    def jump(self):
        self.wake()
        if self.hop <= 0:
            self.hop = 0.28

    def say(self, text, secs=1.2, color=(255, 255, 255)):
        self.bubble = [text, secs, color]

    # ------------------------------------------------------------ update
    def update(self, dt, tx, ty):
        """tx, ty: pixel position of the cursor cell (terminal space)"""
        self.t += dt
        self.hits = 0
        if self.x is None or abs(tx - self.x) > self.cw * 30 or abs(ty - self.y) > self.ch * 8:
            self.x, self.y = float(tx), float(ty)
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist > 0.3:
            k = 1 - math.exp(-dt * 22)
            self.x += dx * k
            self.y += dy * k
            if abs(dx) > 0.5:
                self.face = 1 if dx > 0 else -1
            if dist > self.cw * 0.6:
                self.walk_t += dt
                self.wake()
        else:
            self.x, self.y = float(tx), float(ty)
            self.walk_t = 0.0
        # swing
        if self.swing >= 0:
            self.swing += dt
            if self.swing >= self.swing_dur:
                self.swing = -1.0
                self.hits += 1
        if self.hop > 0:
            self.hop = max(0.0, self.hop - dt)
        if self.bubble:
            self.bubble[1] -= dt
            if self.bubble[1] <= 0:
                self.bubble = None
        # idle life
        self.idle_t += dt
        if self.state != 'sleep' and self.idle_t > 25:
            self.state = 'sleep'
        if self.state == 'sleep':
            self.zz += dt
            return
        self.blink = max(0.0, self.blink - dt)
        self.look = max(0.0, self.look - dt)
        self.next_idle -= dt
        if self.next_idle <= 0 and self.walk_t == 0 and self.swing < 0:
            r = random.random()
            if r < 0.45:
                self.blink = 0.14
            elif r < 0.75:
                self.look = random.uniform(0.6, 1.2)
            elif r < 0.9:
                self.swing = 0.0
                self.swing_dur = 0.45
                self.swing_face = self.face
            else:
                self.hop = 0.22
            self.next_idle = random.uniform(1.2, 4.0)

    def busy(self):
        return self.swing >= 0 or self.hop > 0 or self.walk_t > 0 or self.bubble is not None

    # ------------------------------------------------------------ draw
    def draw(self, surf, ox, oy, lamp=True):
        if self.x is None:
            return
        k = self.k
        sleeping = self.state == 'sleep'
        face = self.face
        if self.swing >= 0:
            face = self.swing_face
        elif self.look > 0:
            face = -self.face
        if sleeping:
            head, legs = 'sleep', 'sit'
        else:
            head = 'blink' if self.blink > 0 else 'open'
            if self.hop > 0:
                legs = 'hop'
            elif self.walk_t > 0:
                legs = 'walk1' if int(self.walk_t * 12) % 2 else 'walk2'
            else:
                legs = 'stand'
        img = self.frames[(head, legs)][0 if face > 0 else 1]
        bob = 0
        if sleeping:
            bob = k
        elif self.hop > 0:
            bob = -int(math.sin(self.hop / 0.28 * math.pi) * self.ch * 0.35)
        sx = int(ox + self.x + (self.cw - W * k) // 2)
        sy = int(oy + self.y + self.ch - H * k + bob)
        if not self.tool:
            surf.blit(img, (sx, sy))
            if sleeping:
                for i in range(3):
                    ph = (self.zz * 0.6 + i / 3) % 1
                    self._z(surf, sx + W * k + int(ph * 4 * k), sy - int(ph * self.ch * 1.2), int(255 * (1 - ph)))
            elif self.bubble:
                self._bubble(surf, sx + W * k // 2, sy - 2 * k, *self.bubble)
            return
        # pickaxe
        hx = sx + (HAND[0] * k if face > 0 else (W - HAND[0]) * k)
        hy = sy + (HAND[1] + 1) * k
        if sleeping:
            ang = 1.2
        elif self.swing >= 0:
            p = min(1.0, self.swing / self.swing_dur)
            ang = -2.3 + 3.0 * (p ** 2.2)
        else:
            ang = -1.6 + 0.12 * math.sin(self.t * 3)
        a = ang if face > 0 else math.pi - ang
        L = 4.5 * k
        ex, ey = hx + math.cos(a) * L, hy + math.sin(a) * L
        pygame.draw.line(surf, (160, 100, 45), (hx, hy), (ex, ey), k)
        nx, ny = -math.sin(a) * 2 * k, math.cos(a) * 2 * k
        pygame.draw.line(surf, (205, 205, 220), (ex - nx, ey - ny), (ex + nx * 0.7, ey + ny * 0.7), k)
        surf.blit(img, (sx, sy))
        if lamp and not sleeping:
            flick = 0.85 + 0.15 * math.sin(self.t * 23) * math.sin(self.t * 7)
            lw = self.lamp.get_width()
            lx = sx + (W * k if face > 0 else 0) - lw // 2
            ly = sy + 2 * k - lw // 2
            if flick < 0.98:
                lm = self.lamp.copy()
                v = int(255 * flick)
                lm.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
                surf.blit(lm, (lx, ly), special_flags=pygame.BLEND_RGB_ADD)
            else:
                surf.blit(self.lamp, (lx, ly), special_flags=pygame.BLEND_RGB_ADD)
        # bubbles
        if sleeping:
            for i in range(3):
                ph = (self.zz * 0.6 + i / 3) % 1
                zx = sx + W * k + int(ph * 4 * k)
                zy = sy - int(ph * self.ch * 1.2)
                self._z(surf, zx, zy, int(255 * (1 - ph)))
        elif self.bubble:
            self._bubble(surf, sx + W * k // 2, sy - 2 * k, *self.bubble)

    def _z(self, surf, x, y, a):
        k = self.k
        c = (a, a, a)
        surf.fill(c, (x, y, 3 * k, k))
        surf.fill(c, (x + k, y + k, k, k))
        surf.fill(c, (x, y + 2 * k, 3 * k, k))

    _GL = {'!': ["#", "#", "#", ".", "#"], '?': ["##.", "..#", ".#.", "...", ".#."],
           '♥': ["#.#", "###", "###", ".#."], '♪': [".##", ".#.", ".#.", "##."], '$': [".#.", "###", ".##", "###", ".#."]}

    def _bubble(self, surf, cx, by, text, left, color):
        k = self.k
        g = self._GL.get(text, self._GL['!'])
        gw, gh = len(g[0]), len(g)
        w, h = (gw + 2) * k, (gh + 2) * k
        x, y = cx - w // 2, by - h - k
        surf.fill((255, 255, 255), (x, y, w, h))
        surf.fill((255, 255, 255), (cx - k // 2 - (k > 1), y + h, k, k))
        col = (230, 40, 60) if text == '♥' else (20, 20, 30)
        for yy, row in enumerate(g):
            for xx, ch in enumerate(row):
                if ch == '#':
                    surf.fill(col, (x + (xx + 1) * k, y + (yy + 1) * k, k, k))

    # ------------------------------------------------------------ particles
    def dust(self, particles, x_px, y_px, col=(150, 120, 90), n=5):
        particles.emit(n, x_px + np.random.uniform(0, self.cw, n).astype(np.float32),
                       y_px + np.random.uniform(self.ch * 0.5, self.ch, n).astype(np.float32),
                       vx=np.random.uniform(-40, 40, n).astype(np.float32),
                       vy=np.random.uniform(-60, -10, n).astype(np.float32), grav=200,
                       life=np.random.uniform(0.2, 0.45, n).astype(np.float32), col=col, pal=P.FADE)
