"""Example: a custom cursor style and a custom cursor effect.

    cursor_style: ghost              # a little floating ghost is the cursor
    cursor_effects: [comet]          # a glowing comet chases the cursor

Try them live in the demo shell:  cursor ghost comet   (or Ctrl+Shift+U)
"""
import math

import pygame

PLUGIN = {'name': 'cursor_demo', 'description': 'adds cursor style "ghost" and cursor effect "comet"'}

GHOST = [".WWW.",
         "WWWWW",
         "WOWOW",
         "WWWWW",
         "WWWWW",
         "W.W.W"]


def register(api):
    from pyterm.cursors import CursorEffect, CursorStyle

    class Ghost(CursorStyle):
        """bobs up and down, glides to the cursor, blushes when you type"""
        character = True               # stays visible (outlined) in unfocused panes

        def start(self):
            self.x = self.y = None
            self.blush = 0.0
            self._img = {}

        def sprite(self, k, rgb):
            key = (k, rgb)
            if key not in self._img:
                s = pygame.Surface((5, 6), pygame.SRCALPHA)
                for y, row in enumerate(GHOST):
                    for x, c in enumerate(row):
                        if c == 'W':
                            s.set_at((x, y), rgb + (230,))
                        elif c == 'O':
                            s.set_at((x, y), (20, 20, 40, 255))
                self._img[key] = pygame.transform.scale(s, (5 * k, 6 * k))
            return self._img[key]

        def update(self, dt, st):
            if self.x is None:
                self.x, self.y = st.x, st.y
            f = min(1.0, dt * 14)
            self.x += (st.x - self.x) * f
            self.y += (st.y - self.y) * f
            if st.typed:
                self.blush = 0.4
            self.blush = max(0.0, self.blush - dt)

        def draw(self, surf, ox, oy, st):
            if self.x is None:
                return
            k = max(1, st.ch // 8)
            img = self.sprite(k, (255, 190, 210) if self.blush else (235, 240, 255))
            bob = math.sin(st.t * 4) * k
            x = ox + self.x + (st.cw - img.get_width()) // 2
            y = oy + self.y + st.ch - img.get_height() - k + bob
            surf.blit(img, (int(x), int(y)))
            if not st.focused:
                pygame.draw.rect(surf, st.rgb, (ox + st.x, oy + st.y, st.cw, st.ch), 1)

        def busy(self):
            return True

    class Comet(CursorEffect):
        """a glowing head that chases the cursor with a fading tail"""
        layer = 'over'
        defaults = {'length': 14}

        def start(self):
            self.pts = []
            self.pos = None

        def update(self, dt, st):
            tgt = (st.x + st.cw / 2, st.y + st.ch / 2)
            if self.pos is None:
                self.pos = list(tgt)
            f = min(1.0, dt * 9)
            self.pos[0] += (tgt[0] - self.pos[0]) * f
            self.pos[1] += (tgt[1] - self.pos[1]) * f
            self.pts.append(tuple(self.pos))
            del self.pts[:-int(self.p('length', 14))]

        def draw(self, surf, ox, oy, st):
            if not st.focused:
                return
            rgb = self.color('color', st)
            n = len(self.pts)
            for i, (x, y) in enumerate(self.pts):
                k = (i + 1) / n
                c = tuple(int(v * k) for v in rgb)
                r = 1 + int(k * 2)
                surf.fill(c, (int(ox + x) - r // 2, int(oy + y) - r // 2, r, r), special_flags=pygame.BLEND_RGB_ADD)

        def busy(self):
            return len(self.pts) > 1 and self.pts[0] != self.pts[-1]

    api.register_cursor('ghost', Ghost)
    api.register_cursor_effect('comet', Comet)
