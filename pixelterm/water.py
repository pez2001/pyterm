"""Water mirror background: the lower part of the window is a lake that
mirrors everything above the waterline - the background layers below it in
the stack *and the terminal text itself* - flipped, tinted and distorted by
waves. Typing drops ripples under the cursor, Enter sends a swell across,
output energy makes the water choppier.

    background: [watermirror]               # alone: moonlit sky, hills, lights
    background: [plasma, watermirror]       # or mirror any other layers
    bg_params:
      watermirror: {level: 0.62, tint: '#5a8cd2', waves: 1.0, speed: 1.0, text: true, sky: auto}

level  waterline (0 top .. 1 bottom)      waves  distortion strength
tint   water color multiplied in          speed  wave speed
text   mirror the terminal text            sky    auto | true | false: draw the built-in night scene
"""
from __future__ import annotations

import math
import random

import pygame

from . import signals
from .backgrounds import Background
from .themes import hex2rgb
from .weather import _lerp, moon_phase


class WaterMirror(Background):
    name = 'watermirror'
    wants_text = True          # the app hands us the panes' text layers (self.text_layers)

    def resize(self, w, h):
        super().resize(w, h)
        self.level = int(h * max(0.15, min(0.95, float(self.p('level', 0.62)))))
        self.text_layers = []
        self.ripples = []         # [x, age]
        self.swell = 0.0
        self.last_enter = signals.enter
        self.last_typing = signals.typing
        self.last_cmd = signals.cmd
        self.energy_now = 0.0
        self._fade = None
        rng = random.Random(21)
        self.stars = [(rng.uniform(0, w), rng.uniform(0, self.level * 0.85), rng.random()) for _ in range(90)]
        xs = range(w + 1)
        self.hills = [int(self.level - 4 - abs(math.sin(x / w * 5.3 + 1)) * h * 0.06 - math.sin(x / w * 17) * h * 0.012)
                      for x in xs]
        self.lights = [(rng.uniform(0, w), rng.choice([(255, 210, 120), (255, 160, 90), (200, 230, 255)]), rng.random())
                       for _ in range(18)]
        self._sky = None

    # ------------------------------------------------------------ update
    def update(self, dt, energy):
        super().update(dt, energy)
        self.energy_now = energy
        sp = float(self.p('speed', 1.0))
        self.wt = getattr(self, 'wt', 0.0) + dt * sp * (1 + energy * 0.8)
        if signals.typing != self.last_typing:
            self.last_typing = signals.typing
            cx = getattr(signals, 'cursor_x', None)
            x = cx if cx is not None else random.uniform(0, self.w)
            if len(self.ripples) < 24:
                self.ripples.append([x + random.uniform(-2, 2), 0.0, random.uniform(0.6, 1.0)])
        if signals.enter != self.last_enter:
            self.last_enter = signals.enter
            self.swell = min(2.5, self.swell + 1.2)
        if signals.cmd is not self.last_cmd and signals.cmd:
            self.last_cmd = signals.cmd
            if signals.cmd[0]:                       # failed command: a big splash in the middle
                self.ripples.append([self.w / 2, 0.0, 2.5])
                self.swell = 2.5
        self.swell = max(0.0, self.swell - dt * 0.9)
        for r in self.ripples:
            r[1] += dt
        self.ripples = [r for r in self.ripples if r[1] < 1.6]

    # ------------------------------------------------------------ draw
    def _night(self, surf):
        w, L = self.w, self.level
        if self._sky is None or self._sky.get_size() != (w, L):
            col = pygame.Surface((1, 32))
            for y in range(32):
                col.set_at((0, y), _lerp((6, 8, 26), (40, 36, 80), y / 31))
            self._sky = pygame.transform.smoothscale(col, (w, max(1, L)))
        surf.blit(self._sky, (0, 0))
        for x, y, tw in self.stars:
            v = int(150 + 100 * math.sin(self.t * 2 + tw * 40))
            surf.fill((v, v, min(255, v + 20)), (int(x), int(y), 1, 1))
        mx, my, r = int(w * 0.72), int(L * 0.28), max(4, self.h // 26)
        glow = pygame.Surface((r * 6, r * 6))
        glow.fill((0, 0, 0))
        for i in range(3, 0, -1):
            pygame.draw.circle(glow, (12 * (4 - i), 12 * (4 - i), 16 * (4 - i)), (r * 3, r * 3), r * i)
        surf.blit(glow, (mx - r * 3, my - r * 3), special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.circle(surf, (235, 232, 210), (mx, my), r)
        ph = moon_phase()
        if abs(ph - 0.5) > 0.06:
            pygame.draw.circle(surf, _lerp((6, 8, 26), (40, 36, 80), my / max(1, L)), (mx + int((ph - 0.5) * 4 * r), my), r)
        for x in range(w):
            y = self.hills[x]
            surf.fill((10, 10, 22), (x, y, 1, L - y))
        for x, c, ph2 in self.lights:
            if math.sin(self.t * 0.7 + ph2 * 20) > -0.8:
                y = self.hills[int(x) % w] + 2
                surf.fill(c, (int(x), min(L - 2, y + int(ph2 * 3)), 1, 1))

    def draw(self, surf, first):
        w, h, L = self.w, self.h, self.level
        sky = self.p('sky', 'auto')
        self._drew_sky = sky is True or (sky == 'auto' and first)
        if self._drew_sky:
            self._night(surf)
        depth = h - L
        if depth < 2:
            return
        top = max(0, L - depth)
        src_h = L - top
        # what is above the waterline: background + (optionally) the terminal text
        src = surf.subsurface((0, top, w, src_h)).copy()
        if self.p('text', True):
            area = pygame.Rect(0, top, w, src_h)
            for ts, (px, py) in self.text_layers:
                r = pygame.Rect(px, py, ts.get_width(), ts.get_height()).clip(area)
                if r.width and r.height:
                    src.blit(ts, (r.x, r.y - top), (r.x - px, r.y - py, r.width, r.height))
        src = pygame.transform.flip(src, False, True)
        tint = hex2rgb(self.p('tint', '#5a8cd2'))
        src.fill(tuple(int(c) for c in _lerp(tint, (255, 255, 255), 0.45)), special_flags=pygame.BLEND_RGB_MULT)
        # water body
        base = tuple(int(c * 0.10) for c in tint)
        surf.fill(base, (0, L, w, depth))
        amp = float(self.p('waves', 1.0)) * (1 + self.energy_now * 0.8 + self.swell)
        t = self.wt
        rips = self.ripples
        for yy in range(min(depth, src_h)):
            k = yy / max(1, depth)                         # 0 at the waterline .. 1 at the bottom
            sy = yy + int(math.sin(t * 2.3 + yy * 0.45) * (0.5 + 2.0 * k) * amp)   # vertical wobble
            sy = max(0, min(src_h - 1, sy))
            dx = math.sin(t * 1.7 + yy * 0.32) * (0.6 + 3.5 * k) * amp + math.sin(t * 3.1 - yy * 0.9) * 0.8 * amp
            surf.blit(src, (int(dx), L + yy), (0, sy, w, 1))
            # ripple rings: local horizontal shove around each drop
            for x, age, size in rips:
                ry = age * 14 * size
                if abs(yy - ry * 0.35) < 1.5:
                    rx = age * 40 * size
                    a = int(90 * (1 - age / 1.6))
                    c = (a, a, min(255, a + 30))
                    surf.fill(c, (int(x - rx), L + yy, max(1, int(rx * 0.5)), 1), special_flags=pygame.BLEND_RGB_ADD)
                    surf.fill(c, (int(x + rx * 0.5), L + yy, max(1, int(rx * 0.5)), 1), special_flags=pygame.BLEND_RGB_ADD)
        # fade with depth + glints
        if self._fade is None or self._fade.get_size() != (w, depth):
            col = pygame.Surface((1, 32))
            for y in range(32):
                v = int(255 * (1 - 0.75 * (y / 31) ** 0.8))
                col.set_at((0, y), (v, v, v))
            self._fade = pygame.transform.smoothscale(col, (w, depth))
        surf.blit(self._fade, (0, L), special_flags=pygame.BLEND_RGB_MULT)
        rnd = random.Random(int(t * 6))
        for _ in range(int(14 + 20 * min(2, amp))):
            yy = int(rnd.random() ** 2 * depth)
            gx = rnd.uniform(0, w)
            gl = rnd.randint(2, 6)
            v = int(70 * (1 - yy / depth))
            surf.fill((v, v, v + 10), (int(gx), L + yy, gl, 1), special_flags=pygame.BLEND_RGB_ADD)
        surf.fill(_lerp(tint, (255, 255, 255), 0.5), (0, L, w, 1), special_flags=pygame.BLEND_RGB_ADD)
        if self._drew_sky:                       # moonlight glitter path on the water
            mx = int(w * 0.72)
            for _ in range(int(40 + 30 * min(2, amp))):
                yy = int(rnd.random() * depth)
                spread = 3 + yy * 0.35
                gx = mx + rnd.gauss(0, spread)
                v = int(170 * (1 - yy / depth) ** 0.7)
                surf.fill((v, v, int(v * 0.85)), (int(gx), L + yy, rnd.randint(1, 4), 1), special_flags=pygame.BLEND_RGB_ADD)
