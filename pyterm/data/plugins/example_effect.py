"""Example: a custom letter effect, delete effect and background.
Use them like the built-ins:  letter_effect: spiral  /  delete_effect: confetti
/  background: [rain]   (or pick them in the Studio)."""
import random

import numpy as np
import pygame

PLUGIN = {'name': 'example_effect', 'description': 'adds letter fx "spiral", delete fx "confetti", bg "rain"'}


def register(api):
    from pyterm import particles as P
    from pyterm.backgrounds import Background
    from pyterm.effects import Appear

    class Spiral(Appear):
        """pixels spiral in from a ring around the letter"""
        duration = 0.6

        def start(self):
            xs, ys = self.pixels()
            n = len(xs)
            if not n:
                return
            ang = np.random.uniform(0, 6.283, n).astype(np.float32)
            r = self.ch * 1.5
            tx = (self.px + xs).astype(np.float32)
            ty = (self.py + ys).astype(np.float32)
            self.m.particles.emit(n, tx + np.cos(ang) * r, ty + np.sin(ang) * r, kind=P.HOMING, tx=tx, ty=ty,
                                  travel=self.dur * 0.9, ease=P.BACK, life=self.dur + 0.05, col=self.rgb, pal=P.COOL)

    def confetti(m, x, vy, c, attr):
        n = 14
        cols = np.array([[255, 60, 90], [60, 255, 140], [80, 160, 255], [255, 230, 60]], np.float32)
        m.particles.emit(n, np.float32(x * m.cw + m.cw / 2), np.float32(vy * m.ch + m.ch / 2),
                         vx=np.random.uniform(-90, 90, n).astype(np.float32),
                         vy=np.random.uniform(-160, -40, n).astype(np.float32), grav=380, drag=0.8,
                         life=np.random.uniform(0.5, 1.0, n).astype(np.float32), col=cols[np.random.randint(0, 4, n)])

    class Rain(Background):
        def resize(self, w, h):
            super().resize(w, h)
            self.drops = [[random.uniform(0, w), random.uniform(0, h), random.uniform(120, 260)] for _ in range(160)]

        def update(self, dt, energy):
            for d in self.drops:
                d[1] += d[2] * dt * (1 + energy)
                if d[1] > self.h:
                    d[0], d[1] = random.uniform(0, self.w), -5

        def draw(self, surf, first):
            if first:
                surf.fill((4, 8, 16))
            for x, y, s in self.drops:
                pygame.draw.line(surf, (70, 110, 170), (x, y), (x - 1, y + s / 30))

    api.register_letter_effect('spiral', Spiral)
    api.register_delete_effect('confetti', confetti)
    api.register_background('rain', Rain)
