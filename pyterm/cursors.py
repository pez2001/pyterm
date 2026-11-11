"""Cursor styles and cursor effects.

Two plug-in points, both selected per theme:

    cursor_style: block                 # ONE style - draws the cursor itself
    cursor_effects: [glow, trail]       # any number of effects layered on top
    cursor_params: {trail: {count: 10}, ripple: {color: '#ff40c0'}}

Built-in styles   block underline beam outline   miner hero settler train
Built-in effects  glow trail ripple sparkle orbit smoke reticle

Write your own (in a plugin, see plugins/cursor_demo.py):

    from pyterm.cursors import CursorStyle, CursorEffect

    class Ghost(CursorStyle):
        def draw(self, surf, ox, oy, st): ...

    def register(api):
        api.register_cursor('ghost', Ghost)
        api.register_cursor_effect('halo', Halo)

Every frame the pane hands the active style and effects a ``CursorState``
(``st``) describing what happened: where the cursor is, how many letters
were typed, whether Enter/bell happened, focus, eco mode ...
"""
from __future__ import annotations

import math
import random

import numpy as np
import pygame

from . import particles as P
from .themes import hex2rgb


class CursorState:
    """what the cursor did this frame (filled in by the pane)"""
    __slots__ = ('cx', 'cy', 'x', 'y', 'cw', 'ch', 'voff', 'moved', 'typed', 'newline', 'bell', 'focused',
                 'visible', 'alt', 'eco', 't', 'dt', 'rgb', 'screen', 'mine')

    def __init__(self):
        self.cx = self.cy = 0          # cell coordinates
        self.x = self.y = 0            # pixel position of the cell, relative to the pane origin
        self.cw = self.ch = 8          # cell size in virtual pixels
        self.voff = 0                  # virtual row offset (for particles: y + voff * ch)
        self.moved = False             # cursor moved to another cell this frame
        self.typed = 0                 # letters printed this frame
        self.newline = False
        self.bell = False
        self.focused = True
        self.visible = True
        self.alt = False               # full-screen app (vim, htop ...) running
        self.eco = False
        self.t = 0.0
        self.dt = 0.0
        self.rgb = (255, 204, 0)       # theme cursor color
        self.screen = None             # vt.Screen
        self.mine = None               # EMERALD MINE world or None


class _Base:
    name = 'base'
    defaults = {}

    def __init__(self, pane, params=None):
        self.pane = pane
        self.params = dict(self.defaults)
        self.params.update(params or {})
        self.start()

    def p(self, key, default=None):
        return self.params.get(key, default)

    def color(self, key, st):
        v = self.params.get(key)
        return hex2rgb(v) if v else st.rgb

    @property
    def particles(self):
        return self.pane.fx.particles

    # --- override what you need
    def start(self):
        pass

    def update(self, dt, st):
        pass

    def draw(self, surf, ox, oy, st):
        pass

    def busy(self):
        """True while the cursor needs animation frames (keeps eco mode awake)"""
        return False

    # --- events
    def wake(self):
        """a key was pressed"""

    def command_done(self, exit_code, secs):
        pass


class CursorStyle(_Base):
    """draws the cursor. ``character = True`` styles are sprites that stay
    visible in unfocused panes (with a thin outline) and are drawn in
    full-screen apps only when the theme sets ``alt_miner: true``"""
    character = False

    def visible(self, st):
        if self.character and st.alt and not self.pane.app.theme.get('alt_miner', False):
            return False
        return st.visible


class CursorEffect(_Base):
    """decorates the cursor. layer: 'under' (drawn before the style),
    'over' (after it) - particle effects usually draw nothing themselves"""
    layer = 'over'
    active_in_alt = False


# ============================================================================ styles
class Block(CursorStyle):
    """pulsing block, the letter under it in inverse video"""
    name = 'block'

    def pulse_rgb(self, st):
        pulse = 0.55 + 0.45 * math.sin((math.pi / 12 if st.eco else st.t) * 6.0)
        r, g, b = st.rgb
        return (int(r * pulse), int(g * pulse), int(b * pulse))

    def shape(self, st):
        return (st.x, st.y, st.cw, st.ch)

    def draw(self, surf, ox, oy, st):
        if not st.focused:
            pygame.draw.rect(surf, st.rgb, (ox + st.x, oy + st.y, st.cw, st.ch), 1)
            return
        if st.eco and int(st.t * 2) % 2:
            return
        x, y, w, h = self.shape(st)
        surf.fill(self.pulse_rgb(st), (ox + x, oy + y, w, h))
        if self.name == 'block':
            sc, r = st.screen, self.pane.renderer
            c = sc.chars[st.cy][st.cx]
            if c not in (' ', ''):
                f, bgc, sty, fl = r.resolve(sc.attrs[st.cy][st.cx])
                surf.blit(r.colored(c, sty, False, r.bg if bgc is None else bgc[:3]), (ox + st.x, oy + st.y))


class Underline(Block):
    name = 'underline'

    def shape(self, st):
        hh = max(2, st.ch // 6)
        return (st.x, st.y + st.ch - hh, st.cw, hh)


class Beam(Block):
    name = 'beam'

    def shape(self, st):
        return (st.x, st.y, max(1, st.cw // 5), st.ch)


class Outline(Block):
    """hollow box (the classic 'unfocused' look, as a style)"""
    name = 'outline'

    def draw(self, surf, ox, oy, st):
        if st.eco and int(st.t * 2) % 2 and st.focused:
            return
        pygame.draw.rect(surf, self.pulse_rgb(st) if st.focused else st.rgb, (ox + st.x, oy + st.y, st.cw, st.ch), 1)


class Character(CursorStyle):
    """an animated pixel character that *is* the cursor (see minercursor.py):
    walks along, strikes at typed letters, hops on Enter, bubbles on bell /
    command results, falls asleep when idle. ``skin`` picks the sprite."""
    name = 'miner'
    skin = 'miner'
    character = True

    def start(self):
        self.mc = None

    def _ensure(self, st):
        if self.mc is None or self.mc.cw != st.cw or self.mc.ch != st.ch:
            from .minercursor import MinerCursor
            self.mc = MinerCursor(st.cw, st.ch, skin=self.skin)

    def update(self, dt, st):
        self._ensure(st)
        mc = self.mc
        mc.update(dt, st.x, st.y)
        if st.mine is None and st.focused and 0 < st.typed < 40:
            mc.strike(-1)
            self.on_type(st)
        if st.newline and st.typed < 12 and st.focused:
            mc.jump()
        if st.bell:
            mc.say('!', 1.0)

    def on_type(self, st):
        pass

    def draw(self, surf, ox, oy, st):
        if self.mc is None:
            return
        self.mc.draw(surf, ox, oy, lamp=st.mine is not None)
        if not st.focused:
            pygame.draw.rect(surf, st.rgb, (ox + st.x, oy + st.y, st.cw, st.ch), 1)

    def busy(self):
        return bool(self.mc and self.mc.busy())

    def wake(self):
        if self.mc:
            self.mc.wake()

    def command_done(self, exit_code, secs):
        if self.mc:
            if exit_code:
                self.mc.say('?', 1.6)
            elif secs >= 3:
                self.mc.say('♥', 1.6)


class Miner(Character):
    name = 'miner'
    skin = 'miner'


class Hero(Character):
    name = 'hero'
    skin = 'hero'


class Settler(Character):
    name = 'settler'
    skin = 'settler'


class Train(Character):
    """a tiny steam locomotive that puffs smoke while you type"""
    name = 'train'
    skin = 'train'

    def on_type(self, st):
        n = 3
        mc = self.mc
        self.particles.emit(n, np.float32(mc.x + st.cw * 0.75), np.float32(mc.y + st.ch * 0.2 + st.voff * st.ch),
                            vx=np.random.uniform(-8, 8, n).astype(np.float32),
                            vy=np.random.uniform(-30, -12, n).astype(np.float32), drag=1.5,
                            life=np.random.uniform(0.5, 1.0, n).astype(np.float32), col=(230, 230, 235), pal=P.FADE)


# ============================================================================ effects
class Glow(CursorEffect):
    """soft pulsing halo under the cursor"""
    name = 'glow'
    layer = 'under'
    defaults = {'strength': 1.0}

    def start(self):
        self._cache = {}

    def draw(self, surf, ox, oy, st):
        if not st.focused or st.eco:
            return
        pulse = 0.55 + 0.45 * math.sin(st.t * 6.0)
        q = int(pulse * 8)
        rgb = self.color('color', st)
        key = (st.cw, st.ch, q, rgb)
        gs = self._cache.get(key)
        if gs is None:
            cw, ch = st.cw, st.ch
            k = q / 8 * float(self.p('strength', 1.0))
            # additive blending ignores alpha, so the falloff is baked into the colors (premultiplied)
            gs = pygame.Surface((cw * 3, ch * 2))
            gs.fill((0, 0, 0))
            for i in range(3, 0, -1):
                a = min(1.0, 0.09 * k * (4 - i))
                c = tuple(int(v * a) for v in rgb)
                pygame.draw.ellipse(gs, c, (cw * 1.5 - cw * i / 2, ch - ch * i / 3, cw * i, ch * i / 1.5))
            if len(self._cache) > 64:
                self._cache.clear()
            self._cache[key] = gs
        surf.blit(gs, (ox + st.x - st.cw, oy + st.y - st.ch // 2), special_flags=pygame.BLEND_RGB_ADD)


class Trail(CursorEffect):
    """sparkles left behind wherever the cursor moves"""
    name = 'trail'
    defaults = {'count': 6}

    def start(self):
        self.last = None

    def update(self, dt, st):
        cur = (st.cx, st.cy + st.voff)
        last = self.last or cur
        if cur != last and st.focused and not st.alt:
            n = int(self.p('count', 6))
            self.particles.emit(n, last[0] * st.cw + np.random.uniform(0, st.cw, n).astype(np.float32),
                                last[1] * st.ch + np.random.uniform(0, st.ch, n).astype(np.float32),
                                vx=np.random.uniform(-20, 20, n).astype(np.float32),
                                vy=np.random.uniform(-30, 5, n).astype(np.float32), drag=2,
                                life=np.random.uniform(0.2, 0.5, n).astype(np.float32),
                                col=self.color('color', st), pal=P.SPARKLE, add=True)
        self.last = cur


class Ripple(CursorEffect):
    """a ring expands from the cursor on Enter (and small ones while typing)"""
    name = 'ripple'
    defaults = {'typing': True}

    def start(self):
        self.rings = []

    def update(self, dt, st):
        if not st.focused:
            return
        if st.newline:
            self.rings.append([st.x + st.cw / 2, st.y + st.ch / 2, 0.0, 0.6, 3.0])
        elif st.typed and self.p('typing', True) and len(self.rings) < 6:
            self.rings.append([st.x + st.cw / 2, st.y + st.ch / 2, 0.0, 0.3, 1.2])
        for r in self.rings:
            r[2] += dt
        self.rings = [r for r in self.rings if r[2] < r[3]]

    def draw(self, surf, ox, oy, st):
        rgb = self.color('color', st)
        for x, y, age, life, size in self.rings:
            k = age / life
            rad = int(2 + k * st.ch * size)
            c = tuple(int(v * (1 - k)) for v in rgb)
            pygame.draw.circle(surf, c, (int(ox + x), int(oy + y)), rad, 1)

    def busy(self):
        return bool(self.rings)


class Sparkle(CursorEffect):
    """a few twinkling stars hover around the cursor"""
    name = 'sparkle'
    defaults = {'rate': 6}

    def update(self, dt, st):
        if st.focused and not st.alt and not st.eco and random.random() < dt * float(self.p('rate', 6)):
            self.particles.emit(1, np.float32(st.x + random.uniform(-st.cw, st.cw * 2)),
                                np.float32(st.y + st.voff * st.ch + random.uniform(-st.ch * 0.5, st.ch * 1.5)),
                                vy=np.float32(-6), life=np.float32(random.uniform(0.3, 0.7)),
                                col=self.color('color', st), pal=P.SPARKLE, add=True)


class Orbit(CursorEffect):
    """little satellites circle the cursor, faster while you type"""
    name = 'orbit'
    defaults = {'count': 3}

    def start(self):
        self.a = 0.0
        self.spin = 1.0

    def update(self, dt, st):
        self.spin += ((6.0 if st.typed else 1.5) - self.spin) * min(1, dt * 4)
        self.a += dt * self.spin

    def draw(self, surf, ox, oy, st):
        if not st.focused or st.eco:
            return
        n = int(self.p('count', 3))
        cx, cy = ox + st.x + st.cw / 2, oy + st.y + st.ch / 2
        rgb = self.color('color', st)
        for i in range(n):
            a = self.a + i * math.tau / n
            x, y = cx + math.cos(a) * st.cw * 1.1, cy + math.sin(a) * st.ch * 0.45
            surf.fill(rgb, (int(x), int(y), 1, 1))
            surf.fill(tuple(v // 3 for v in rgb), (int(x - math.cos(a + 0.3) * 2), int(y - math.sin(a + 0.3)), 1, 1))

    def busy(self):
        return True


class Smoke(CursorEffect):
    """gray puffs rise from the cursor while you type"""
    name = 'smoke'

    def update(self, dt, st):
        if st.focused and 0 < st.typed < 40:
            n = 2
            self.particles.emit(n, np.float32(st.x + st.cw * 0.5), np.float32(st.y + st.voff * st.ch),
                                vx=np.random.uniform(-6, 6, n).astype(np.float32),
                                vy=np.random.uniform(-25, -10, n).astype(np.float32), drag=1.5,
                                life=np.random.uniform(0.4, 0.9, n).astype(np.float32), col=(200, 200, 205), pal=P.FADE)


class Reticle(CursorEffect):
    """targeting brackets lock onto the cursor: they breathe, kick outwards on every key
    and fire a scan line along the row on Enter"""
    name = 'reticle'
    defaults = {'size': 1.0}

    def start(self):
        self.kick = 0.0
        self.sweep = 0.0
        self.sweep_at = (0, 0)

    def update(self, dt, st):
        if st.typed:
            self.kick = 1.0
        if st.newline and st.focused:
            self.sweep = 1.0
            self.sweep_at = (st.x + st.cw // 2, st.y + st.ch)
        self.kick = max(0.0, self.kick - dt * 5)
        self.sweep = max(0.0, self.sweep - dt * 2.5)

    def draw(self, surf, ox, oy, st):
        if not st.focused:
            return
        rgb = self.color('color', st)
        if self.sweep > 0:
            k = 1 - self.sweep
            half = int(k * st.cw * 44)
            c = tuple(int(v * self.sweep) for v in rgb)
            x, y = ox + self.sweep_at[0], oy + self.sweep_at[1]
            surf.fill(c, (x - half, y, half * 2, 1), special_flags=pygame.BLEND_RGB_ADD)
        if st.eco:
            return
        s = float(self.p('size', 1.0))
        d = int(round((2 + math.sin(st.t * 3.0) + self.kick * 4) * s))
        L = max(2, int(st.cw * 0.4 * s))
        x0, y0 = ox + st.x - d, oy + st.y - d
        x1, y1 = ox + st.x + st.cw + d - 1, oy + st.y + st.ch + d - 1
        hot = (255, 255, 255) if self.kick > 0.6 else rgb
        for x, y, dx, dy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            surf.fill(hot, (x if dx > 0 else x - L + 1, y, L, 1))
            surf.fill(hot, (x, y if dy > 0 else y - L + 1, 1, L))
        dim = tuple(v // 2 for v in rgb)
        mx, my = (x0 + x1) // 2, (y0 + y1) // 2
        surf.fill(dim, (x0 - 3, my, 2, 1))
        surf.fill(dim, (x1 + 2, my, 2, 1))
        surf.fill(dim, (mx, y0 - 3, 1, 2))
        surf.fill(dim, (mx, y1 + 2, 1, 2))

    def busy(self):
        return self.kick > 0 or self.sweep > 0


class ChiselCursor(CursorStyle):
    """a tiny chisel and mallet drawn entirely inside the cursor cell (like the block cursor);
    the mallet taps the chisel whenever you type"""
    name = 'chisel'
    character = True

    def start(self):
        self.strike = 0.0

    def update(self, dt, st):
        if st.typed and st.focused:
            self.strike = 0.1
            n = 2
            self.particles.emit(n, np.float32(st.x + st.cw * 0.3), np.float32(st.y + st.voff * st.ch + st.ch - 1),
                                vx=np.random.uniform(-15, 15, n).astype(np.float32), vy=np.random.uniform(-20, 0, n).astype(np.float32),
                                grav=300, life=np.random.uniform(0.3, 0.7, n).astype(np.float32), col=(70, 66, 56), pal=P.FADE,
                                add=True)
        self.strike = max(0.0, self.strike - dt)

    def draw(self, surf, ox, oy, st):
        cw, ch = st.cw, st.ch
        x0, y0 = ox + st.x, oy + st.y
        # the cell itself: a slightly recessed block so you always see where the cursor is
        cell = pygame.Rect(x0, y0, cw, ch)
        surf.fill((214, 206, 192), cell, special_flags=pygame.BLEND_RGB_MULT)
        if not st.focused:
            pygame.draw.rect(surf, st.rgb, cell, 1)
            return
        lw = max(1, round(cw / 6))
        tip = (x0 + cw * 0.28, y0 + ch * 0.9)
        ferrule = (x0 + cw * 0.52, y0 + ch * 0.58)
        top = (x0 + cw * 0.70, y0 + ch * 0.36)
        pygame.draw.line(surf, (104, 108, 120), tip, ferrule, lw)              # steel blade
        pygame.draw.line(surf, (60, 62, 70), ferrule, (ferrule[0] + 1, ferrule[1] - 1), lw + 1)
        pygame.draw.line(surf, (146, 96, 54), ferrule, top, lw + 1)            # wooden handle
        surf.fill((236, 238, 246), (int(tip[0]), int(tip[1]), 1, 1))          # the edge
        drop = ch * 0.1 if self.strike > 0 else 0                              # mallet taps the handle
        hx, hy = x0 + cw * 0.5, y0 + ch * 0.06 + drop
        surf.fill((112, 72, 42), (int(hx), int(hy), max(2, int(cw * 0.42)), max(2, int(ch * 0.12))))
        pygame.draw.line(surf, (150, 104, 62), (hx + cw * 0.38, hy + ch * 0.1), (x0 + cw - 1, hy + ch * 0.26), 1)

    def busy(self):
        return self.strike > 0


CURSORS = {c.name: c for c in (Block, Underline, Beam, Outline, Miner, Hero, Settler, Train, ChiselCursor)}
CURSOR_EFFECTS = {c.name: c for c in (Glow, Trail, Ripple, Sparkle, Orbit, Smoke, Reticle)}


def make_style(name, pane, params=None):
    cls = CURSORS.get(name) or Block
    return cls(pane, (params or {}).get(cls.name))


def make_effects(names, pane, params=None):
    out = []
    for n in names or []:
        cls = CURSOR_EFFECTS.get(n)
        if cls:
            out.append(cls(pane, (params or {}).get(n)))
    return out
