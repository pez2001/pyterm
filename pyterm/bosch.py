"""Bosch: an animated pixel garden of earthly delights - and the hell next door.

My own reading of the strange world of Hieronymus Bosch (not a copy of any single painting), built from his
motifs and alive all the time. Paradise on the left blends into a burning city on the right:

  paradise   a pink fountain tower with crescent finials, spires, ponds with bobbing glass spheres, an owl in a
             hollow tree, giant strawberries / cherries / raspberries / blueberries that little naked people
             climb into and out of, a pool with riders circling it on goats, birds and fish, bathers, a flying
             fish with a knight, a flock of birds
  hell       a burning city under smoke and sparks, the Tree-Man (egg torso, tree legs, standing in two boats,
             a hat full of tiny figures and a bagpipe), a bird-headed Prince of Hell on his pot throne who gulps
             down sinners, a pair of ears that walks around with a knife, a giant harp with a man strung in it,
             a lute, bird-headed imps with spears, lava cracks

It reacts to the terminal: typed letters release little souls that float up, a command that succeeds makes the
fountain surge and the riders gallop, a failed command makes the city flare up (the Prince screams, the screen
reddens, the picture shakes), the bell wakes the owl, output energy speeds everything up.

bg_params: {bosch: {speed: 1.0, fire: 1.0, souls: true, riders: 12}}
"""
from __future__ import annotations

import math
import random

import numpy as np
import pygame

from . import signals
from .backgrounds import Background
from .roman import _noise
from .scenes import glow

ADD = pygame.BLEND_RGB_ADD

C = dict(
    sky_l_top=(150, 196, 192), sky_l_bot=(238, 228, 170),
    sky_r_top=(24, 10, 16), sky_r_bot=(216, 88, 26),
    grass=(112, 152, 80), burnt=(64, 36, 30),
    pink=(228, 152, 164), pink_hi=(248, 200, 198), pink_lo=(176, 98, 122),
    blue=(110, 156, 204), blue_hi=(178, 214, 232), blue_lo=(64, 98, 150),
    skin=(240, 200, 168), skin_lo=(200, 152, 128),
    red=(198, 46, 42), orange=(240, 136, 40), yellow=(255, 214, 90),
    green=(70, 124, 64), green_hi=(140, 184, 92),
    brown=(104, 68, 48), brown_hi=(150, 106, 70), ink=(30, 18, 22),
    grey=(112, 122, 142), grey_hi=(170, 180, 196), egg=(236, 222, 190),
)


def _mix(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def _dark(c, f=0.7):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f))


def _sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def _rect(s, col, x, y, w, h):
    s.fill(col, (int(x), int(y), int(w), int(h)))


def _crescent(s, x, y, r, col):
    bg = s.get_at((max(0, min(s.get_width() - 1, x)), max(0, y - r)))[:3]
    pygame.draw.circle(s, col, (x, y), r)
    pygame.draw.circle(s, bg, (x + max(1, r // 2), y - max(1, r // 3)), max(1, r - 1))


def _poly(s, col, pts):
    pygame.draw.polygon(s, col, [(int(x), int(y)) for x, y in pts])


class BoschBase(Background):
    """the painted, static part of the world"""
    name = 'bosch'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        self.s = max(1, int(round(h / 200)))                 # one painted pixel = s screen pixels
        self.lw, self.lh = max(16, -(-w // self.s)), max(16, -(-h // self.s))
        self.low = pygame.Surface((self.lw, self.lh))
        self.fx = pygame.Surface((self.lw, self.lh), pygame.SRCALPHA)
        rng = random.Random(1516)
        self.ponds, self.windows, self.flames, self.cracks = [], [], [], []
        self.hy = int(self.lh * 0.5)
        self.static = self._paint(rng)
        self._populate(rng)
        self.seq = signals.letter_seq
        self.last_cmd = signals.cmd

    # ------------------------------------------------------------------ painting
    def _paint(self, rng):
        w, h, hy = self.lw, self.lh, self.hy
        st = pygame.Surface((w, h))
        xs = np.linspace(0, 1, w, dtype=np.float32)
        blend = _sstep(0.42, 0.82, xs)
        b3 = blend[:, None, None]
        f = lambda k: np.array(C[k], np.float32)[None, None, :]
        v = (np.linspace(0, 1, hy, dtype=np.float32)[None, :, None]) ** 1.5
        sky = (f('sky_l_top') * (1 - b3) + f('sky_r_top') * b3) * (1 - v) + (f('sky_l_bot') * (1 - b3) + f('sky_r_bot') * b3) * v
        n = _noise(w, h - hy, 7, 5)[..., None]
        ground = (f('grass') * (1 - b3) + f('burnt') * b3) * (0.62 + 0.8 * n)
        img = np.concatenate([sky, ground], axis=1)
        pygame.surfarray.blit_array(st, np.clip(img, 0, 255).astype(np.uint8))
        for _ in range(w * (h - hy) // 14):                  # tufts and speckles
            x, y = rng.randrange(w), rng.randrange(hy, h)
            u = x / w
            c = st.get_at((x, y))[:3]
            st.set_at((x, y), _mix(c, (200, 220, 120) if u < 0.5 else (120, 50, 30), 0.35) if rng.random() < 0.5 else _dark(c, 0.8))
        # hills: pale blue-green in paradise, burnt red-black in hell
        cl = ((150, 190, 190), (124, 170, 150), (96, 148, 96))
        cr = ((96, 40, 40), (62, 28, 30), (38, 20, 22))
        for layer, (amp, off) in enumerate(((16, 12), (11, 6), (6, 1))):
            for x in range(w):
                y = hy - off - amp * (0.55 + 0.3 * math.sin(x * 0.03 * (layer + 1) + layer * 2) + 0.15 * math.sin(x * 0.011 + layer))
                pygame.draw.line(st, _mix(cl[layer], cr[layer], float(blend[x])), (x, int(y)), (x, hy))
        # ponds with pale shores
        self._pond(st, int(w * 0.30), int(h * 0.585), int(w * 0.12), int(h * 0.03))
        self._pond(st, int(w * 0.07), int(h * 0.90), int(w * 0.06), int(h * 0.04))
        # towers, spires, the hollow tree
        self._spires(st, int(w * 0.30), int(h * 0.57), 6, rng)
        self._tower(st, int(w * 0.15), int(h * 0.62), int(h * 0.46))
        self._hollow_tree(st, int(w * 0.035), int(h * 0.62))
        # hell: frozen lake, lava cracks, the burning city
        pygame.draw.ellipse(st, (26, 34, 54), (int(w * 0.57), int(h * 0.84), int(w * 0.20), int(h * 0.10)))
        pygame.draw.ellipse(st, (60, 76, 104), (int(w * 0.585), int(h * 0.855), int(w * 0.17), int(h * 0.05)))
        self._cracks(st, rng)
        self._city(st, rng)
        return st

    def _pond(self, s, cx, cy, rx, ry):
        pygame.draw.ellipse(s, C['pink_hi'], (cx - rx - 2, cy - ry - 1, 2 * rx + 4, 2 * ry + 3))
        pygame.draw.ellipse(s, (118, 182, 196), (cx - rx, cy - ry, 2 * rx, 2 * ry))
        pygame.draw.ellipse(s, (166, 218, 220), (cx - rx + 3, cy - ry + 1, max(2, 2 * rx - 8), max(1, ry)))
        self.ponds.append((cx, cy, rx, ry))

    def _tower(self, s, cx, by, H):
        pk, hi, lo = C['pink'], C['pink_hi'], C['pink_lo']
        pygame.draw.ellipse(s, lo, (cx - int(.20 * H), by - int(.07 * H), int(.40 * H), int(.10 * H)))
        pygame.draw.ellipse(s, pk, (cx - int(.17 * H), by - int(.09 * H), int(.34 * H), int(.08 * H)))
        sw = max(3, int(.07 * H))
        _rect(s, pk, cx - sw // 2, by - int(.64 * H), sw, int(.58 * H))
        _rect(s, hi, cx - sw // 2, by - int(.64 * H), 1, int(.58 * H))
        _rect(s, lo, cx + sw // 2, by - int(.64 * H), 1, int(.58 * H))
        for fy, fr in ((.16, .22), (.34, .17), (.50, .12)):          # stacked basins, water spilling over
            y, rx = by - int(fy * H), int(fr * H)
            ht = max(3, int(.045 * H))
            pygame.draw.ellipse(s, C['blue_lo'], (cx - rx, y, rx * 2, ht + 2))
            pygame.draw.ellipse(s, C['pink'], (cx - rx, y - 1, rx * 2, ht))
            pygame.draw.ellipse(s, C['blue_hi'], (cx - rx + 2, y, rx * 2 - 4, max(2, ht - 2)))
        for side in (-1, 1):                                          # side globes with dark windows
            gx, gy, gr = cx + side * int(.22 * H), by - int(.46 * H), int(.07 * H)
            _rect(s, pk, gx - 1, gy, 3, int(.2 * H))
            pygame.draw.circle(s, lo, (gx, gy), gr)
            pygame.draw.circle(s, pk, (gx - 1, gy - 1), max(1, gr - 1))
            pygame.draw.ellipse(s, C['ink'], (gx - gr // 3, gy - 1, max(2, gr // 2), max(3, gr)))
        gy, gr = by - int(.74 * H), int(.15 * H)                      # the great hollow globe
        pygame.draw.circle(s, lo, (cx, gy), gr)
        pygame.draw.circle(s, pk, (cx - 1, gy - 1), gr - 1)
        pygame.draw.circle(s, hi, (cx - gr // 3, gy - gr // 3), max(1, gr // 4))
        pygame.draw.ellipse(s, C['ink'], (cx - gr // 3 + 1, gy - 1, gr // 2 + 1, gr // 2 + 3))
        pygame.draw.ellipse(s, C['blue'], (cx - gr // 3 + 2, gy + 1, max(1, gr // 2 - 1), max(1, gr // 2)))
        _poly(s, pk, [(cx - gr // 2, gy - gr + 3), (cx + gr // 2, gy - gr + 3), (cx, by - H)])
        _poly(s, lo, [(cx + 1, gy - gr + 3), (cx + gr // 2, gy - gr + 3), (cx, by - H)])
        _crescent(s, cx, by - H - 3, 3, C['yellow'])
        lx = cx + sw // 2 + 3                                         # a long ladder up the stem, people on it
        y0, y1 = by - int(.10 * H), by - int(.62 * H)
        _rect(s, C['brown'], lx, y1, 1, y0 - y1)
        _rect(s, C['brown'], lx + 4, y1, 1, y0 - y1)
        for ry in range(y1, y0, 3):
            _rect(s, C['brown_hi'], lx, ry, 5, 1)
        self.ladder = (lx + 2, y0, y1)

    def _spires(self, s, cx, by, n, rng):
        for i in range(n):
            x = cx + (i - n // 2) * 9 + rng.randint(-2, 2)
            hgt, wd = rng.randint(14, 34), rng.randint(4, 7)
            col = (C['pink'], C['blue'], C['pink_hi'])[i % 3]
            _rect(s, col, x, by - hgt, wd, hgt)
            _rect(s, _dark(col, 0.78), x + wd - 1, by - hgt, 1, hgt)
            _poly(s, _dark(col, 0.82), [(x - 1, by - hgt), (x + wd, by - hgt), (x + wd // 2, by - hgt - wd - 3)])
            for wy in range(by - hgt + 3, by - 3, 6):
                s.set_at((x + wd // 2, wy), C['ink'])
            if i % 2 == 0:
                _crescent(s, x + wd // 2, by - hgt - wd - 5, 2, C['yellow'])
        pygame.draw.ellipse(s, C['blue_lo'], (cx - 14, by - 10, 28, 16))                # blue pavilion dome
        pygame.draw.ellipse(s, C['blue'], (cx - 13, by - 11, 26, 14))
        pygame.draw.ellipse(s, C['blue_hi'], (cx - 9, by - 10, 8, 4))

    def _hollow_tree(self, s, tx, by):
        _poly(s, C['brown'], [(tx - 9, by), (tx - 6, by - 40), (tx - 3, by - 62), (tx + 5, by - 62), (tx + 8, by - 40), (tx + 12, by)])
        _poly(s, C['brown_hi'], [(tx - 9, by), (tx - 6, by - 40), (tx - 3, by - 62), (tx - 1, by - 62), (tx - 3, by - 40), (tx - 5, by)])
        for dx, dy, r in ((-8, -64, 9), (6, -68, 10), (-2, -74, 8), (14, -60, 7), (-16, -56, 6)):
            pygame.draw.circle(s, C['green'], (tx + dx, by + dy), r)
            pygame.draw.circle(s, C['green_hi'], (tx + dx - 2, by + dy - 2), max(2, r // 2))
        pygame.draw.ellipse(s, C['ink'], (tx - 5, by - 38, 8, 10))
        self.owl = (tx - 1, by - 33)

    def _cracks(self, s, rng):
        w, h = self.lw, self.lh
        for _ in range(7):
            x, y = rng.uniform(w * 0.52, w * 0.98), rng.uniform(h * 0.58, h * 0.98)
            a = rng.uniform(0, math.tau)
            pts = [(x, y)]
            for _ in range(rng.randint(5, 11)):
                a += rng.uniform(-0.8, 0.8)
                x += math.cos(a) * rng.uniform(3, 7)
                y += math.sin(a) * rng.uniform(1.5, 3.5)
                pts.append((x, y))
            pygame.draw.lines(s, (120, 34, 16), False, pts, 2)
            self.cracks.append(pts)

    def _city(self, s, rng):
        w, h, hy = self.lw, self.lh, self.hy
        x0 = int(w * 0.52)
        x = x0
        while x < w:
            bw = rng.randint(6, 13)
            u = (x - x0) / max(1, w - x0)
            bh = int(rng.uniform(12, 28) + 24 * math.sin(u * math.pi) ** 1.2)
            by = hy + 1
            body = (30, 16, 22)
            _rect(s, body, x, by - bh, bw, bh)
            _rect(s, (84, 38, 28), x, by - bh, 1, bh)
            kind = rng.choice(('point', 'dome', 'flat', 'tower'))
            if kind == 'point':
                _poly(s, body, [(x - 1, by - bh), (x + bw, by - bh), (x + bw // 2, by - bh - bw - 2)])
                top = by - bh - bw - 2
            elif kind == 'dome':
                pygame.draw.ellipse(s, body, (x - 1, by - bh - 5, bw + 2, 10))
                top = by - bh - 5
            elif kind == 'tower':
                _rect(s, body, x + bw // 2 - 1, by - bh - 9, 3, 9)
                _poly(s, body, [(x + bw // 2 - 2, by - bh - 9), (x + bw // 2 + 3, by - bh - 9), (x + bw // 2, by - bh - 15)])
                top = by - bh - 15
            else:
                for bx in range(x, x + bw, 3):
                    _rect(s, body, bx, by - bh - 2, 2, 2)
                top = by - bh - 2
            for wy in range(by - bh + 3, by - 3, 4):
                for wx in range(x + 2, x + bw - 1, 3):
                    if rng.random() < 0.38:
                        self.windows.append((wx, wy, rng.random() * 9))
            if rng.random() < 0.55:
                self.flames.append([x + bw // 2, top + 2, rng.randint(6, 13), rng.random() * 9])
            x += bw + rng.randint(-1, 2)
        for fx in range(int(w * 0.55), w, 17):                  # fires on the ground between the ruins
            self.flames.append([fx + rng.randint(-4, 4), hy + rng.randint(4, 14), rng.randint(5, 9), rng.random() * 9])


def _fruit_sprites():
    """giant fruits drawn once: name -> (surface, (hole_x, hole_y) where little people go in)"""
    out = {}
    s = pygame.Surface((15, 17), pygame.SRCALPHA)                     # strawberry
    pygame.draw.polygon(s, C['red'], [(1, 4), (13, 4), (11, 11), (7, 16), (3, 11)])
    pygame.draw.ellipse(s, C['red'], (1, 2, 13, 8))
    for x, y in ((4, 5), (8, 5), (11, 6), (3, 8), (6, 8), (9, 8), (5, 11), (8, 11), (7, 13)):
        s.set_at((x, y), C['yellow'])
    pygame.draw.ellipse(s, (240, 110, 100), (3, 3, 4, 2))
    for dx in (-4, -2, 0, 2, 4):
        pygame.draw.line(s, C['green'], (7, 2), (7 + dx, 0))
    pygame.draw.ellipse(s, C['ink'], (6, 11, 3, 4))
    out['straw'] = (s, (7, 15))
    s = pygame.Surface((14, 14), pygame.SRCALPHA)                     # cherries
    for cx in (4, 10):
        pygame.draw.circle(s, C['red'], (cx, 9), 4)
        pygame.draw.circle(s, (250, 120, 110), (cx - 1, 8), 1)
        pygame.draw.line(s, C['green'], (cx, 5), (7, 0))
    out['cherry'] = (s, (4, 12))
    s = pygame.Surface((14, 14), pygame.SRCALPHA)                     # raspberry
    for x, y in ((4, 4), (8, 4), (3, 7), (7, 7), (11, 7), (5, 10), (9, 10), (7, 12), (6, 2)):
        pygame.draw.circle(s, (214, 56, 96), (x, y + 1), 2)
        s.set_at((x - 1, y), (250, 150, 170))
    pygame.draw.ellipse(s, C['green'], (4, 0, 6, 3))
    out['rasp'] = (s, (7, 13))
    s = pygame.Surface((12, 12), pygame.SRCALPHA)                     # blueberry
    pygame.draw.circle(s, C['blue_lo'], (6, 7), 5)
    pygame.draw.circle(s, C['blue'], (5, 6), 3)
    pygame.draw.circle(s, C['blue_hi'], (4, 5), 1)
    pygame.draw.circle(s, C['ink'], (6, 2), 1)
    out['blueb'] = (s, (6, 11))
    return out


class Bosch(BoschBase):
    name = 'bosch'
    opaque = True

    # ------------------------------------------------------------------ cast
    def _populate(self, rng):
        w, h = self.lw, self.lh
        self.fruit = _fruit_sprites()
        self.fruit_at = [('straw', int(w * 0.31), int(h * 0.80)), ('rasp', int(w * 0.09), int(h * 0.78)),
                         ('blueb', int(w * 0.25), int(h * 0.92)), ('cherry', int(w * 0.40), int(h * 0.93)),
                         ('straw', int(w * 0.02), int(h * 0.96)), ('blueb', int(w * 0.50), int(h * 0.97))]
        self.fruit_at = [(k, x, min(y, h - self.fruit[k][0].get_height() - 2)) for k, x, y in self.fruit_at]
        self.holes = [(x + self.fruit[k][1][0], y + self.fruit[k][1][1]) for k, x, y in self.fruit_at]
        self.climbers = [[0.0, 1], [0.5, -1]]
        self.fishwalk = [{'x': w * 0.20, 'y': h * 0.90, 'tx': w * 0.2, 'ty': h * 0.9, 'wait': 1.0, 'dir': 1, 'ph': 0.0},
                         {'x': w * 0.34, 'y': h * 0.70, 'tx': w * 0.3, 'ty': h * 0.7, 'wait': 3.0, 'dir': -1, 'ph': 2.0}]
        self.mussel = (int(w * 0.555), int(h * 0.72))
        self.pool = (int(w * 0.46), int(h * 0.80), int(w * 0.11), int(h * 0.055))
        nr = int(self.p('riders', 12))
        self.riders = [{'a': i * math.tau / max(1, nr), 'k': i % 4, 'col': [(150, 100, 70), (236, 230, 220), (110, 150, 200),
                        (230, 140, 150), (120, 160, 90), (230, 200, 120)][i % 6], 'sp': rng.uniform(0.55, 0.8)} for i in range(nr)]
        self.bathers = [[self.pool[0] + rng.randint(-14, 14), self.pool[1] + rng.randint(-2, 3), rng.random() * 9] for _ in range(5)]
        self.spheres = [[w * 0.26, h * 0.72, 9, 0.0], [w * 0.40, h * 0.62, 7, 2.0], [w * 0.30, h * 0.50, 12, 4.0]]
        self.walkers = []
        for i in range(16):
            self.walkers.append({'x': rng.uniform(w * 0.03, w * 0.55), 'y': rng.uniform(h * 0.66, h * 0.96), 'tx': 0, 'ty': 0,
                                 'wait': rng.uniform(0, 3), 'hid': 0.0, 'hole': False, 'ph': rng.random() * 9, 'dir': 1,
                                 'sp': rng.uniform(7, 13), 'hat': rng.choice((None, None, C['red'], C['blue'], C['yellow'])),
                                 'carry': rng.choice((None, None, None, C['red'], C['blue_lo'], (214, 56, 96))),
                                 'col': rng.choice((C['skin'], C['skin'], C['pink_hi'], (230, 180, 150)))})
            self._goto(self.walkers[-1], rng)
        self.imps = [{'x': rng.uniform(w * 0.55, w * 0.97), 'y': rng.uniform(h * 0.74, h * 0.95), 'tx': 0, 'ty': 0,
                      'wait': rng.uniform(0, 2), 'ph': rng.random() * 9, 'sp': rng.uniform(5, 9), 'dir': -1} for _ in range(5)]
        for im in self.imps:
            self._goto_imp(im, rng)
        self.souls, self.spray, self.smoke, self.sparks, self.birds = [], [], [], [], []
        self.fish = None
        self.fish_in = rng.uniform(6, 12)
        self.flock_in = rng.uniform(3, 8)
        self.boost = 0.0            # failed command: hell flares up
        self.surge = 0.0            # command succeeded: the fountain surges, riders gallop
        self.owl_wide = 0.0
        self.rng = rng

    def _goto(self, p, rng):
        if rng.random() < 0.3 and self.holes:
            p['tx'], p['ty'] = rng.choice(self.holes)
            p['hole'] = True
        else:
            p['tx'], p['ty'] = rng.uniform(self.lw * 0.03, self.lw * 0.56), rng.uniform(self.lh * 0.66, self.lh * 0.97)
            p['hole'] = False

    def _goto_imp(self, p, rng):
        p['tx'], p['ty'] = rng.uniform(self.lw * 0.55, self.lw * 0.97), rng.uniform(self.lh * 0.74, self.lh * 0.96)

    # ------------------------------------------------------------------ life
    def update(self, dt, energy):
        dt *= float(self.p('speed', 1.0))
        super().update(dt, energy)
        rng, w, h = self.rng, self.lw, self.lh
        boost_k = 1 + energy * 0.8
        for p in self.walkers:
            if p['hid'] > 0:
                p['hid'] -= dt
                continue
            if p['wait'] > 0:
                p['wait'] -= dt
                continue
            dx, dy = p['tx'] - p['x'], p['ty'] - p['y']
            d = math.hypot(dx, dy)
            if d < 1.6:
                if p['hole']:
                    p['hid'] = rng.uniform(3, 7)
                p['wait'] = rng.uniform(0.4, 3)
                self._goto(p, rng)
            else:
                p['x'] += dx / d * p['sp'] * dt * boost_k
                p['y'] += dy / d * p['sp'] * dt * boost_k * 0.7
                p['dir'] = 1 if dx > 0 else -1
        for im in self.imps:
            if im['wait'] > 0:
                im['wait'] -= dt
                continue
            dx, dy = im['tx'] - im['x'], im['ty'] - im['y']
            d = math.hypot(dx, dy)
            if d < 1.6:
                im['wait'] = rng.uniform(0.5, 3)
                self._goto_imp(im, rng)
            else:
                im['x'] += dx / d * im['sp'] * dt * (1 + self.boost)
                im['y'] += dy / d * im['sp'] * dt * (1 + self.boost) * 0.7
                im['dir'] = 1 if dx > 0 else -1
        for fw in self.fishwalk:
            if fw['wait'] > 0:
                fw['wait'] -= dt
                continue
            dx, dy = fw['tx'] - fw['x'], fw['ty'] - fw['y']
            d = math.hypot(dx, dy)
            if d < 1.5:
                fw['wait'] = rng.uniform(1, 4)
                fw['tx'], fw['ty'] = rng.uniform(w * 0.04, w * 0.55), rng.uniform(h * 0.68, h * 0.95)
            else:
                fw['x'] += dx / d * 5 * dt
                fw['y'] += dy / d * 3.5 * dt
                fw['dir'] = 1 if dx > 0 else -1
        for c in self.climbers:
            c[0] = (c[0] + dt * 0.05 * c[1] * (1 + self.surge)) 
            if c[0] > 1 or c[0] < 0:
                c[1] = -c[1]
                c[0] = max(0.0, min(1.0, c[0]))
        for r in self.riders:
            r['a'] += dt * r['sp'] * (1 + self.surge * 2.2 + energy * 0.6)
        for sp in self.spheres:
            sp[3] += dt
        new, self.seq = signals.take_letters(self.seq)
        if self.p('souls', True):
            for _, ch, x, y, typed in new[-4:]:
                if typed and len(self.souls) < 60:
                    self.souls.append([x / self.s, y / self.s, rng.uniform(-3, 3), rng.uniform(-14, -8), 3.2 + rng.random(), rng.random() * 9])
        if signals.cmd is not self.last_cmd and signals.cmd:
            self.last_cmd = signals.cmd
            if signals.cmd[0]:
                self.boost = 1.0
                signals.shake = max(signals.shake, 0.3)
            else:
                self.surge = 1.0
        if signals.bell and signals.recent(signals.bell, 0.3):
            self.owl_wide = 1.5
        self.boost = max(0.0, self.boost - dt * 0.35)
        self.surge = max(0.0, self.surge - dt * 0.4)
        self.owl_wide = max(0.0, self.owl_wide - dt)
        # fountain: constant trickle, surges on success
        px, py = self.tower_top()
        if rng.random() < dt * (4 + 40 * self.surge + 5 * energy):
            self.spray.append([px, py, rng.uniform(-9, 9) * (1 + self.surge), rng.uniform(-26, -14) * (1 + self.surge * 0.6), 1.6])
        # fire: smoke and sparks
        fire = float(self.p('fire', 1.0)) * (1 + self.boost * 1.5 + energy * 0.5)
        for fl in self.flames:
            if rng.random() < dt * 0.5 * fire:
                self.smoke.append([fl[0], fl[1] - fl[2], rng.uniform(1, 6), rng.uniform(-9, -5), 4.5, rng.uniform(1.5, 3)])
            if rng.random() < dt * 0.6 * fire:
                self.sparks.append([fl[0], fl[1] - fl[2], rng.uniform(-8, 8), rng.uniform(-22, -8), 1.2 + rng.random()])
        for lst in (self.souls, self.spray, self.smoke, self.sparks):
            for q in lst:
                q[0] += q[2] * dt
                q[1] += q[3] * dt
                q[4] -= dt
            lst[:] = [q for q in lst if q[4] > 0][-260:]
        for q in self.spray:
            q[3] += 38 * dt
        for q in self.souls:
            q[2] = math.sin(self.t * 2 + q[5]) * 5
        # a flying fish with a knight crosses the sky now and then, a flock of birds too
        self.fish_in -= dt
        if self.fish is None and self.fish_in <= 0:
            d = rng.choice((1, -1))
            self.fish = {'x': -20 if d > 0 else w + 20, 'y': h * rng.uniform(0.12, 0.3), 'd': d, 'ph': rng.random() * 9}
        if self.fish:
            self.fish['x'] += self.fish['d'] * 13 * dt
            if self.fish['x'] < -30 or self.fish['x'] > w + 30:
                self.fish = None
                self.fish_in = rng.uniform(18, 35)
        self.flock_in -= dt
        if self.flock_in <= 0:
            self.flock_in = rng.uniform(14, 30)
            y0, d = h * rng.uniform(0.1, 0.35), rng.choice((1, -1))
            for i in range(7):
                self.birds.append({'x': (-6 if d > 0 else w + 6) - d * abs(i - 3) * 5, 'y': y0 + abs(i - 3) * 3, 'd': d, 'ph': i})
        for b in self.birds:
            b['x'] += b['d'] * 24 * dt
        self.birds = [b for b in self.birds if -30 < b['x'] < w + 30]

    def tower_top(self):
        return int(self.lw * 0.15), int(self.lh * 0.62) - int(self.lh * 0.46 * 0.76)

    # ------------------------------------------------------------------ drawing helpers
    def _fig(self, x, y, col=None, moving=True, ph=0.0, hat=None, carry=None, d=1):
        s, t = self.low, self.t
        col = col or C['skin']
        x, y = int(x), int(y)
        st = int(t * 6 + ph) % 2 if moving else 0
        _rect(s, col, x, y - 6, 2, 2)
        _rect(s, _dark(col, 0.86), x, y - 4, 2, 3)
        if hat:
            _rect(s, hat, x - 1, y - 7, 3, 1)
        _rect(s, C['skin_lo'], x - st, y - 1, 1, 1)
        _rect(s, C['skin_lo'], x + 1 + st, y - 1, 1, 1)
        if carry:
            _rect(s, carry, x + (2 if d > 0 else -2), y - 5, 2, 2)

    def _rider(self, x, y, kind, col, fl, ph):
        s, t = self.low, self.t
        x, y = int(x), int(y)
        st = int(t * 8 + ph * 3) % 2
        lift = 2 if kind == 2 else 0
        _rect(s, col, x - 3, y - 4 - lift, 6, 3)
        _rect(s, _mix(col, (255, 255, 255), 0.3), x - 3, y - 4 - lift, 6, 1)
        hx = x + (3 if fl > 0 else -4)
        if kind == 2:                                              # fish: tail instead of legs
            _rect(s, col, x - fl * 4, y - 5, 1, 4)
            _rect(s, C['blue_lo'], x - 1, y - 1, 3, 1)
            _rect(s, col, hx, y - 5, 1, 3)
        else:
            _rect(s, _dark(col, 0.7), x - 3 + st, y - 1, 1, 2)
            _rect(s, _dark(col, 0.7), x + 2 - st, y - 1, 1, 2)
            if kind == 1:                                          # bird: long neck and beak
                _rect(s, col, hx, y - 8, 1, 5)
                _rect(s, C['orange'], hx + (1 if fl > 0 else -2), y - 8, 2, 1)
            else:
                _rect(s, col, hx, y - 6, 2, 3)
                if kind == 3:                                      # antlers
                    _rect(s, C['brown'], hx, y - 8, 1, 2)
                    _rect(s, C['brown'], hx + 1, y - 9, 1, 1)
        _rect(s, C['skin'], x - 1, y - 8 - lift, 2, 2)
        _rect(s, C['red'] if kind % 2 else C['blue_lo'], x - 1, y - 6 - lift, 2, 2)
        _rect(s, C['ink'], x - 1, y - 9 - lift, 2, 1)

    def _fire(self, x, y, sz, seed, k=1.0):
        """a flame: licking tongues with rounded, overlapping bases and an ember glow where it sits"""
        s, t = self.low, self.t
        w0 = max(3, int(sz * 0.55))
        pygame.draw.ellipse(s, (120, 30, 14), (x - w0 - 1, y - 2, 2 * w0 + 2, 6))             # glowing embers under the fire
        pygame.draw.ellipse(s, C['red'], (x - w0, y - 3, 2 * w0, 5))
        for i, dx in enumerate((-2, 0, 2)):
            hh = max(3, int(sz * (0.7 + 0.3 * math.sin(t * 9 + seed * 3 + i * 2)) * k))
            w2 = max(2, int(sz * 0.32))
            sw = int(math.sin(t * 6 + seed + i) * 1.6)
            cx = x + dx
            col = C['red'] if i != 1 else C['orange']
            _poly(s, col, [(cx - w2, y), (cx - w2 + 1, y - hh // 3), (cx + sw, y - hh), (cx + w2 - 1, y - hh // 3), (cx + w2, y)])
            pygame.draw.ellipse(s, col, (cx - w2, y - 3, 2 * w2, 5))
            h2 = max(2, int(hh * 0.62))
            col2 = C['orange'] if i != 1 else C['yellow']
            _poly(s, col2, [(cx - w2 // 2, y), (cx + sw, y - h2), (cx + w2 // 2, y)])
            pygame.draw.ellipse(s, col2, (cx - max(1, w2 // 2), y - 2, max(2, w2), 4))
        pygame.draw.ellipse(s, C['yellow'], (x - 2, y - 2, 4, 3))                              # white-hot heart

    def _treeman(self, tx, fy):
        s, t = self.low, self.t
        sway = int(round(math.sin(t * 0.7)))
        for dx in (-9, 9):                                         # two boats on the frozen lake
            bob = int(round(math.sin(t * 1.3 + dx)))
            x = tx + dx
            _poly(s, C['brown'], [(x - 8, fy - 3 + bob), (x + 8, fy - 3 + bob), (x + 5, fy + bob), (x - 5, fy + bob)])
            _rect(s, C['brown_hi'], x - 8, fy - 3 + bob, 16, 1)
        for dx in (-6, 6):                                         # tree-trunk legs with knots and a twig
            bob = int(round(math.sin(t * 1.3 + dx * 1.5)))
            x = tx + dx
            _rect(s, C['brown_hi'], x - 1, fy - 28, 3, 26 + bob)
            _rect(s, C['brown'], x + 1, fy - 28, 1, 26 + bob)
            s.set_at((x, fy - 16), C['ink'])
            s.set_at((x, fy - 9), C['ink'])
            _rect(s, C['brown'], x + (2 if dx > 0 else -3), fy - 22, 2, 1)
        ex, ey = tx + sway, fy - 43                               # the egg torso, hollow in front
        pygame.draw.ellipse(s, _dark(C['egg'], 0.74), (ex - 13, ey - 17, 26, 34))
        pygame.draw.ellipse(s, C['egg'], (ex - 13, ey - 17, 23, 33))
        pygame.draw.ellipse(s, (252, 244, 220), (ex - 10, ey - 14, 6, 11))
        _poly(s, C['ink'], [(ex - 3, ey - 6), (ex + 3, ey - 10), (ex + 6, ey - 5), (ex + 9, ey + 1), (ex + 4, ey + 8), (ex - 4, ey + 5),
                            (ex - 6, ey - 1)])                    # the breach, jagged
        fl = 0.7 + 0.3 * math.sin(t * 11) * math.sin(t * 4.3)
        pygame.draw.ellipse(s, _mix(C['ink'], C['orange'], 0.45 * fl), (ex - 3, ey - 5, 10, 10))
        for fx, c in ((ex - 1, C['skin']), (ex + 2, C['skin_lo']), (ex + 5, C['pink'])):     # tiny people drinking at a table
            _rect(s, c, fx, ey - 1 + int(math.sin(t * 2 + fx) > 0.8), 2, 3)
        _rect(s, C['brown'], ex - 2, ey + 3, 9, 1)
        _rect(s, C['yellow'], ex + 2, ey - 5, 1, 3)               # candle
        s.set_at((ex + 2, ey - 6), C['yellow'] if int(t * 7) % 2 else C['orange'])
        nx, ny = tx - 10 + sway, fy - 70                          # bent neck, sorrowful face turned back
        _rect(s, C['brown_hi'], nx + 4, ny + 4, 3, 10)
        _rect(s, C['brown_hi'], nx + 6, ny + 12, 4, 3)
        pygame.draw.circle(s, C['skin_lo'], (nx + 3, ny), 5)
        pygame.draw.circle(s, C['skin'], (nx + 2, ny - 1), 4)
        _rect(s, C['skin_lo'], nx - 3, ny + 1, 2, 2)
        _rect(s, C['ink'], nx, ny - 2 + (1 if int(t * 0.5) % 11 == 0 else 0), 1, 1)
        _rect(s, C['ink'], nx - 1, ny + 3, 4, 1)
        hy2 = ny - 8                                               # the hat: a broad disc with a dome, a bagpipe, tiny people
        pygame.draw.ellipse(s, C['brown'], (nx - 17 + sway, hy2, 40, 6))
        pygame.draw.ellipse(s, C['brown_hi'], (nx - 17 + sway, hy2 - 1, 40, 4))
        pygame.draw.ellipse(s, C['pink_lo'], (nx - 4 + sway, hy2 - 8, 13, 11))
        pygame.draw.ellipse(s, C['pink'], (nx - 4 + sway, hy2 - 9, 12, 8))
        pygame.draw.circle(s, C['grey'], (nx + 17 + sway, hy2 - 3), 3)                    # bagpipe
        for k in range(3):
            _rect(s, C['ink'], nx + 16 + k * 2 + sway, hy2 - 9 + k, 1, 6 - k)
        for k, x in enumerate((nx - 13, nx - 8, nx + 11)):
            bob = int(math.sin(t * 3 + k * 2) > 0.7)
            _rect(s, C['skin'] if k % 2 else C['pink_hi'], x + sway, hy2 - 4 - bob, 2, 4)

    def _prince(self, px, fy):
        s, t = self.low, self.t
        open_ = (math.sin(t * 0.9) > 0.65) or self.boost > 0.2
        _poly(s, C['brown'], [(px - 9, fy - 12), (px + 9, fy - 12), (px + 6, fy), (px - 6, fy)])          # pot throne
        _rect(s, C['brown_hi'], px - 9, fy - 12, 18, 2)
        _rect(s, (86, 98, 128), px - 5, fy - 30, 10, 19)                                                  # body
        _rect(s, C['grey'], px - 5, fy - 30, 2, 19)
        _rect(s, C['grey'], px - 8, fy - 26, 3, 9)                                                         # arm
        pygame.draw.circle(s, C['grey_hi'], (px, fy - 35), 5)                                              # bird head
        _rect(s, C['yellow'], px - 3, fy - 37, 2, 2)
        s.set_at((px - 3, fy - 37), C['ink'])
        bx = px - 5
        gap = 3 if open_ else 0
        _poly(s, C['orange'], [(bx, fy - 36), (bx - 9, fy - 33 - gap), (bx, fy - 33 - gap)])
        _poly(s, C['yellow'], [(bx, fy - 32 + gap), (bx - 8, fy - 32 + gap), (bx, fy - 34 + gap)])
        if open_:                                                   # a sinner's legs kicking out of the beak
            k = int(t * 8) % 2
            _rect(s, C['skin'], bx - 6 - k, fy - 34, 1, 3)
            _rect(s, C['skin'], bx - 8 + k, fy - 33, 1, 3)
        pygame.draw.ellipse(s, C['ink'], (px - 7, fy - 44, 14, 9))                                         # pot helmet
        _rect(s, C['ink'], px - 9, fy - 38, 18, 2)
        _rect(s, C['red'], px, fy - 48, 1, 5)

    def _ears(self, ex, fy):
        s, t = self.low, self.t
        st = int(t * 5) % 2
        for dx in (-9, 1):
            pygame.draw.ellipse(s, C['skin_lo'], (ex + dx, fy - 21, 9, 17))
            pygame.draw.ellipse(s, C['skin'], (ex + dx + 1, fy - 20, 7, 15))
            pygame.draw.ellipse(s, C['pink_lo'], (ex + dx + 2, fy - 16, 4, 8))
        _poly(s, C['grey_hi'], [(ex - 1, fy - 25), (ex + 1, fy - 25), (ex + 1, fy - 7), (ex, fy - 5), (ex - 1, fy - 7)])      # the knife
        _rect(s, C['ink'], ex - 1, fy - 8, 2, 1)
        _rect(s, C['brown'], ex - 1, fy - 5, 2, 2)
        _rect(s, C['skin_lo'], ex - 5 + st, fy - 4, 2, 4)
        _rect(s, C['skin_lo'], ex + 3 - st, fy - 4, 2, 4)

    def _harp(self, hx, fy):
        s, t = self.low, self.t
        _rect(s, C['brown'], hx + 9, fy - 36, 3, 36)                                  # pillar
        _rect(s, C['brown_hi'], hx + 9, fy - 36, 1, 36)
        _poly(s, C['brown'], [(hx - 12, fy - 24), (hx + 12, fy - 38), (hx + 12, fy - 34), (hx - 12, fy - 20)])   # curved neck
        _poly(s, C['brown'], [(hx - 12, fy - 22), (hx - 12, fy - 19), (hx - 2, fy), (hx + 12, fy), (hx + 12, fy - 3), (hx, fy - 3)])
        for i in range(7):                                                            # strings, trembling
            wob = int(round(math.sin(t * 14 + i) * (0.4 + self.boost * 2 + self.surge)))
            xi = hx - 10 + i * 3
            ytop = fy - 23 - i * 2 + (1 if i else 0)
            _rect(s, C['grey_hi'], xi + wob, ytop, 1, max(2, fy - 6 - ytop + i // 2))
        k = int(t * 3 + 0.5) % 2                                                      # a man strung in it
        _rect(s, C['skin'], hx - 3 + k, fy - 22, 2, 2)
        _rect(s, C['skin_lo'], hx - 4 + k, fy - 20, 4, 5)
        _rect(s, C['skin_lo'], hx - 4, fy - 15 + k, 1, 4)
        _rect(s, C['skin_lo'], hx, fy - 15 + (1 - k), 1, 4)

    def _mussel(self):
        s, t = self.low, self.t
        mx, my = self.mussel
        gap = int(2 + 5 * (0.5 + 0.5 * math.sin(t * 0.45)) ** 2)
        pygame.draw.ellipse(s, C['pink_lo'], (mx - 10, my - 1, 20, 9))                 # lower shell
        pygame.draw.ellipse(s, C['pink'], (mx - 10, my - 2, 20, 7))
        pygame.draw.ellipse(s, C['ink'], (mx - 8, my - 1, 16, 4))
        if gap > 3:                                                                   # a couple inside
            _rect(s, C['skin'], mx - 4, my - 2, 2, 2)
            _rect(s, C['skin_lo'], mx - 5, my, 4, 2)
            _rect(s, C['pink_hi'], mx + 1, my - 2, 2, 2)
            _rect(s, C['skin_lo'], mx, my, 4, 2)
        pygame.draw.ellipse(s, C['pink_lo'], (mx - 10, my - 4 - gap, 20, 9))           # upper shell, opening and closing
        pygame.draw.ellipse(s, C['pink_hi'], (mx - 10, my - 5 - gap, 20, 7))
        for rx in (-6, -2, 2, 6):
            _rect(s, C['pink'], mx + rx, my - 5 - gap, 1, 5)

    def _fishwalker(self, f):
        s, t = self.low, self.t
        x, y, d = int(f['x']), int(f['y']), f['dir']
        st = int(t * 5 + f['ph']) % 2
        pygame.draw.ellipse(s, C['blue_lo'], (x - 7, y - 11, 14, 8))
        pygame.draw.ellipse(s, C['blue'], (x - 7, y - 12, 14, 6))
        for fx in (-3, 0, 3):
            _rect(s, C['blue_hi'], x + fx, y - 12, 1, 6)
        _poly(s, C['blue'], [(x - d * 7, y - 8), (x - d * 12, y - 12), (x - d * 12, y - 5)])
        _rect(s, C['ink'], x + d * 4 - (1 if d < 0 else 0), y - 10, 1, 1)
        _rect(s, C['skin_lo'], x - 3 + st, y - 4, 1, 4)                               # two thin human legs
        _rect(s, C['skin_lo'], x + 2 - st, y - 4, 1, 4)
        _rect(s, C['ink'], x - 3 + st - 1, y - 1, 2, 1)
        _rect(s, C['ink'], x + 2 - st - 1, y - 1, 2, 1)
        _rect(s, C['red'], x - 2, y - 15, 5, 3)                                       # a funnel hat
        _rect(s, C['red'], x, y - 17, 1, 2)

    def _climbers(self):
        lx, y0, y1 = self.ladder
        for c in self.climbers:
            y = y0 + (y1 - y0) * c[0]
            _rect(self.low, C['skin'], lx - 1, y - 5, 2, 2)
            _rect(self.low, C['pink_lo'], lx - 1, y - 3, 2, 2)
            k = int(self.t * 3 + c[0] * 20) % 2
            _rect(self.low, C['skin_lo'], lx - 2 + k, y - 1, 1, 1)
            _rect(self.low, C['skin_lo'], lx + 1 - k, y - 1, 1, 1)

    def _lute(self, lx, fy):
        s = self.low
        pygame.draw.ellipse(s, C['brown'], (lx - 7, fy - 15, 14, 15))
        pygame.draw.ellipse(s, C['brown_hi'], (lx - 6, fy - 14, 10, 12))
        pygame.draw.circle(s, C['ink'], (lx, fy - 8), 2)
        _poly(s, C['brown'], [(lx - 2, fy - 14), (lx + 1, fy - 14), (lx + 8, fy - 30), (lx + 5, fy - 31)])
        _rect(s, C['red'], lx + 4, fy - 33, 4, 3)

    def _owl(self):
        s, t = self.low, self.t
        ox, oy = self.owl
        _rect(s, C['brown_hi'], ox - 3, oy - 2, 7, 8)
        _rect(s, C['brown'], ox - 3, oy - 3, 1, 2)
        _rect(s, C['brown'], ox + 3, oy - 3, 1, 2)
        blink = (t * 0.33) % 7 < 0.14 and not self.owl_wide
        look = int(round(math.sin(t * 0.5) * 1.2))
        for ex in (ox - 3, ox + 1):
            _rect(s, C['yellow'] if not blink else C['brown'], ex, oy - 1, 3, 3)
            if self.owl_wide:
                _rect(s, (255, 255, 200), ex - 1, oy - 2, 5, 5)
            if not blink:
                _rect(s, C['ink'], ex + 1 + (look if not self.owl_wide else 0), oy, 1, 1)
        _rect(s, C['orange'], ox - 1, oy + 2, 2, 2)

    def _fishfly(self, f):
        s, t = self.low, self.t
        x, y = int(f['x']), int(f['y'] + math.sin(t * 1.5 + f['ph']) * 4)
        d = f['d']
        pygame.draw.ellipse(s, C['blue_lo'], (x - 9, y - 4, 18, 8))
        pygame.draw.ellipse(s, C['pink_hi'], (x - 9, y - 4, 18, 6))
        for sx in (-3, 0, 3):
            _rect(s, C['blue'], x + sx, y - 4, 1, 7)
        wag = int(math.sin(t * 8) * 2)
        _poly(s, C['pink'], [(x - d * 9, y), (x - d * 14, y - 4 + wag), (x - d * 14, y + 4 + wag)])
        _rect(s, C['ink'], x + d * 6 - (1 if d < 0 else 0), y - 2, 1, 1)
        _rect(s, C['skin'], x - 1, y - 8, 2, 2)                                                           # the knight
        _rect(s, C['red'], x - 1, y - 6, 2, 3)
        _rect(s, C['ink'], x - 1, y - 9, 2, 1)
        pygame.draw.line(s, C['grey_hi'], (x + d, y - 6), (x + d * 12, y - 12))

    def _bird(self, b):
        s, t = self.low, self.t
        x, y = int(b['x']), int(b['y'] + math.sin(t * 2 + b['ph']) * 2)
        up = int(t * 6 + b['ph']) % 2
        c = (60, 56, 80)
        _rect(s, c, x, y, 2, 1)
        _rect(s, c, x - 2, y - up, 2, 1)
        _rect(s, c, x + 2, y - up, 2, 1)

    # ------------------------------------------------------------------ the picture
    def draw(self, surf, first):
        s, t, w, h, hy = self.low, self.t, self.lw, self.lh, self.hy
        s.blit(self.static, (0, 0))
        energy = max(0.0, min(2.0, signals.energy)) if hasattr(signals, 'energy') else 0.0
        fire = float(self.p('fire', 1.0)) * (1 + self.boost * 1.2 + energy * 0.3)
        # pond ripples
        for cx, cy, rx, ry in self.ponds:
            for i in range(4):
                u = (t * 0.2 + i * 0.25) % 1.0
                lx = int(cx - rx * 0.8 + u * rx * 1.6)
                ly = cy - ry // 2 + i * max(1, ry // 3)
                _rect(s, (206, 240, 236), lx, ly, 3, 1)
        # glowing windows of the burning city, lava cracks
        for wx, wy, ph in self.windows:
            fl = math.sin(t * (6 + ph) + ph * 3) * math.sin(t * 2.3 + ph)
            if fl > -0.5 - self.boost * 0.4:
                s.fill((255, 170, 50) if fl > 0.2 else (190, 70, 30), (wx, wy, 2, 2))
        for pts in self.cracks:
            for i, (x, y) in enumerate(pts):
                if math.sin(t * 2 + i + pts[0][0]) > -0.3:
                    s.set_at((int(x), int(y)), (255, 150, 40))
        # fruits sit behind the walkers that stand above them, in front of those below: sort everything by foot y
        items = []
        for k, x, y in self.fruit_at:
            items.append((y + self.fruit[k][0].get_height(), 'fruit', (k, x, y)))
        for p in self.walkers:
            if p['hid'] <= 0:
                items.append((p['y'], 'walker', p))
        for im in self.imps:
            items.append((im['y'], 'imp', im))
        for r in self.riders:
            px, py, rx, ry = self.pool
            ax, ay = px + (rx + 7) * math.cos(r['a']), py + (ry + 5) * math.sin(r['a'])
            items.append((ay, 'rider', (ax, ay, r)))
        items.sort(key=lambda it: it[0])
        # the pool they ride around
        px, py, rx, ry = self.pool
        pygame.draw.ellipse(s, C['pink_lo'], (px - rx - 3, py - ry - 1, 2 * rx + 6, 2 * ry + 4))
        pygame.draw.ellipse(s, C['pink_hi'], (px - rx - 2, py - ry - 2, 2 * rx + 4, 2 * ry + 2))
        pygame.draw.ellipse(s, (126, 186, 204), (px - rx, py - ry, 2 * rx, 2 * ry))
        pygame.draw.ellipse(s, (176, 222, 226), (px - rx + 4, py - ry + 2, 2 * rx - 12, ry))
        for i in range(5):
            u = (t * 0.25 + i * 0.2) % 1.0
            _rect(s, (220, 244, 240), px - rx + 6 + u * (2 * rx - 14), py - ry + 3 + i * 2, 4, 1)
        for bx, by, ph in self.bathers:
            bob = int(round(math.sin(t * 1.6 + ph)))
            _rect(s, C['skin'], bx, by - 2 + bob, 2, 2)
            if math.sin(t * 0.9 + ph) > 0.8:
                _rect(s, C['skin'], bx - 1, by - 5 + bob, 1, 3)
                _rect(s, C['skin'], bx + 2, by - 5 + bob, 1, 3)
        for _, kind, data in items:
            if kind == 'fruit':
                k, x, y = data
                s.blit(self.fruit[k][0], (x, y))
            elif kind == 'walker':
                self._fig(data['x'], data['y'], data['col'], True, data['ph'], data['hat'], data['carry'], data['dir'])
            elif kind == 'imp':
                x, y, im = int(data['x']), int(data['y']), data
                st = int(t * 5 + im['ph']) % 2
                _rect(s, (60, 50, 70), x, y - 6, 3, 5)
                _rect(s, C['grey'], x, y - 8, 3, 2)
                _rect(s, C['orange'], x + (3 if im['dir'] > 0 else -2), y - 8, 2, 1)
                _rect(s, (60, 50, 70), x + st, y - 1, 1, 2)
                _rect(s, (60, 50, 70), x + 2 - st, y - 1, 1, 2)
                pygame.draw.line(s, C['grey_hi'], (x + (4 if im['dir'] > 0 else -1), y - 2), (x + (5 if im['dir'] > 0 else -2), y - 13))
            else:
                ax, ay, r = data
                fl = 1 if -math.sin(r['a']) > 0 else -1
                self._rider(ax, ay, r['k'], r['col'], fl, r['a'])
        self._mussel()
        self._climbers()
        for fw in self.fishwalk:
            self._fishwalker(fw)
        # the far-off figures of hell
        self._owl()
        self._treeman(int(w * 0.67), int(h * 0.88))
        self._harp(int(w * 0.80), int(h * 0.98))
        self._lute(int(w * 0.745), int(h * 0.985))
        self._prince(int(w * 0.89), int(h * 0.90))
        ex = int(w * 0.57 + math.sin(t * 0.13) * w * 0.05)
        self._ears(ex, int(h * 0.965))
        for fl in self.flames:
            self._fire(int(fl[0]), int(fl[1]), fl[2], fl[3], fire)
        if self.fish:
            self._fishfly(self.fish)
        for b in self.birds:
            self._bird(b)
        # glows: the horizon of hell, the candle in the egg
        flick = 0.85 + 0.15 * math.sin(t * 7.1) * math.sin(t * 2.9)
        glow(s, int(w * 0.80), hy, int(w * 0.30), tuple(int(v * flick * (1 + self.boost)) for v in (70, 26, 6)))
        if self.boost > 0:
            _b = self.boost
            s.fill((int(80 * _b), int(10 * _b), 0), special_flags=ADD)
        # translucent things on the fx layer
        fx = self.fx
        fx.fill((0, 0, 0, 0))
        for q in self.smoke:
            a = int(110 * min(1, q[4] / 2))
            r = max(1, int(q[5] + (4.5 - q[4]) * 0.8))
            pygame.draw.circle(fx, (40, 30, 36, a), (int(q[0]), int(q[1])), r)
        for q in self.spray:
            fx.set_at((int(q[0]), int(q[1])), (230, 246, 255, 230))
            fx.set_at((int(q[0]) + 1, int(q[1])), (180, 220, 250, 160))
        for q in self.sparks:
            fx.set_at((int(q[0]), int(q[1])), (255, 200, 80, int(255 * min(1, q[4]))))
        for sx, sy, r, ph in self.spheres:                                                                 # glass spheres with people inside
            yy = sy + math.sin(ph * 0.8) * 3
            r = int(r)
            pygame.draw.circle(fx, (150, 200, 232, 80), (int(sx), int(yy)), r)
            pygame.draw.circle(fx, (230, 246, 255, 180), (int(sx), int(yy)), r, 1)
            pygame.draw.circle(fx, (255, 255, 255, 210), (int(sx - r * 0.4), int(yy - r * 0.4)), max(1, r // 4))
            for k in range(2 if r < 10 else 3):
                gx = sx - r * 0.4 + k * r * 0.45 + math.sin(ph * 1.3 + k) * 1.5
                gy = yy + r * 0.2 + math.sin(ph * 2 + k * 2) * 1.5
                fx.fill((240, 200, 168, 255), (int(gx), int(gy) - 4, 2, 2))
                fx.fill((226, 150, 160, 255), (int(gx), int(gy) - 2, 2, 3))
        for q in self.souls:
            a = int(255 * min(1, q[4] / 1.2))
            x, y = int(q[0]), int(q[1])
            fx.fill((255, 240, 220, a), (x, y, 2, 2))
            fx.fill((240, 214, 200, a), (x, y + 2, 2, 3))
            fx.fill((255, 240, 160, a), (x - 1, y - 2, 4, 1))
        s.blit(fx, (0, 0))
        big = pygame.transform.scale(s, (self.w, self.h))
        surf.blit(big, (0, 0))
