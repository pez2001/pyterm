"""Classic Amiga sine scroller with a big demo font: every 2-pixel column of
the text rides its own point of the sine wave, so the letters bend and roll
like in a 1990 cracktro. Used by the boot intro and plugins/sine_scroller.py.

    sc = SineScroller('HELLO SCENE!   ', font='builtin:scroller')
    sc.update(dt)
    sc.draw(surf, rect, y_center, amplitude)
"""
from __future__ import annotations

import math

from . import fonts

_FONTS = {}


def get_font(spec):
    f = _FONTS.get(spec)
    if f is None:
        f = _FONTS[spec] = fonts.load_font(spec)
    return f


class SineScroller:
    def __init__(self, text, font='builtin:scroller', speed=120.0, wave=0.018, wobble=3.0, strip=2):
        self.text = text or ' '
        self.font = get_font(font)
        self.speed, self.wave, self.wobble, self.strip = speed, wave, wobble, strip
        self.x = 0.0
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        self.x += dt * self.speed

    def draw(self, surf, rect, yc, amp):
        f = self.font
        if f.animated:
            f.set_frame(int(self.t * f.fps))
        step = f.cw - 3                       # glyph cells carry outline + shadow padding
        start = int(self.x // step)
        off = self.x % step
        st = self.strip
        t = self.t
        for i in range(rect.width // step + 2):
            c = self.text[(start + i) % len(self.text)]
            if c == ' ':
                continue
            g = f.glyph(c)
            gw, gh = g.get_size()
            gx = rect.x + i * step - off
            for sx in range(0, gw, st):
                X = gx + sx
                if X < rect.x - st or X > rect.right:
                    continue
                dy = math.sin(X * self.wave + t * self.wobble) * amp
                surf.blit(g, (X, yc - gh // 2 + dy), (sx, 0, st, gh))
