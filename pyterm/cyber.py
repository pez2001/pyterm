"""zeroday - a hacker's deck as a living background.

  zeroday   a holographic dot-matrix globe turns in cyberspace while hex rain falls behind it.
            * every letter you type flies off as a packet to your home node and is routed
              on to a city somewhere in the world (great-circle arcs with glowing heads)
            * program output drives the rain, the throughput scope and the ambient traffic
            * a command that succeeds roots the node you were attacking: ACCESS GRANTED
            * a command that fails trips the ICE: red counter-traces race back to your home
              node, the picture tears, the TRACE meter climbs - at 100 % the connection is
              burned and every rooted node is lost
            * Enter sweeps a scan ring over the globe, the bell pings like a sonar,
              left / right spin the globe
            HUD: clock (UTC), node id, live hex tap of what you type, throughput scope,
            typing speed, packets, rooted nodes, trace meter, uptime

  bg_params:
    zeroday: {accent: '#00ffd0', accent2: '#ff2e88', alert: '#ff2846', ok: '#3cff78',
              home: [64.1, -21.9], rain: 1.0, hud: true, globe: true, spin: 1.0,
              globe_x: 0.68, globe_y: 0.47, globe_size: 0.36, callsign: 'ZERODAY//OS'}

Everything reacts through pyterm.signals; nothing here reads the terminal contents beyond the
letters the terminal already publishes for all scenes.
"""
from __future__ import annotations

import collections
import math
import random
import time

import numpy as np
import pygame

from . import signals
from .backgrounds import Background
from .scenes import glow
from .themes import hex2rgb
from .weather import _F

ADD = pygame.BLEND_RGB_ADD
HEX = '0123456789ABCDEF'

# glyphs the weather widget's 3x5 font does not have
_EXTRA = {
    '[': "##.#..#..#..##.", ']': ".##..#..#..#.##", '>': "#...#...#.#.#..", '<': "..#.#.#...#...#",
    '=': "...###...###...", '_': "............###", '|': ".#..#..#..#..#.", '#': "#.#####.#####.#",
    '*': "...#.#.#.#.#...", '!': ".#..#..#.....#.", '?': "##...#.#.....#.", ',': "..........#.#..",
    "'": ".#..#..........",
}


class TinyFont:
    """the 3x5 pixel font, cached as surfaces (whole lines too) - drawn additively"""

    def __init__(self):
        self.glyphs = {}
        self.lines = {}

    def glyph(self, ch, col):
        key = (ch, col)
        s = self.glyphs.get(key)
        if s is None:
            s = pygame.Surface((3, 5))
            s.fill((0, 0, 0))
            for i, b in enumerate(_EXTRA.get(ch) or _F.get(ch) or _F[' ']):
                if b == '#':
                    s.set_at((i % 3, i // 3), col)
            if len(self.glyphs) > 2000:
                self.glyphs.clear()
            self.glyphs[key] = s
        return s

    def line(self, text, col, scale=1):
        key = (text, col, scale)
        s = self.lines.get(key)
        if s is None:
            text = text.upper()
            s = pygame.Surface((max(1, len(text) * 4 - 1), 5))
            s.fill((0, 0, 0))
            for i, ch in enumerate(text):
                if ch != ' ':
                    s.blit(self.glyph(ch, col), (i * 4, 0))
            if scale > 1:
                s = pygame.transform.scale(s, (s.get_width() * scale, s.get_height() * scale))
            if len(self.lines) > 500:
                self.lines.clear()
            self.lines[key] = s
        return s

    def text(self, surf, x, y, text, col, scale=1):
        surf.blit(self.line(text, col, scale), (int(x), int(y)), special_flags=ADD)
        return x + len(text) * 4 * scale

    def width(self, text, scale=1):
        return (len(text) * 4 - 1) * scale


# ============================================================================ the world
# coarse coastlines as (lon, lat) polygons - enough for a recognisable dot globe
_LAND = [
    # north america
    [(-168, 66), (-156, 71), (-128, 70), (-110, 68), (-95, 72), (-82, 73), (-78, 62), (-64, 60), (-56, 52), (-66, 45),
     (-70, 42), (-76, 35), (-81, 31), (-80, 25), (-83, 29), (-90, 29), (-97, 26), (-97, 20), (-90, 21), (-87, 16),
     (-83, 10), (-78, 8), (-85, 11), (-92, 15), (-105, 20), (-110, 24), (-115, 31), (-122, 37), (-124, 47),
     (-135, 58), (-150, 60), (-165, 55), (-162, 60)],
    # greenland
    [(-55, 60), (-44, 60), (-22, 70), (-20, 80), (-40, 83), (-60, 81), (-70, 77), (-55, 70)],
    # south america
    [(-78, 8), (-72, 12), (-62, 10), (-52, 5), (-50, 0), (-36, -6), (-39, -15), (-48, -25), (-58, -35), (-65, -42),
     (-68, -53), (-74, -52), (-73, -38), (-70, -20), (-76, -14), (-81, -5), (-80, 1)],
    # africa
    [(-17, 15), (-16, 22), (-10, 30), (-5, 35), (10, 37), (20, 32), (32, 31), (35, 24), (43, 12), (51, 12), (42, -1),
     (40, -15), (35, -24), (28, -33), (19, -35), (13, -22), (12, -6), (9, 3), (-7, 4), (-13, 8)],
    # eurasia
    [(-9, 37), (-9, 43), (-2, 44), (-4, 48), (3, 51), (8, 54), (10, 58), (5, 59), (6, 62), (14, 68), (25, 71), (40, 67),
     (60, 69), (70, 73), (90, 76), (110, 74), (130, 72), (160, 70), (180, 68), (178, 64), (163, 60), (156, 51),
     (142, 54), (135, 45), (128, 38), (122, 31), (121, 25), (110, 21), (108, 12), (104, 9), (100, 13), (98, 8),
     (103, 2), (98, 16), (92, 22), (80, 13), (77, 8), (72, 20), (66, 25), (57, 26), (52, 16), (43, 13), (35, 28),
     (36, 36), (27, 37), (23, 38), (19, 42), (13, 45), (18, 40), (16, 38), (12, 44), (8, 44), (3, 43), (0, 39), (-5, 36)],
    [(-5, 50), (1, 51), (0, 54), (-2, 58), (-6, 57), (-4, 54)],                                   # great britain
    [(-10, 52), (-6, 52), (-6, 55), (-9, 54)],                                                    # ireland
    [(-24, 65), (-14, 66), (-14, 64), (-22, 63.5)],                                               # iceland
    [(130, 32), (136, 34), (141, 38), (142, 44), (140, 41), (135, 35)],                           # japan
    [(114, -22), (122, -17), (130, -12), (136, -12), (142, -11), (146, -19), (153, -27), (150, -37), (143, -38),
     (135, -34), (124, -33), (115, -34)],                                                         # australia
    [(172, -41), (175, -37), (178, -38), (174, -41), (168, -46), (167, -45)],                     # new zealand
    [(44, -16), (49, -13), (50, -17), (47, -25), (44, -24)],                                      # madagascar
    [(95, 5), (104, -5), (106, -6), (100, 2)],                                                    # sumatra
    [(109, 1), (117, 6), (118, 1), (115, -4), (110, -3)],                                         # borneo
    [(131, -1), (141, -3), (148, -6), (147, -10), (138, -8), (132, -4)],                          # new guinea
    [(106, -6), (114, -7), (114, -8.5), (106, -7.5)],                                             # java
    [(120, 14), (122, 18), (124, 13), (126, 7), (122, 7)],                                        # philippines
    [(80, 9), (82, 7), (80, 6)],                                                                  # sri lanka
]

CITIES = [('SFO', 37.8, -122.4), ('LAX', 34.0, -118.2), ('SEA', 47.6, -122.3), ('MEX', 19.4, -99.1),
          ('NYC', 40.7, -74.0), ('YYZ', 43.7, -79.4), ('MIA', 25.8, -80.2), ('BOG', 4.7, -74.1),
          ('GRU', -23.5, -46.6), ('BUE', -34.6, -58.4), ('LON', 51.5, -0.1), ('PAR', 48.9, 2.3),
          ('AMS', 52.4, 4.9), ('BER', 52.5, 13.4), ('STO', 59.3, 18.1), ('MOW', 55.8, 37.6),
          ('IST', 41.0, 29.0), ('CAI', 30.0, 31.2), ('LOS', 6.5, 3.4), ('NBO', -1.3, 36.8),
          ('JNB', -26.2, 28.0), ('DXB', 25.2, 55.3), ('BOM', 19.1, 72.9), ('DEL', 28.6, 77.2),
          ('SIN', 1.3, 103.8), ('HKG', 22.3, 114.2), ('PEK', 39.9, 116.4), ('SEL', 37.6, 127.0),
          ('TYO', 35.7, 139.7), ('SYD', -33.9, 151.2), ('AKL', -36.8, 174.8), ('HNL', 21.3, -157.9)]


def _vec(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return np.array([math.cos(la) * math.sin(lo), math.sin(la), math.cos(la) * math.cos(lo)], np.float32)


def _in_poly(lon, lat, poly):
    inside = np.zeros(lon.shape, bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if y1 == y2:
            continue
        inside ^= ((y1 > lat) != (y2 > lat)) & (lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1)
    return inside


_WORLD = {}


def world(step=2.0):
    """(land points Nx3, graticule points Mx3) on the unit sphere - built once"""
    w = _WORLD.get(step)
    if w is not None:
        return w
    lats, lons = [], []
    for lat in np.arange(-90 + step / 2, 90, step):
        n = max(1, int(360 * math.cos(math.radians(lat)) / step))
        lo = np.linspace(-180, 180, n, endpoint=False) + (step / 2 if int(lat / step) % 2 else 0)
        lons.append(lo)
        lats.append(np.full(n, lat))
    lon = np.concatenate(lons)
    lat = np.concatenate(lats)
    land = np.zeros(lon.shape, bool)
    for poly in _LAND:
        land |= _in_poly(lon, lat, poly)
    land |= lat < -72 + 4 * np.sin(np.radians(lon * 3))          # antarctica
    lon, lat = np.radians(lon[land]), np.radians(lat[land])
    pts = np.stack([np.cos(lat) * np.sin(lon), np.sin(lat), np.cos(lat) * np.cos(lon)], 1).astype(np.float32)
    g = []
    a = np.radians(np.arange(0, 360, 3.0))
    for la in range(-60, 61, 30):                                # parallels
        r = math.radians(la)
        g.append(np.stack([np.cos(r) * np.sin(a), np.full(a.shape, math.sin(r)), np.cos(r) * np.cos(a)], 1))
    b = np.radians(np.arange(-84, 85, 3.0))
    for lo in range(0, 360, 30):                                 # meridians
        r = math.radians(lo)
        g.append(np.stack([np.cos(b) * math.sin(r), np.sin(b), np.cos(b) * math.cos(r)], 1))
    _WORLD[step] = w = (pts, np.concatenate(g).astype(np.float32))
    return w


def _arc(a, b, n=28):
    """great-circle arc a -> b, lifted off the surface in the middle"""
    om = math.acos(float(np.clip(np.dot(a, b), -1, 1)))
    t = np.linspace(0, 1, n, dtype=np.float32)
    if om < 1e-3:
        pts = np.repeat(a[None, :], n, 0)
    else:
        pts = (np.sin((1 - t) * om)[:, None] * a + np.sin(t * om)[:, None] * b) / math.sin(om)
    lift = 0.10 + 0.30 * om / math.pi
    return (pts * (1 + lift * np.sin(np.pi * t))[:, None]).astype(np.float32)


def _mul(col, k):
    return (min(255, int(col[0] * k)), min(255, int(col[1] * k)), min(255, int(col[2] * k)))


def _mix(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


# ============================================================================ the scene
class ZeroDay(Background):
    name = 'zeroday'
    opaque = True

    def _col(self, key, default):
        v = self.p(key, None)
        try:
            return tuple(hex2rgb(v)) if isinstance(v, str) else (tuple(int(c) for c in v[:3]) if v else default)
        except Exception:
            return default

    def resize(self, w, h):
        super().resize(w, h)
        first = not hasattr(self, 'arcs')
        self.accent = self._col('accent', (0, 255, 208))
        self.accent2 = self._col('accent2', (255, 46, 136))
        self.alert_col = self._col('alert', (255, 40, 70))
        self.ok_col = self._col('ok', (60, 255, 120))
        self.show_hud = bool(self.p('hud', True))
        self.show_globe = bool(self.p('globe', True))
        self.rain_k = float(self.p('rain', 1.0) or 0)
        self.spin = float(self.p('spin', 1.0))
        self.callsign = str(self.p('callsign', 'ZERODAY//OS'))[:24]
        self.compact = w < 360 or h < 200
        self.tf = getattr(self, 'tf', None) or TinyFont()
        # globe
        self.R = max(12, int(min(h * float(self.p('globe_size', 0.36)), w * 0.3)))
        self.gx, self.gy = int(w * float(self.p('globe_x', 0.68))), int(h * float(self.p('globe_y', 0.47)))
        land, grat = world()
        self.pts = np.concatenate([land, grat])
        self.base = np.concatenate([np.ones(len(land), np.float32), np.full(len(grat), 0.22, np.float32)])
        self.nland = len(land)
        D = 2 * self.R + 3
        self.gsurf = pygame.Surface((D, D), 0, 32)
        self._lut_col = None
        self.cities = [(n, _vec(la, lo), la, lo) for n, la, lo in CITIES]
        home = self.p('home', None)
        try:
            self.home = _vec(float(home[0]), float(home[1]))
        except Exception:
            self.home = _vec(64.1, -21.9)
        # rain
        self._build_rain()
        self._build_static()
        if first:
            self.rot = 0.6
            self.rot_v = 0.0
            self.arcs = []           # dicts: pts, t, speed, col, city, linger
            self.packets = []        # [x0, y0, k, char]
            self.rings = []          # [vec, age, col]
            self.pings = []          # [age]
            self.seq = signals.letter_seq
            self.last_cmd = signals.cmd
            self.last_bell = signals.bell
            self.last_enter = signals.enter
            self.rooted = set()
            self.target = random.randrange(len(self.cities))
            self.trace = 0.0
            self.alert = 0.0
            self.glitch = 0.0
            self.grant = 0.0
            self.banner = None       # [text, color, seconds]
            self.scan = None         # scan ring position 1 .. -1
            self.pkts = 0
            self.born = time.time()
            self.node = '%04X' % random.randrange(0x1000, 0xFFFF)
            self.hexlines = collections.deque(('%04X  %s' % (random.randrange(65536), self._hexrow()) for _ in range(6)), maxlen=6)
            self.hex_t = 0.0
            self.tap = collections.deque(maxlen=8)
            self.hist = collections.deque([0.0] * 48, maxlen=48)
            self.hist_t = 0.0
            self.ping_ms = 42
            self.M = np.eye(3, dtype=np.float32)

    @staticmethod
    def _hexrow():
        return ' '.join('%02X' % random.randrange(256) for _ in range(8))

    # ------------------------------------------------------------ static parts
    def _build_rain(self):
        w, h = self.w, self.h
        rng = random.Random(1337)
        self.strips = []
        dim = _mul(self.accent, 0.42)
        for _ in range(8):
            n = rng.randint(7, 20)
            s = pygame.Surface((3, n * 6))
            s.fill((0, 0, 0))
            for i in range(n):
                k = (i + 1) / n
                col = (200, 255, 240) if i == n - 1 else _mul(dim, k * k)
                s.blit(self.tf.glyph(rng.choice(HEX), col), (0, i * 6))
            self.strips.append(s)
        cols = int(w / 7 * min(1.5, self.rain_k)) if self.rain_k > 0 else 0
        self.drops = [[rng.randrange(0, max(1, w // 4)) * 4, rng.uniform(-h, h), rng.uniform(25, 80), rng.randrange(8)]
                      for _ in range(cols)]

    def _build_static(self):
        w, h = self.w, self.h
        # backdrop: deep blue-black gradient
        col = pygame.Surface((1, 32))
        for y in range(32):
            k = y / 31
            col.set_at((0, y), (int(3 - 2 * k), int(7 - 4 * k), int(16 - 9 * k)))
        back = pygame.transform.smoothscale(col, (w, h))
        st = pygame.Surface((w, h))
        st.fill((0, 0, 0))
        st.set_colorkey((0, 0, 0))
        ac = self.accent
        lo = _mul(ac, 0.28)
        if self.show_globe:
            R, gx, gy = self.R, self.gx, self.gy
            for i in range(R, 0, -2):                             # dark glass ball, brighter towards the limb
                f = 0.022 + 0.075 * (i / R) ** 4
                pygame.draw.circle(st, (max(1, int(ac[0] * f)), max(2, int(ac[1] * f)), max(3, int(ac[2] * f))), (gx, gy), i)
            pygame.draw.circle(st, _mul(ac, 0.3), (gx, gy), R + 1, 1)
            for i in range(72):                                   # outer tick ring
                a = i * math.tau / 72
                r0 = R + 6
                r1 = R + (10 if i % 6 == 0 else 8)
                pygame.draw.line(st, _mul(ac, 0.35 if i % 6 == 0 else 0.18),
                                 (gx + math.cos(a) * r0, gy + math.sin(a) * r0), (gx + math.cos(a) * r1, gy + math.sin(a) * r1))
            for i in range(0, 360, 3):                            # dotted orbit of the relay satellite
                a = math.radians(i)
                st.set_at((int(gx + math.cos(a) * R * 1.32), int(gy + math.sin(a) * R * 0.34)), _mul(self.accent2, 0.3)) \
                    if 0 <= gx + math.cos(a) * R * 1.32 < w and 0 <= gy + math.sin(a) * R * 0.34 < h else None
        if self.show_hud:
            k = max(6, min(w, h) // 22)
            for (x, y, dx, dy) in ((2, 2, 1, 1), (w - 3, 2, -1, 1), (2, h - 3, 1, -1), (w - 3, h - 3, -1, -1)):
                pygame.draw.line(st, ac, (x, y), (x + dx * k, y))
                pygame.draw.line(st, ac, (x, y), (x, y + dy * k))
            # top and bottom rails with notches
            pygame.draw.line(st, lo, (k + 6, 11), (w - k - 7, 11))
            pygame.draw.line(st, lo, (k + 6, h - 12), (w - k - 7, h - 12))
            for x in range(k + 6, w - k - 7, 16):
                st.set_at((x, 12), lo)
                st.set_at((x, h - 13), lo)
            if not self.compact:
                self.hex_rect = pygame.Rect(6, h - 66, 124, 50)
                self.scope_rect = pygame.Rect(w - 110, h - 66, 104, 50)
                for r, title in ((self.hex_rect, 'MEM TAP'), (self.scope_rect, 'THROUGHPUT')):
                    pygame.draw.rect(st, lo, r, 1)
                    st.fill((0, 0, 0), (r.x + 4, r.y, len(title) * 4 + 3, 1))
                    st.blit(self.tf.line(title, _mul(ac, 0.6)), (r.x + 6, r.y - 2))
                    st.fill(ac, (r.x, r.y, 3, 1))
                    st.fill(ac, (r.x, r.y, 1, 3))
                    st.fill(ac, (r.right - 3, r.bottom - 1, 3, 1))
                    st.fill(ac, (r.right - 1, r.bottom - 3, 1, 3))
                sr = self.scope_rect
                for i in range(1, 4):                              # scope graticule
                    for x in range(sr.x + 3, sr.right - 3, 4):
                        st.set_at((x, sr.y + i * sr.h // 4), _mul(ac, 0.14))
        back.blit(st, (0, 0))
        self.backdrop = back
        # rain falls behind the glass ball: per column, the rows the disc covers
        self.disc = {}
        if self.show_globe:
            R1 = self.R + 1
            for x in range(0, w, 4):
                dx = x + 1 - self.gx
                if abs(dx) < R1:
                    half = int(math.sqrt(R1 * R1 - dx * dx))
                    self.disc[x] = (self.gy - half, self.gy + half + 1)

    # ------------------------------------------------------------ helpers
    def _proj(self, v):
        p = self.M @ v
        return self.gx + float(p[0]) * self.R, self.gy - float(p[1]) * self.R, float(p[2])

    def _launch(self, a, b, col, city=None, speed=1.6, kind='out'):
        if len(self.arcs) < 28:
            self.arcs.append({'pts': _arc(a, b), 't': 0.0, 'speed': speed * random.uniform(0.8, 1.2), 'col': col,
                              'city': city, 'linger': 1.0, 'kind': kind, 'end': b})

    def _say(self, text, col, secs=1.8):
        self.banner = [text, col, secs, secs]

    def _pick_target(self):
        free = [i for i in range(len(self.cities)) if i not in self.rooted]
        if not free:
            self.rooted.clear()
            free = list(range(len(self.cities)))
            self._say('NETWORK OWNED - NEW GRID', self.ok_col, 2.5)
        self.target = random.choice(free)
        self.ping_ms = random.randint(9, 280)

    # ------------------------------------------------------------ update
    def update(self, dt, energy):
        super().update(dt, energy)
        now = time.time()
        e = min(2.0, energy)
        # globe rotation: idle drift + output + left / right keys
        want = (0.10 + e * 0.35) * self.spin
        if signals.recent(signals.right, 0.25):
            want += 1.6
        if signals.recent(signals.left, 0.25):
            want -= 1.6
        self.rot_v += (want - self.rot_v) * min(1, dt * 3)
        self.rot += self.rot_v * dt
        ca, sa = math.cos(self.rot), math.sin(self.rot)
        ct, st = math.cos(0.38), math.sin(0.38)
        ry = np.array([[ca, 0, sa], [0, 1, 0], [-sa, 0, ca]], np.float32)
        rx = np.array([[1, 0, 0], [0, ct, -st], [0, st, ct]], np.float32)
        self.M = rx @ ry
        # rain
        sp = 0.35 + e * 1.6 + (1.5 if self.alert > 0 else 0)
        h = self.h
        for d in self.drops:
            d[1] += d[2] * dt * sp
            if d[1] > h + 6:
                d[1] = -self.strips[d[3]].get_height() - random.uniform(0, h * 0.6)
                d[0] = random.randrange(0, max(1, self.w // 4)) * 4
                d[3] = random.randrange(len(self.strips))
        # typed letters become packets
        new, self.seq = signals.take_letters(self.seq)
        typed = [l for l in new if l[4]]
        for l in typed[-5:]:
            self.tap.append(l[1])
            if len(self.packets) < 24:
                self.packets.append([float(l[2]), float(l[3]), 0.0, l[1]])
        self.pkts += len(new)
        for p in self.packets:
            p[2] += dt * 2.8
        for p in [p for p in self.packets if p[2] >= 1]:
            n, v, _, _ = self.cities[self.target]
            self._launch(self.home, v, self.accent, self.target)
        self.packets = [p for p in self.packets if p[2] < 1]
        # ambient traffic between random cities, more of it under load
        if self.show_globe and random.random() < dt * (0.35 + e * 3.0):
            a, b = random.sample(self.cities, 2)
            self._launch(a[1], b[1], _mul(self.accent2, 0.75), None, speed=1.0, kind='amb')
        for a in self.arcs:
            if a['t'] < 1:
                a['t'] = min(1.0, a['t'] + dt * a['speed'])
                if a['t'] >= 1:
                    self.rings.append([a['end'], 0.0, a['col']])
            else:
                a['linger'] -= dt * 1.4
        self.arcs = [a for a in self.arcs if a['linger'] > 0]
        for r in self.rings:
            r[1] += dt
        self.rings = [r for r in self.rings if r[1] < 0.7]
        # command results
        if signals.cmd is not self.last_cmd and signals.cmd:
            self.last_cmd = signals.cmd
            if signals.cmd[0]:
                self.trace += random.uniform(14, 26)
                self.alert = 2.4
                self.glitch = 0.45
                signals.shake = max(signals.shake, 0.35)
                for c in random.sample(self.cities, 5):
                    self._launch(c[1], self.home, self.alert_col, None, speed=1.3, kind='trace')
                if self.trace >= 100:
                    self.trace = 0.0
                    self.rooted.clear()
                    self.glitch = 1.2
                    self._say('CONNECTION BURNED - REROUTING', self.alert_col, 2.8)
                else:
                    self._say('INTRUSION DETECTED', self.alert_col, 2.0)
            else:
                self.rooted.add(self.target)
                name, v, _, _ = self.cities[self.target]
                self.rings.append([v, -0.0, self.ok_col])
                self.grant = 1.0
                self.trace = max(0.0, self.trace - 8)
                self._say('ACCESS GRANTED - %s ROOTED' % name, self.ok_col, 1.8)
                self._pick_target()
        if signals.bell != self.last_bell:
            self.last_bell = signals.bell
            self.pings += [0.0, -0.18, -0.36]
        if signals.enter != self.last_enter:
            self.last_enter = signals.enter
            if self.scan is None:
                self.scan = 1.15
        if self.scan is not None:
            self.scan -= dt * 3.2
            if self.scan < -1.15:
                self.scan = None
        self.pings = [p + dt for p in self.pings if p + dt < 1.2]
        self.alert = max(0.0, self.alert - dt)
        self.glitch = max(0.0, self.glitch - dt)
        self.grant = max(0.0, self.grant - dt * 1.2)
        self.trace = max(0.0, self.trace - dt * 0.6)
        if self.banner:
            self.banner[2] -= dt
            if self.banner[2] <= 0:
                self.banner = None
        # hud feeds
        self.hex_t += dt * (0.8 + e * 9)
        while self.hex_t >= 1:
            self.hex_t -= 1
            self.hexlines.append('%04X  %s' % (random.randrange(65536), self._hexrow()))
        self.hist_t += dt
        if self.hist_t >= 0.1:
            self.hist_t = 0.0
            self.hist.append(min(1.0, e * 0.6 + random.uniform(0, 0.05) + (0.25 if signals.recent(signals.typing, 0.3) else 0)))
        self.idle = now - max(signals.typing, signals.enter) > 20

    # ------------------------------------------------------------ draw
    def _draw_globe(self, surf):
        R, gx, gy = self.R, self.gx, self.gy
        p = self.pts @ self.M.T
        z = p[:, 2]
        front = z > 0
        b = np.where(front, 0.42 + 0.78 * z, 0.10) * self.base
        if self.scan is not None:
            b += np.exp(-((p[:, 1] - self.scan) / 0.07) ** 2) * 1.4 * np.where(front, 1.0, 0.25)
        n = self.nland
        col = self.accent
        if self.alert > 0:
            col = _mix(col, self.alert_col, min(1.0, self.alert))
        elif self.grant > 0:
            col = _mix(col, self.ok_col, self.grant)
        if col != self._lut_col:                                  # brightness 0..2 -> packed pixel, entry 256 = white
            self._lut_col = col
            k = np.arange(256, dtype=np.float32)[:, None] / 127.5
            c = np.minimum(k * np.array(col, np.float32), 255).astype(np.uint32)
            rs, gs, bs, _ = self.gsurf.get_shifts()
            self._lut = np.append((c[:, 0] << rs) | (c[:, 1] << gs) | (c[:, 2] << bs), self.gsurf.map_rgb((255, 255, 255))).astype(np.uint32)
        idx = np.minimum(b * 127.5, 255).astype(np.intp)
        flick = np.random.random(n) < 0.004 + min(2.0, signals.energy) * 0.02
        idx[:n][flick & front[:n]] = 256
        val = self._lut[idx]
        sx = np.clip((p[:, 0] * R + (R + 1)).astype(np.intp), 0, 2 * R + 2)
        sy = np.clip(((R + 1) - p[:, 1] * R).astype(np.intp), 0, 2 * R + 2)
        self.gsurf.fill(0)
        px = pygame.surfarray.pixels2d(self.gsurf)
        back = ~front
        px[sx[back], sy[back]] = val[back]
        px[sx[front], sy[front]] = val[front]
        if R >= 120:                                              # big globe: land dots two pixels wide
            lf = front[:n]
            px[np.minimum(sx[:n][lf] + 1, 2 * R + 2), sy[:n][lf]] = val[:n][lf]
        del px
        surf.blit(self.gsurf, (gx - R - 1, gy - R - 1), special_flags=ADD)

    def _draw_net(self, surf):
        R, gx, gy, tf = self.R, self.gx, self.gy, self.tf
        M = self.M
        # arcs
        for a in self.arcs:
            P = a['pts'] @ M.T
            X = gx + P[:, 0] * R
            Y = gy - P[:, 1] * R
            vis = (P[:, 2] > 0) | (P[:, 0] ** 2 + P[:, 1] ** 2 > 1.0)
            n = len(P)
            head = a['t'] * (n - 1)
            hi = int(head)
            col = a['col']
            done = a['t'] >= 1
            for i in range(min(hi + 1, n - 1)):
                if not (vis[i] and vis[i + 1]):
                    continue
                f = max(0.0, 1 - (head - i) / (n * 0.6))
                if done:
                    f = max(f, 0.45) * a['linger']
                else:
                    f = max(f, 0.18)
                if f < 0.05:
                    continue
                pygame.draw.line(surf, _mul(col, f), (float(X[i]), float(Y[i])), (float(X[i + 1]), float(Y[i + 1])))
            if not done and vis[hi]:
                k = head - hi
                j = min(n - 1, hi + 1)
                hx, hy = float(X[hi] + (X[j] - X[hi]) * k), float(Y[hi] + (Y[j] - Y[hi]) * k)
                glow(surf, hx, hy, 4, _mul(col, 0.7))
                surf.fill((255, 255, 255), (int(hx), int(hy), 1, 1))
        # impact rings
        for v, age, col in self.rings:
            x, y, z = self._proj(v)
            if z > 0:
                k = max(0.0, age) / 0.7
                pygame.draw.circle(surf, _mul(col, 1 - k), (int(x), int(y)), int(2 + k * R * 0.14), 1)
        # cities
        blink = int(self.t * 3) % 2
        for i, (name, v, _, _) in enumerate(self.cities):
            x, y, z = self._proj(v)
            if z <= 0.05:
                continue
            x, y = int(x), int(y)
            if i in self.rooted:
                c = self.ok_col
                pygame.draw.polygon(surf, c, [(x, y - 3), (x + 3, y), (x, y + 3), (x - 3, y)], 1)
                if z > 0.35 and not self.compact:
                    tf.text(surf, x + 5, y - 2, name, _mul(c, 0.8))
            elif i == self.target:
                c = self.accent2
                d = 4 + blink
                for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                    surf.fill(c, (x + dx * d - (1 if dx > 0 else 0), y + dy * d, 2, 1))
                    surf.fill(c, (x + dx * d, y + dy * d - (1 if dy > 0 else 0), 1, 2))
                surf.fill((255, 255, 255), (x, y, 1, 1))
                tf.text(surf, x + 8, y - 2, name, c)
            else:
                surf.fill(_mul(self.accent, 0.4 + 0.6 * z), (x - 1, y, 3, 1))
                surf.fill(_mul(self.accent, 0.4 + 0.6 * z), (x, y - 1, 1, 3))
        # home node
        hx, hy, hz = self._proj(self.home)
        hc = self.alert_col if self.alert > 0 else (255, 255, 255)
        if hz > 0:
            pygame.draw.circle(surf, _mul(hc, 0.5 + 0.5 * math.sin(self.t * 5)), (int(hx), int(hy)), 4, 1)
            surf.fill(hc, (int(hx), int(hy), 1, 1))
            tf.text(surf, int(hx) - 7, int(hy) - 11, 'HOME', _mul(hc, 0.8))
        for age in self.pings:
            if age > 0:
                pygame.draw.circle(surf, _mul(self.accent, (1 - age / 1.2) * 0.9), (int(hx), int(hy)), int(3 + age * R * 1.1), 1)
        # relay satellite on its orbit
        a = self.t * 0.5
        sxp, syp = int(gx + math.cos(a) * R * 1.32), int(gy + math.sin(a) * R * 0.34)
        surf.fill(self.accent2, (sxp - 1, syp, 3, 1))
        surf.fill(self.accent2, (sxp, syp - 1, 1, 3))
        if not self.compact:
            tf.text(surf, sxp + 4, syp - 6, 'SAT-7', _mul(self.accent2, 0.7))
        # packets on their way from the keyboard to the home node
        for x0, y0, k, ch in self.packets:
            e = k * k * (3 - 2 * k)
            x = x0 + (hx - x0) * e
            y = y0 + (hy - y0) * e - math.sin(math.pi * k) * 14
            e2 = max(0.0, e - 0.12)
            pygame.draw.line(surf, _mul(self.accent, 0.5), (x0 + (hx - x0) * e2, y0 + (hy - y0) * e2 - math.sin(math.pi * max(0, k - 0.1)) * 14), (x, y))
            if ch.upper() in _F or ch in _EXTRA:
                surf.blit(tf.glyph(ch.upper(), (255, 255, 255)), (int(x) - 1, int(y) - 2), special_flags=ADD)
            else:
                surf.fill((255, 255, 255), (int(x), int(y), 2, 2))

    def _draw_hud(self, surf):
        w, h, tf = self.w, self.h, self.tf
        ac = self.accent
        mid = _mul(ac, 0.7)
        alert = self.alert > 0
        state = 'ALERT' if alert else ('STEALTH' if getattr(self, 'idle', False) else 'ACTIVE')
        sc = self.alert_col if alert else (self.ok_col if state == 'ACTIVE' else mid)
        k = max(6, min(w, h) // 22)
        x = tf.text(surf, k + 8, 4, self.callsign, ac)
        if not self.compact:
            x = tf.text(surf, x + 8, 4, 'NODE %s' % self.node, mid)
            x = tf.text(surf, x + 8, 4, 'TOR>VPN>SAT', _mul(self.accent2, 0.8))
        clock = time.strftime('%Y-%m-%d %H:%M:%S UTC' if not self.compact else '%H:%M:%S', time.gmtime())
        tf.text(surf, w - k - 8 - tf.width(clock), 4, clock, mid)
        # bottom status rail
        y = h - 9
        x = k + 8
        if not alert or int(self.t * 6) % 2:
            tf.text(surf, x, y, state, sc)
        x += 36
        x = tf.text(surf, x, y, 'CPM %03d' % min(999, int(signals.typing_speed())), mid) + 10
        if not self.compact:
            x = tf.text(surf, x, y, 'PKT %06d' % (self.pkts % 1000000), mid) + 10
        x = tf.text(surf, x, y, 'ROOT %02d/%02d' % (len(self.rooted), len(self.cities)), self.ok_col if self.rooted else mid) + 10
        # trace meter
        tr = min(100.0, self.trace)
        tcol = self.alert_col if tr > 60 else ((255, 190, 40) if tr > 30 else mid)
        x = tf.text(surf, x, y, 'TRACE', tcol) + 2
        bw = 40 if not self.compact else 20
        pygame.draw.rect(surf, _mul(tcol, 0.5), (x, y - 1, bw + 2, 7), 1)
        if tr > 0:
            surf.fill(tcol, (x + 1, y, int(bw * tr / 100), 5))
        x = tf.text(surf, x + bw + 6, y, '%02d%%' % tr, tcol) + 10
        up = int(time.time() - self.born)
        ut = 'UP %02d:%02d:%02d' % (up // 3600, up // 60 % 60, up % 60)
        if x + tf.width(ut) < w - k - 8:
            tf.text(surf, w - k - 8 - tf.width(ut), y, ut, mid)
        if self.compact:
            return
        # memory tap: the last keys you typed as hex on top, then the scrolling dump
        r = self.hex_rect
        tap = ' '.join('%02X' % (ord(c) & 255) for c in self.tap)
        tf.text(surf, r.x + 5, r.y + 6, 'KEYS', self.accent2)
        if tap:
            tf.text(surf, r.x + 29, r.y + 6, tap, (255, 255, 255) if signals.recent(signals.typing, 0.15) else self.accent2)
        for i, ln in enumerate(self.hexlines):
            tf.text(surf, r.x + 5, r.y + 13 + i * 6, ln, _mul(ac, 0.3 + 0.1 * i))
        # throughput scope
        r = self.scope_rect
        n = len(self.hist)
        pts = [(r.x + 3 + i * (r.w - 7) / (n - 1), r.bottom - 4 - v * (r.h - 12)) for i, v in enumerate(self.hist)]
        pygame.draw.lines(surf, _mul(sc if alert else ac, 0.9), False, pts)
        surf.fill((255, 255, 255), (int(pts[-1][0]), int(pts[-1][1]) - 1, 2, 2))
        # target read-out under the globe
        if self.show_globe:
            name, _, la, lo = self.cities[self.target]
            t1 = 'TGT %s  %04.1f%s %05.1f%s' % (name, abs(la), 'N' if la >= 0 else 'S', abs(lo), 'E' if lo >= 0 else 'W')
            t2 = 'PING %03dMS  HOPS %d' % (self.ping_ms + int(3 * math.sin(self.t * 2)), 3 + self.ping_ms % 5)
            yy = min(h - 28, self.gy + self.R + 14)
            tf.text(surf, self.gx - tf.width(t1) // 2, yy, t1, self.accent2)
            tf.text(surf, self.gx - tf.width(t2) // 2, yy + 7, t2, mid)

    def _draw_banner(self, surf):
        text, col, left, total = self.banner
        if left < total - 0.5 and int(left * 7) % 3 == 0:
            return                                                # blink
        sc = 3 if self.tf.width(text, 3) < self.w * 0.6 else (2 if self.tf.width(text, 2) < self.w - 20 else 1)
        tw = self.tf.width(text, sc)
        cx = self.gx if self.show_globe and tw / 2 + 8 < min(self.gx, self.w - self.gx) else self.w // 2
        x, y = cx - tw // 2, (self.gy if self.show_globe else self.h // 2) - 3 * sc
        box = pygame.Rect(x - 6, y - 5, tw + 12, 5 * sc + 10)
        surf.fill((0, 0, 0), box)
        pygame.draw.rect(surf, col, box, 1)
        surf.fill(col, (box.x, box.y, 4, 2))
        surf.fill(col, (box.right - 4, box.bottom - 2, 4, 2))
        self.tf.text(surf, x, y, text, col, sc)

    def draw(self, surf, first):
        w, h = self.w, self.h
        if first:
            surf.blit(self.backdrop, (0, 0))
        else:
            surf.blit(self.backdrop, (0, 0), special_flags=ADD)
        disc = self.disc
        for x, y, _, i in self.drops:
            s = self.strips[i]
            y = int(y) // 6 * 6
            d = disc.get(x)
            if d is None or y >= d[1] or y + s.get_height() <= d[0]:
                surf.blit(s, (x, y), special_flags=ADD)
            else:
                if y < d[0]:
                    surf.blit(s, (x, y), (0, 0, 3, d[0] - y), special_flags=ADD)
                if y + s.get_height() > d[1]:
                    surf.blit(s, (x, d[1]), (0, d[1] - y, 3, y + s.get_height() - d[1]), special_flags=ADD)
        if self.show_globe:
            self._draw_globe(surf)
            self._draw_net(surf)
        if self.show_hud:
            self._draw_hud(surf)
        if self.banner:
            self._draw_banner(surf)
        if self.alert > 0:
            surf.fill((int(46 * min(1.0, self.alert)), 0, int(8 * min(1.0, self.alert))), special_flags=ADD)
        elif self.grant > 0:
            surf.fill((0, int(26 * self.grant), int(10 * self.grant)), special_flags=ADD)
        if self.glitch > 0:                                       # the picture tears
            for _ in range(2 + int(self.glitch * 6)):
                y = random.randrange(0, max(1, h - 12))
                hh = random.randint(2, 11)
                band = surf.subsurface((0, y, w, min(hh, h - y))).copy()
                surf.blit(band, (random.randint(-14, 14), y))


SCENES = {'zeroday': ZeroDay}
