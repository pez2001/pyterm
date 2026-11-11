"""Letter effects.

*Appear* effects animate a letter into existence while its cell is hidden in
the text layer; *vanish* effects turn a deleted letter into particles.
Everything is tracked in virtual rows (vy = screen row + total full-screen
scrolls) so scrolling costs O(1).

Write your own: subclass ``Appear`` (see plugins/example_effect.py) and
register it with ``api.register_letter_effect``.
"""
from __future__ import annotations

import math
import random

import numpy as np
import pygame

from . import particles as P
from .vt import EV_DEL, EV_PUT, EV_RESET, EV_SCROLL

rnd = random.random


def blit_alpha(dst, src, pos, alpha, area=None):
    alpha = int(max(0, min(255, alpha)))
    if alpha <= 0:
        return
    src.set_alpha(alpha)
    dst.blit(src, pos, area)
    src.set_alpha(255)


def lerp_rgb(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def quant(rgb, q=24):
    return (rgb[0] // q * q, rgb[1] // q * q, rgb[2] // q * q)


# ============================================================================
class Appear:
    """Base class. self.x, self.vy are cell coords; px/py pixel coords in
    virtual terminal space. Return False from update() when finished."""
    name = 'base'
    duration = 0.5

    def __init__(self, m, x, vy, c, attr):
        self.m = m
        self.x, self.vy, self.c, self.attr = x, vy, c, attr
        f, bgc, style, fl = m.renderer.resolve(attr)
        self.rgb = f or (200, 200, 200)
        self.style = style
        self.t = 0.0
        self.dur = self.duration * m.speed * (0.85 + 0.3 * rnd())
        self.cw, self.ch = m.cw, m.ch
        self.px, self.py = x * m.cw, vy * m.ch
        self.start()

    def glyph(self, rgb=None):
        return self.m.renderer.colored(self.c, self.style, False, rgb or self.rgb)

    def pixels(self):
        return self.m.font.pixels(self.c, self.style)

    def moved(self, dvy):
        self.vy += dvy
        self.py += dvy * self.ch

    def start(self):
        pass

    def update(self, dt):
        self.t += dt
        return self.t < self.dur

    def draw(self, surf, ox, oy):
        pass

    @property
    def k(self):
        return min(1.0, self.t / self.dur)


class Instant(Appear):
    name = 'none'

    def update(self, dt):
        return False


class Flame(Appear):
    """the letter ignites, burns white-hot and cools to its color"""
    name = 'flame'
    duration = 0.7

    def start(self):
        xs, ys = self.pixels()
        n = len(xs)
        if not n:
            return
        k = max(3, int(n * 0.9))  # one emission for the whole lifetime (delays spread it out)
        sel = np.random.randint(0, n, k)
        d = np.random.uniform(0, 1, k).astype(np.float32)
        self.m.particles.emit(k, self.px + xs[sel] + np.random.uniform(-.5, .5, k).astype(np.float32),
                              self.py + ys[sel], vx=np.random.uniform(-12, 12, k).astype(np.float32),
                              vy=np.random.uniform(-70, -25, k).astype(np.float32),
                              life=np.random.uniform(0.25, 0.6, k).astype(np.float32), pal=P.FIRE, add=True,
                              delay=d * d * self.dur * 0.8)

    def draw(self, surf, ox, oy):
        k = self.k
        if k < 0.5:
            tint = lerp_rgb((255, 255, 210), (255, 150, 30), k * 2)
        else:
            tint = lerp_rgb((255, 150, 30), self.rgb, (k - 0.5) * 2)
        jitter = -1 if rnd() < 0.3 * (1 - k) else 0
        blit_alpha(surf, self.glyph(quant(tint)), (ox + self.px, oy + self.py + jitter), 80 + 175 * k)


class Laser(Appear):
    """a laser beam from the sky engraves the letter line by line"""
    name = 'laser'
    duration = 0.45

    def start(self):
        m = self.m
        self.origin = (m.cols * self.cw * (0.15 + 0.7 * rnd()), -self.ch * 3)
        self.beam = random.choice([(255, 40, 60), (60, 255, 120), (80, 160, 255), (255, 60, 255)])
        n = 12
        d = np.random.uniform(0, self.dur * 0.85, n).astype(np.float32)
        self.m.particles.emit(n, self.px + np.random.uniform(0, self.cw, n).astype(np.float32),
                              self.py + d / self.dur * self.ch * 1.15, vx=np.random.uniform(-80, 80, n).astype(np.float32),
                              vy=np.random.uniform(-90, -10, n).astype(np.float32), grav=300,
                              life=0.35, col=self.beam, pal=P.FADE, add=True, delay=d)
        self.show_beam = len(self.m.active) < 64

    def draw(self, surf, ox, oy):
        k = self.k
        row = int(self.ch * min(1.0, k * 1.15))
        g = self.glyph()
        if row > 0:
            surf.blit(g, (ox + self.px, oy + self.py), (0, 0, self.cw, row))
        if k < 0.95 and self.show_beam:
            hx = ox + self.px + rnd() * self.cw
            hy = oy + self.py + min(row, self.ch - 1)
            sx = ox + self.origin[0]
            sy = oy + self.py - self.ch * 30  # beam comes from far above
            pygame.draw.line(surf, self.beam, (sx, sy), (hx, hy), 1)
            surf.fill((255, 255, 255), (hx - 1, hy - 1, 3, 2))
            surf.fill(self.beam, (ox + self.px, hy, self.cw, 1), special_flags=pygame.BLEND_RGB_ADD)


class Sand(Appear):
    """grains of sand rain down and pile up into the letter"""
    name = 'sand'
    duration = 0.75

    def start(self):
        xs, ys = self.pixels()
        n = len(xs)
        if not n:
            self.dur = 0
            return
        h = self.ch
        travel = (0.18 + (1 - ys / h) * 0.35 + np.random.uniform(0, 0.12, n)).astype(np.float32) * self.dur / 0.75
        delay = np.random.uniform(0, 0.12, n).astype(np.float32)
        sand = np.array([[225, 190, 120]], np.float32)
        col = (np.array(self.rgb, np.float32) * 0.55 + sand * 0.45) * np.random.uniform(0.75, 1.1, (n, 1)).astype(np.float32)
        tx = (self.px + xs).astype(np.float32)
        ty = (self.py + ys).astype(np.float32)
        self.m.particles.emit(n, tx + np.random.uniform(-3, 3, n).astype(np.float32),
                              ty - np.random.uniform(h * 1.5, h * 4, n).astype(np.float32),
                              kind=P.HOMING, tx=tx, ty=ty, travel=travel, ease=P.FALL,
                              life=self.dur + 0.06, col=np.clip(col, 0, 255), delay=delay)


class Dissolve(Appear):
    """pixels materialise in random order out of static noise"""
    name = 'dissolve'
    duration = 0.6

    def start(self):
        xs, ys = self.pixels()
        n = len(xs)
        if not n:
            return
        tx = (self.px + xs).astype(np.float32)
        ty = (self.py + ys).astype(np.float32)
        delay = np.random.uniform(0, self.dur * 0.75, n).astype(np.float32)
        self.m.particles.emit(n, tx, ty, kind=P.HOMING, tx=tx, ty=ty, travel=0.15, pal=P.FLASH,
                              life=self.dur + 0.05, col=self.rgb, delay=delay)
        k = 6
        self.m.particles.emit(k, self.px + np.random.uniform(0, self.cw, k).astype(np.float32),
                              self.py + np.random.uniform(0, self.ch, k).astype(np.float32),
                              life=np.random.uniform(0.1, 0.4, k).astype(np.float32), pal=P.SPARKLE,
                              col=(255, 255, 255), add=True, delay=np.random.uniform(0, 0.3, k).astype(np.float32))


class Construction(Appear):
    """a tiny crane assembles the letter brick by brick, bottom up"""
    name = 'construction'
    duration = 0.9

    def start(self):
        xs, ys = self.pixels()
        n = len(xs)
        self.n = n
        if not n:
            return
        order = np.lexsort((xs, -ys))
        xs, ys = xs[order], ys[order]
        self.bx = xs
        self.by = ys
        self.delays = (np.arange(n) / max(1, n) * self.dur * 0.8).astype(np.float32)
        tx = (self.px + xs).astype(np.float32)
        ty = (self.py + ys).astype(np.float32)
        self.m.particles.emit(n, tx, ty - 3 - ys * 0.3, kind=P.HOMING, tx=tx, ty=ty, travel=0.07, ease=P.FALL,
                              pal=P.FLASH, life=self.dur + 0.05, col=lerp_rgb(self.rgb, (255, 190, 40), 0.35),
                              delay=self.delays)

    def draw(self, surf, ox, oy):
        if not self.n or self.k > 0.92:
            return
        i = min(self.n - 1, int(np.searchsorted(self.delays, self.t)))
        x0, y0 = ox + self.px, oy + self.py
        # scaffold
        for yy in range(0, self.ch, 2):
            c = (255, 200, 0) if (yy // 2) % 2 else (40, 40, 40)
            surf.set_at((x0 - 1, y0 + yy), c)
            surf.set_at((x0 + self.cw, y0 + yy), c)
        # crane
        top = y0 - 4
        surf.fill((255, 200, 0), (x0 - 1, top, self.cw + 2, 1))
        hx = x0 + int(self.bx[i])
        hy = y0 + int(self.by[i]) - 2
        pygame.draw.line(surf, (160, 160, 160), (hx, top + 1), (hx, max(top + 1, hy)))
        surf.set_at((hx, max(top + 1, hy)), (255, 255, 255))


class Teleport(Appear):
    """star-trek style beam-in shimmer"""
    name = 'teleport'
    duration = 0.8

    def start(self):
        n = 30
        self.m.particles.emit(n, self.px + np.random.uniform(0, self.cw, n).astype(np.float32),
                              self.py + np.random.uniform(-2, self.ch + 2, n).astype(np.float32),
                              vy=np.random.uniform(-15, 15, n).astype(np.float32),
                              life=np.random.uniform(0.08, 0.3, n).astype(np.float32), pal=P.SPARKLE,
                              col=lerp_rgb(self.rgb, (190, 230, 255), 0.6), add=True,
                              delay=np.random.uniform(0, self.dur * 0.75, n).astype(np.float32))

    def draw(self, surf, ox, oy):
        k = self.k
        b = math.sin(k * math.pi)
        x0, y0 = ox + self.px, oy + self.py
        beam = (int(60 * b), int(90 * b), int(140 * b))
        surf.fill(beam, (x0, y0 - self.ch, self.cw, self.ch * 3), special_flags=pygame.BLEND_RGB_ADD)
        blit_alpha(surf, self.glyph(quant(lerp_rgb((200, 240, 255), self.rgb, k))),
                   (x0 + (random.randint(-1, 1) if k < 0.6 else 0), y0), 255 * k * k)


class Fluid(Appear):
    """liquid pours in and fills the letter from the bottom"""
    name = 'fluid'
    duration = 0.8

    def start(self):
        self.liquid = lerp_rgb(self.rgb, (60, 140, 255), 0.5)
        n = 4
        self.m.particles.emit(n, self.px + self.cw / 2 + np.random.uniform(-1, 1, n).astype(np.float32),
                              self.py - np.random.uniform(self.ch, self.ch * 3, n).astype(np.float32),
                              vy=60, grav=500, life=0.25, col=self.liquid, pal=P.SOLID,
                              delay=np.random.uniform(0, 0.25, n).astype(np.float32))

    def draw(self, surf, ox, oy):
        k = self.k
        e = 1 - (1 - k) ** 2
        g = self.glyph()
        cw, ch = self.cw, self.ch
        x0, y0 = ox + self.px, oy + self.py
        strip = max(1, cw // 4)
        amp = 1.6 * (1 - k)
        for i in range(0, cw, strip):
            lvl = int(ch * (1 - e) + math.sin(self.t * 14 + i * 0.9) * amp)
            lvl = max(0, min(ch, lvl))
            if lvl < ch:
                surf.blit(g, (x0 + i, y0 + lvl), (i, lvl, strip, ch - lvl))
            if 0 < lvl < ch and k < 0.97:
                surf.fill(self.liquid, (x0 + i, y0 + lvl, strip, 1))


class Decrypt(Appear):
    """hacker-movie decryption: random glyphs until the right one locks in"""
    name = 'decrypt'
    duration = 0.55
    POOL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#$%&*+=?@<>/\\|'

    def draw(self, surf, ox, oy):
        if self.k > 0.85:
            col = (255, 255, 255)
            c = self.c
        else:
            c = random.choice(self.POOL)
            col = (80, 255, 120) if rnd() < 0.8 else (255, 255, 255)
        surf.blit(self.m.renderer.colored(c, self.style, False, col), (ox + self.px, oy + self.py))


class Drop(Appear):
    """letters fall from above and bounce into place"""
    name = 'drop'
    duration = 0.55

    @staticmethod
    def bounce(t):
        n1, d1 = 7.5625, 2.75
        if t < 1 / d1:
            return n1 * t * t
        if t < 2 / d1:
            t -= 1.5 / d1
            return n1 * t * t + 0.75
        if t < 2.5 / d1:
            t -= 2.25 / d1
            return n1 * t * t + 0.9375
        t -= 2.625 / d1
        return n1 * t * t + 0.984375

    def draw(self, surf, ox, oy):
        off = -(1 - self.bounce(self.k)) * self.ch * 3
        surf.blit(self.glyph(), (ox + self.px, oy + self.py + off))


class Glitch(Appear):
    """chromatic aberration glitch-in"""
    name = 'glitch'
    duration = 0.4

    def draw(self, surf, ox, oy):
        k = self.k
        x0, y0 = ox + self.px, oy + self.py
        a = int(4 * (1 - k)) + 1
        for col, dx in (((255, 0, 60), -a), ((0, 255, 200), a)):
            if rnd() < 0.85:
                surf.blit(self.m.renderer.colored(self.c, self.style, False, col),
                          (x0 + dx + random.randint(-1, 1), y0 + random.randint(-1, 1)),
                          special_flags=pygame.BLEND_RGB_ADD)
        if k > 0.5:
            surf.blit(self.glyph(), (x0, y0))


class Pop(Appear):
    """letter zooms in from big & translucent"""
    name = 'pop'
    duration = 0.35

    def draw(self, surf, ox, oy):
        k = self.k
        s = 1 + 2.5 * (1 - k) ** 2
        g = self.glyph()
        w, h = int(self.cw * s), int(self.ch * s)
        z = pygame.transform.scale(g, (w, h))
        blit_alpha(surf, z, (ox + self.px - (w - self.cw) // 2, oy + self.py - (h - self.ch) // 2), 255 * k)


class Bump(Appear):
    """jump'n'run: the letter gets bumped from below and a coin pops out"""
    name = 'bump'
    duration = 0.5

    def draw(self, surf, ox, oy):
        k = self.k
        up = math.sin(min(1.0, k / 0.35) * math.pi) * self.ch * 0.35 if k < 0.35 else 0
        surf.blit(self.glyph(), (ox + self.px, oy + self.py - up))
        # coin
        if k < 0.9:
            cy = oy + self.py - self.ch * 0.4 - math.sin(k / 0.9 * math.pi) * self.ch * 1.6
            spin = abs(math.cos(self.t * 18))
            w = max(1, int(self.cw * 0.7 * spin))
            h = int(self.ch * 0.7)
            cx = ox + self.px + self.cw // 2
            pygame.draw.ellipse(surf, (255, 210, 40), (cx - w // 2, cy, w, h))
            if w > 2:
                pygame.draw.ellipse(surf, (255, 250, 180), (cx - w // 4, cy + 1, max(1, w // 3), max(1, h // 2)))


class Shoot(Appear):
    """arcade: a shot from the cannon at the bottom hits the cell, the letter flashes in"""
    name = 'shoot'
    duration = 0.4
    TARGETS = []   # columns for the invaders background cannon to aim at

    def start(self):
        Shoot.TARGETS.append(self.x / max(1, self.m.cols))
        del Shoot.TARGETS[:-32]

    def draw(self, surf, ox, oy):
        k = self.k
        bottom = oy + (self.m.voff + self.m.rows) * self.ch
        x = ox + self.px + self.cw // 2
        top = oy + self.py + self.ch
        if k < 0.55:
            y = bottom + (top - bottom) * (k / 0.55)
            surf.fill((255, 255, 255), (x, y - self.ch // 2, max(1, self.cw // 6), self.ch // 2))
        else:
            q = (k - 0.55) / 0.45
            if q < 0.4:
                r = int(self.cw * (0.4 + q * 1.5))
                for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1), (0, 1), (-1, 0), (1, 0)):
                    surf.fill((255, 255, 255), (ox + self.px + self.cw // 2 + dx * r // 2, oy + self.py + self.ch // 2 + dy * r // 2, 1, 1))
            blit_alpha(surf, self.glyph(quant(lerp_rgb((255, 255, 255), self.rgb, q))), (ox + self.px, oy + self.py), 120 + 135 * q)


class Puff(Appear):
    """a little steam/smoke puff pops, and the letter is revealed inside it"""
    name = 'puff'
    duration = 0.45

    def start(self):
        n = 10
        a = np.random.uniform(0, 6.283, n).astype(np.float32)
        sp = np.random.uniform(8, 25, n).astype(np.float32)
        self.m.particles.emit(n, self.px + self.cw / 2 + np.cos(a) * 2, self.py + self.ch / 2 + np.sin(a) * 2,
                              vx=np.cos(a) * sp, vy=np.sin(a) * sp - 15, drag=2.0,
                              life=np.random.uniform(0.35, 0.7, n).astype(np.float32), col=(235, 235, 240), pal=P.FADE)

    def draw(self, surf, ox, oy):
        k = self.k
        cx, cy = ox + self.px + self.cw // 2, oy + self.py + self.ch // 2
        if k < 0.6:
            r = int(self.cw * (0.3 + k * 1.2))
            v = int(240 - 60 * k)
            for dx, dy in ((-1, 0), (1, 0), (0, -1)):
                pygame.draw.circle(surf, (v, v, v), (cx + dx * r // 2, cy + dy * r // 3), max(1, r // 2))
        blit_alpha(surf, self.glyph(), (ox + self.px, oy + self.py), 255 * max(0.0, (k - 0.3) / 0.7))


class Neon(Appear):
    """the letter flickers on like a neon tube, with a colored glow"""
    name = 'neon'
    duration = 0.6

    def start(self):
        self.pattern = [rnd() < 0.5 for _ in range(8)]

    def draw(self, surf, ox, oy):
        k = self.k
        i = int(k * 8)
        on = k > 0.85 or (i < 8 and self.pattern[i])
        x, y = ox + self.px, oy + self.py
        if not on:
            blit_alpha(surf, self.glyph(quant(lerp_rgb((0, 0, 0), self.rgb, 0.25))), (x, y), 255)
            return
        hot = quant(lerp_rgb((255, 255, 255), self.rgb, k))
        glow = self.glyph(quant(lerp_rgb((0, 0, 0), self.rgb, 0.5)))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            surf.blit(glow, (x + dx, y + dy), special_flags=pygame.BLEND_RGB_ADD)
        surf.blit(self.glyph(hot), (x, y))


class Chisel(Appear):
    """the letter is chiseled into the stone stroke by stroke, top to bottom; stone dust trickles
    down and little chips fly off at the chisel's edge"""
    name = 'chisel'
    duration = 0.55

    def start(self):
        xs, ys = self.pixels()
        self.rows = sorted(set(int(y) for y in ys)) if len(ys) else []
        self.xs, self.ys = xs, ys
        self.last_emit = 0.0

    def tip(self):
        k = self.k
        if not self.rows:
            return self.px + self.cw / 2, self.py + self.ch / 2
        i = min(len(self.rows) - 1, int(k * len(self.rows)))
        y = self.rows[i]
        sel = self.xs[self.ys.astype(int) == y]
        if len(sel) == 0:
            return self.px + self.cw / 2, self.py + y
        swing = 0.5 + 0.5 * math.sin(self.t * 40)
        return self.px + float(sel.min() + (sel.max() - sel.min()) * swing), self.py + y

    def update(self, dt):
        self.t += dt
        if self.t < self.dur:
            self.last_emit += dt
            if self.last_emit > 0.03:
                self.last_emit = 0
                x, y = self.tip()
                n = 3
                self.m.particles.emit(n, np.full(n, x, np.float32), np.full(n, y, np.float32),
                                      vx=np.random.uniform(-25, 25, n).astype(np.float32),
                                      vy=np.random.uniform(-40, 0, n).astype(np.float32), grav=320, drag=0.8,
                                      life=np.random.uniform(0.5, 1.1, n).astype(np.float32), col=(70, 66, 56), pal=P.FADE, add=True)
                if rnd() < 0.35:            # a chip of stone flying off
                    self.m.particles.emit(1, np.float32(x), np.float32(y), vx=np.float32(random.choice((-1, 1)) * random.uniform(40, 90)),
                                          vy=np.float32(-random.uniform(40, 90)), grav=500, life=np.float32(0.6),
                                          col=(150, 136, 118), pal=P.SOLID)
            return True
        # last puff of dust
        n = 8
        self.m.particles.emit(n, self.px + np.random.uniform(0, self.cw, n).astype(np.float32),
                              np.full(n, self.py + self.ch, np.float32), vx=np.random.uniform(-10, 10, n).astype(np.float32),
                              vy=np.random.uniform(-10, 5, n).astype(np.float32), grav=120, drag=2,
                              life=np.random.uniform(0.4, 0.9, n).astype(np.float32), col=(60, 56, 48), pal=P.FADE, add=True)
        return False

    def draw(self, surf, ox, oy):
        k = self.k
        g = self.glyph()
        hgt = int(self.ch * min(1.0, k * 1.05))
        if hgt > 0:
            surf.blit(g, (ox + self.px, oy + self.py), (0, 0, self.cw, hgt))
        if k < 1 and int(self.t * 30) % 2:
            x, y = self.tip()                    # the edge biting into the stone: a tiny spark
            surf.fill((255, 246, 220), (int(ox + x), int(oy + y), 1, 1))


class Breach(Appear):
    """the cell is breached: raw bits, then hex under a targeting bracket and a scan line,
    then the real letter snaps in with an RGB split and cools from white to its color"""
    name = 'breach'
    duration = 0.5
    HEX = '0123456789ABCDEF'
    CY, MG = (0, 255, 208), (255, 48, 128)

    def draw(self, surf, ox, oy):
        k = self.k
        x, y = ox + self.px, oy + self.py
        cw, ch = self.cw, self.ch
        col = self.m.renderer.colored
        if k < 0.3:
            surf.blit(col(random.choice('01'), self.style, False, (0, 120, 100)), (x, y))
        elif k < 0.68:
            surf.blit(col(random.choice(self.HEX), self.style, False, self.CY), (x, y))
        elif k < 0.88:
            a = 1 + int((0.88 - k) * 12)
            surf.blit(col(self.c, self.style, False, self.CY), (x - a, y), special_flags=pygame.BLEND_RGB_ADD)
            surf.blit(col(self.c, self.style, False, self.MG), (x + a, y), special_flags=pygame.BLEND_RGB_ADD)
            surf.blit(col(self.c, self.style, False, (255, 255, 255)), (x, y))
        else:
            surf.blit(self.glyph(quant(lerp_rgb((255, 255, 255), self.rgb, (k - 0.88) / 0.12))), (x, y))
        if k < 0.88:
            surf.fill((0, 96, 80), (x, y + int(k / 0.88 * (ch - 1)), cw, 1), special_flags=pygame.BLEND_RGB_ADD)
            if k >= 0.3:                                    # targeting bracket
                c = (0, 150, 124)
                for bx, by in ((x, y), (x + cw - 2, y), (x, y + ch - 1), (x + cw - 2, y + ch - 1)):
                    surf.fill(c, (bx, by, 2, 1))


class Random(Appear):
    name = 'random'


APPEAR = {c.name: c for c in (Instant, Flame, Laser, Sand, Dissolve, Construction, Teleport, Fluid,
                              Decrypt, Drop, Glitch, Pop, Bump, Shoot, Puff, Neon, Chisel, Breach)}
RANDOM_POOL = ['flame', 'laser', 'sand', 'dissolve', 'construction', 'teleport', 'fluid', 'decrypt', 'drop', 'glitch',
               'pop', 'bump', 'puff', 'neon', 'chisel', 'breach']


# ============================================================================ vanish
def _glyph_px(m, c, attr, x, vy):
    f, bgc, style, fl = m.renderer.resolve(attr)
    xs, ys = m.font.pixels(c, style)
    return (x * m.cw + xs).astype(np.float32), (vy * m.ch + ys).astype(np.float32), (f or (200, 200, 200))


def v_shatter(m, x, vy, c, attr):
    X, Y, rgb = _glyph_px(m, c, attr, x, vy)
    n = len(X)
    if not n:
        return
    cx, cy = x * m.cw + m.cw / 2, vy * m.ch + m.ch / 2
    dx, dy = X - cx, Y - cy
    sp = np.random.uniform(40, 140, n).astype(np.float32)
    nn = np.sqrt(dx * dx + dy * dy) + 0.5
    m.particles.emit(n, X, Y, vx=dx / nn * sp, vy=dy / nn * sp - 60, grav=420, drag=0.5,
                     life=np.random.uniform(0.4, 0.9, n).astype(np.float32), col=rgb, pal=P.FADE)


def v_dust(m, x, vy, c, attr):
    X, Y, rgb = _glyph_px(m, c, attr, x, vy)
    n = len(X)
    if not n:
        return
    m.particles.emit(n, X, Y, vx=np.random.uniform(10, 50, n).astype(np.float32),
                     vy=np.random.uniform(-40, -5, n).astype(np.float32), drag=1.2,
                     life=np.random.uniform(0.5, 1.3, n).astype(np.float32), col=rgb, pal=P.FADE, add=True,
                     delay=((X - x * m.cw) / m.cw * 0.2).astype(np.float32))


def v_burn(m, x, vy, c, attr):
    X, Y, rgb = _glyph_px(m, c, attr, x, vy)
    n = len(X)
    if not n:
        return
    m.particles.emit(n, X, Y, vx=np.random.uniform(-10, 10, n).astype(np.float32),
                     vy=np.random.uniform(-90, -30, n).astype(np.float32),
                     life=np.random.uniform(0.3, 0.8, n).astype(np.float32), pal=P.FIRE, add=True,
                     delay=((m.ch - (Y - vy * m.ch)) / m.ch * 0.15).astype(np.float32))


def v_melt(m, x, vy, c, attr):
    X, Y, rgb = _glyph_px(m, c, attr, x, vy)
    n = len(X)
    if not n:
        return
    m.particles.emit(n, X, Y, vy=np.random.uniform(0, 20, n).astype(np.float32), grav=260,
                     life=np.random.uniform(0.5, 1.0, n).astype(np.float32), col=rgb, pal=P.FADE,
                     delay=np.random.uniform(0, 0.25, n).astype(np.float32))


def v_rainbow(m, x, vy, c, attr):
    X, Y, rgb = _glyph_px(m, c, attr, x, vy)
    n = len(X)
    if not n:
        return
    ang = np.random.uniform(0, 6.283, n).astype(np.float32)
    sp = np.random.uniform(30, 110, n).astype(np.float32)
    m.particles.emit(n, X, Y, vx=np.cos(ang) * sp, vy=np.sin(ang) * sp, drag=1.5, add=True,
                     life=np.random.uniform(0.4, 1.0, n).astype(np.float32), pal=P.RAINBOW)


def v_bricks(m, x, vy, c, attr):
    """the letter breaks into four brick chunks that tumble away"""
    X, Y, rgb = _glyph_px(m, c, attr, x, vy)
    n = len(X)
    if not n:
        return
    cx, cy = x * m.cw + m.cw / 2, vy * m.ch + m.ch / 2
    qx = np.where(X < cx, -1.0, 1.0).astype(np.float32)
    qy = np.where(Y < cy, -1.0, 0.4).astype(np.float32)
    m.particles.emit(n, X, Y, vx=qx * 70, vy=qy * 160 - 80, grav=700, life=0.9, col=(200, 90, 40), pal=P.SOLID)


_BOOM = ['X.X.X', '.XXX.', 'XX.XX', '.XXX.', 'X.X.X']


def v_invader(m, x, vy, c, attr):
    """arcade explosion sprite, then it fades"""
    pts = [(i, j) for j, row in enumerate(_BOOM) for i, ch in enumerate(row) if ch == 'X']
    k = max(1, m.cw // 5)
    X = np.array([x * m.cw + i * k for i, j in pts], np.float32)
    Y = np.array([vy * m.ch + m.ch // 2 - 5 * k // 2 + j * k for i, j in pts], np.float32)
    n = len(X)
    m.particles.emit(n, X, Y, vx=(X - X.mean()) * 4, vy=(Y - Y.mean()) * 4, drag=3, life=0.45,
                     col=(255, 255, 255), pal=P.FADE)


def v_spark(m, x, vy, c, attr):
    """short circuit: a blue-white flash, sparks shower down, the tube goes dark"""
    X, Y, rgb = _glyph_px(m, c, attr, x, vy)
    n = len(X)
    if not n:
        return
    m.particles.emit(n, X, Y, life=np.random.uniform(0.15, 0.35, n).astype(np.float32), col=(200, 230, 255),
                     pal=P.FADE, add=True)
    k = max(6, n // 3)
    sel = np.random.randint(0, n, k)
    ang = np.random.uniform(-2.8, -0.3, k).astype(np.float32)
    sp = np.random.uniform(40, 130, k).astype(np.float32)
    m.particles.emit(k, X[sel], Y[sel], vx=np.cos(ang) * sp, vy=np.sin(ang) * sp, grav=500, drag=0.4,
                     life=np.random.uniform(0.3, 0.8, k).astype(np.float32), pal=P.FIRE, add=True,
                     delay=np.random.uniform(0, 0.1, k).astype(np.float32))


def v_firework(m, x, vy, c, attr):
    """the letter bursts like a tiny firework into colorful pixels"""
    X, Y, rgb = _glyph_px(m, c, attr, x, vy)
    n = len(X)
    if not n:
        return
    k = n * 2
    cx, cy = float(X.mean()), float(Y.mean())
    ang = np.random.uniform(0, 6.283, k).astype(np.float32)
    sp = np.random.uniform(30, 90, k).astype(np.float32)
    pal = np.array([(255, 80, 80), (255, 210, 60), (80, 200, 255), (120, 255, 120), (255, 120, 255), (255, 255, 255)], np.float32)
    col = pal[np.random.randint(0, len(pal))]
    m.particles.emit(k, cx + np.cos(ang) * 1.5, cy + np.sin(ang) * 1.5, vx=np.cos(ang) * sp, vy=np.sin(ang) * sp - 20,
                     grav=90, drag=1.8, life=np.random.uniform(0.5, 1.1, k).astype(np.float32), col=tuple(int(v) for v in col),
                     pal=P.SPARKLE, add=True)


def v_leaves(m, x, vy, c, attr):
    """the letter falls apart into autumn leaves that flutter down"""
    X, Y, rgb = _glyph_px(m, c, attr, x, vy)
    n = len(X)
    if not n:
        return
    sel = np.random.randint(0, n, max(3, n // 2))
    k = len(sel)
    col = random.choice([(220, 70, 30), (240, 130, 30), (250, 190, 50), (180, 50, 30)])
    m.particles.emit(k, X[sel], Y[sel], vx=np.random.uniform(-25, 25, k).astype(np.float32),
                     vy=np.random.uniform(-10, 10, k).astype(np.float32), grav=40, drag=2.5,
                     life=np.random.uniform(0.8, 1.6, k).astype(np.float32), col=col, pal=P.FADE)


def v_snow(m, x, vy, c, attr):
    """the letter melts into snowflakes drifting down"""
    X, Y, rgb = _glyph_px(m, c, attr, x, vy)
    n = len(X)
    if not n:
        return
    m.particles.emit(n, X, Y, vx=np.random.uniform(-12, 12, n).astype(np.float32),
                     vy=np.random.uniform(5, 25, n).astype(np.float32), drag=1.0,
                     life=np.random.uniform(0.7, 1.6, n).astype(np.float32), col=(230, 240, 255), pal=P.FADE,
                     delay=np.random.uniform(0, 0.2, n).astype(np.float32))


def v_petals(m, x, vy, c, attr):
    """pink cherry petals blow away to the right"""
    X, Y, rgb = _glyph_px(m, c, attr, x, vy)
    n = len(X)
    if not n:
        return
    sel = np.random.randint(0, n, max(3, n // 2))
    k = len(sel)
    m.particles.emit(k, X[sel], Y[sel], vx=np.random.uniform(20, 60, k).astype(np.float32),
                     vy=np.random.uniform(-15, 15, k).astype(np.float32), grav=15, drag=1.2,
                     life=np.random.uniform(0.8, 1.6, k).astype(np.float32), col=(255, 190, 215), pal=P.FADE)


def v_crumble(m, x, vy, c, attr):
    """the carved letter crumbles: stone chips tumble down, dust drifts up"""
    X, Y, rgb = _glyph_px(m, c, attr, x, vy)
    n = len(X)
    if not n:
        return
    sel = np.random.randint(0, n, max(4, n // 3))
    k = len(sel)
    m.particles.emit(k, X[sel], Y[sel], vx=np.random.uniform(-35, 35, k).astype(np.float32),
                     vy=np.random.uniform(-50, 10, k).astype(np.float32), grav=520,
                     life=np.random.uniform(0.6, 1.1, k).astype(np.float32), col=(150, 136, 118), pal=P.SOLID)
    m.particles.emit(n, X, Y, vx=np.random.uniform(-12, 12, n).astype(np.float32),
                     vy=np.random.uniform(-25, -5, n).astype(np.float32), drag=1.6,
                     life=np.random.uniform(0.5, 1.2, n).astype(np.float32), col=(64, 60, 50), pal=P.FADE, add=True)


def v_derez(m, x, vy, c, attr):
    """de-rezzed: a white flash, then the letter's scan lines are torn apart sideways -
    even rows to the left in cyan, odd rows to the right in magenta"""
    X, Y, rgb = _glyph_px(m, c, attr, x, vy)
    n = len(X)
    if not n:
        return
    row = (Y - vy * m.ch).astype(np.int32)
    odd = (row & 1).astype(np.float32)
    sp = (np.random.randint(2, 8, n) * 28).astype(np.float32)
    col = np.where(odd[:, None] > 0, np.float32((255, 48, 128)), np.float32((0, 255, 208)))
    m.particles.emit(n, X, Y, life=0.09, col=(255, 255, 255), pal=P.FADE, add=True)
    m.particles.emit(n, X, Y, vx=(odd * 2 - 1) * sp, drag=2.5, life=np.random.uniform(0.25, 0.6, n).astype(np.float32),
                     col=col, pal=P.FADE, add=True, delay=(row / max(1, m.ch) * 0.12).astype(np.float32))


def v_random(m, x, vy, c, attr):
    random.choice(_VANISH_POOL)(m, x, vy, c, attr)


VANISH = {'none': None, 'random': v_random, 'spark': v_spark, 'crumble': v_crumble, 'firework': v_firework, 'leaves': v_leaves,
          'snow': v_snow, 'petals': v_petals, 'shatter': v_shatter, 'dust': v_dust, 'burn': v_burn, 'melt': v_melt,
          'rainbow': v_rainbow, 'bricks': v_bricks, 'invader': v_invader, 'derez': v_derez}
_VANISH_POOL = [v_crumble, v_firework, v_spark, v_shatter, v_dust, v_burn, v_melt, v_rainbow, v_bricks, v_invader, v_derez]


# ============================================================================ manager
class EffectsManager:
    def __init__(self, renderer, font, max_effects=900, max_particles=120000):
        self.renderer = renderer
        self.font = font
        self.cw, self.ch = font.cw, font.ch
        self.cols = self.rows = 1
        self.particles = P.Particles(max_particles, size=max(1, round(font.ch / 18)))
        self.active = {}            # (x, vy) -> Appear
        self.voff = 0               # virtual row offset
        self.max_effects = max_effects
        self.appear_name = 'none'
        self.vanish_name = 'none'
        self.speed = 1.0
        self.miner = None           # set by app when emerald-mine mode is on
        self.near = None            # (x, y, r): only animate letters within r cells of this cell (full-screen apps)
        self._hidden_prev = {}
        self.vanish_budget = 1200
        self.spawn_budget = 180      # new letter effects per frame (rest appear instantly)
        self.stats = {'puts': 0, 'dels': 0, 'nl': 0, 'last': ' ', 'bell': 0}
        self.listeners = []         # plugins: fn(ev)

    def set_font(self, font):
        self.font = font
        self.cw, self.ch = font.cw, font.ch
        self.particles.size = max(1, round(font.ch / 18))
        self.clear()

    def resize(self, cols, rows):
        self.cols, self.rows = cols, rows

    def clear(self):
        self.active.clear()
        self.particles.clear()
        if self.miner:
            self.miner.reset_pending()

    # ------------------------------------------------------------ events
    def process(self, events):
        st = self.stats
        st['puts'] = st['dels'] = st['nl'] = st['bell'] = 0
        if not events:
            return
        rows = self.rows
        # suffix sum of full-screen scrolls: skip effects for letters that are
        # scrolled away before this frame is even drawn
        suffix = [0] * (len(events) + 1)
        acc = 0
        for i in range(len(events) - 1, -1, -1):
            e = events[i]
            if e[0] == EV_SCROLL and e[1] == 0 and e[2] == rows - 1:
                acc += e[3]
            suffix[i] = acc
        cls = APPEAR.get(self.appear_name, Instant)
        vanish = VANISH.get(self.vanish_name)
        load = len(self.active) / max(1, self.max_effects)
        self.speed = max(0.35, 1.0 - load * 0.65)
        budget = self.vanish_budget
        spawn = self.spawn_budget
        voff = self.voff
        miner = self.miner
        active = self.active
        for i, e in enumerate(events):
            t = e[0]
            if t == EV_PUT:
                _, x, y, c, attr = e
                st['puts'] += 1
                st['last'] = c
                key = (x, y + voff)
                active.pop(key, None)
                if y - suffix[i + 1] < 0:
                    continue
                if miner is not None:
                    miner.enqueue(x, y + voff)
                    continue
                if cls is Instant or spawn <= 0 or len(active) >= self.max_effects:
                    continue
                near = self.near
                if near is not None and (abs(y - near[1]) > 0 or abs(x - near[0]) > near[2]):
                    continue
                spawn -= 1
                k = cls
                if cls is Random:
                    k = APPEAR[random.choice(RANDOM_POOL)]
                eff = k(self, x, y + voff, c, attr)
                if eff.dur > 0:
                    active[key] = eff
            elif t == EV_DEL:
                _, x, y, c, attr = e
                st['dels'] += 1
                key = (x, y + voff)
                if active.pop(key, None) is not None:
                    continue
                if miner is not None:
                    miner.cell_cleared(x, y + voff)
                near = self.near
                if near is not None and (y != near[1] or abs(x - near[0]) > near[2]):
                    continue
                if vanish and budget > 0 and y - suffix[i + 1] >= 0 and self.particles.free > 200:
                    budget -= 1
                    vanish(self, x, y + voff, c, attr)
            elif t == EV_SCROLL:
                _, top, bot, n = e
                if n == 0:
                    vy = top + voff
                    for key in [k for k in active if k[1] == vy]:
                        del active[key]
                    if miner is not None:
                        miner.row_changed(vy)
                elif top == 0 and bot == rows - 1:
                    voff += n
                    self.voff = voff
                    if miner is not None:
                        miner.scrolled(n)
                else:
                    self._partial_scroll(top, bot, n)
            elif t == EV_RESET:
                active.clear()
                if miner is not None:
                    miner.reset_pending()
            elif t == 6:
                st['nl'] += 1
            elif t == 5:
                st['bell'] += 1
            if self.listeners and t in (EV_PUT, EV_DEL):
                for fn in self.listeners:
                    fn(e)

    def _partial_scroll(self, top, bot, n):
        voff = self.voff
        new = {}
        for (x, vy), eff in self.active.items():
            y = vy - voff
            if top <= y <= bot:
                y2 = y - n
                if top <= y2 <= bot:
                    eff.moved(-n)
                    new[(x, vy - n)] = eff
            else:
                new[(x, vy)] = eff
        self.active = new
        self.particles.shift((top + voff) * self.ch, (bot + 1 + voff) * self.ch, -n * self.ch)
        if self.miner is not None:
            self.miner.partial_scroll(top + voff, bot + voff, n)

    # ------------------------------------------------------------ frame
    def update(self, dt):
        voff = self.voff
        dead = []
        for key, eff in self.active.items():
            if key[1] < voff or not eff.update(dt):
                dead.append(key)
        for key in dead:
            self.active.pop(key, None)
        self.particles.update(dt)

    def hidden_rows(self, renderer):
        """map screen row -> set of hidden columns; marks changed rows dirty"""
        voff = self.voff
        rows = self.rows
        hid = {}
        for (x, vy) in self.active:
            y = vy - voff
            if 0 <= y < rows:
                s = hid.get(y)
                if s is None:
                    hid[y] = {x}
                else:
                    s.add(x)
        if self.miner is not None:
            for (x, vy) in self.miner.pending:
                y = vy - voff
                if 0 <= y < rows:
                    hid.setdefault(y, set()).add(x)
        prev = self._hidden_prev
        dirty = renderer.extra_dirty
        # previous map was in virtual rows; convert for comparison
        pv = self._prev_voff if hasattr(self, '_prev_voff') else voff
        shift = voff - pv
        for y, s in prev.items():
            y2 = y - shift
            if 0 <= y2 < rows and hid.get(y2) != s:
                dirty.add(y2)
        for y, s in hid.items():
            ps = prev.get(y + shift)
            if ps != s:
                dirty.add(y)
        self._hidden_prev = hid
        self._prev_voff = voff
        return hid

    def draw(self, surf, ox, oy):
        """ox, oy: pixel position of terminal cell (0,0) on surf"""
        vy0 = oy - self.voff * self.ch
        for eff in self.active.values():
            eff.draw(surf, ox, vy0)
        self.particles.draw(surf, ox, vy0)
