"""Live weather background.

Fetches the current weather for your location from Open-Meteo (free, no API
key) every few minutes in a background thread and simulates it: sky colors
by sun position, sun / moon / stars, drifting clouds by cloud cover, rain,
drizzle, showers, snow, fog, and thunderstorms with lightning (and thunder).
Wind drives clouds, rain slant and snow drift.

The scene: a dithered pixel-art sky following the real time of day (sunrise /
sunset from the API, or computed astronomically), sun with rays, the moon in
its *real* phase with halo, twinkling stars and shooting stars, three layers
of shaded clouds lit by dawn / dusk / storm light and city light pollution, a
skyline with sunlit facades and lit windows at night, seasonal swaying trees
(autumn leaves blow in the wind), street lamps, a road with little cars
(headlights at night, spray in the rain), rain in depth with splashes and
rippling wet reflections, snow that settles on the rooftops, fog banks,
forked lightning with flicker and thunder delayed by distance, birds - and a
pixel weather widget.

theme:   background: [weather]
         bg_params:
           weather: {location: auto,     # auto (IP based) | "Berlin" | [lat, lon]
                     refresh_min: 10,
                     simulate: null,     # force: clear cloudy rain snow fog storm
                     timelapse: 0,       # seconds per simulated day (0 = real clock)
                     hour: null,         # freeze the time of day
                     widget: true}
demo shell:  weather [clear|cloudy|rain|snow|fog|storm|live|timelapse [secs]]
Offline the background cycles through all conditions as a demo.
"""
from __future__ import annotations

import json
import math
import random
import threading
import time
import urllib.parse
import urllib.request

import numpy as np
import pygame

from .backgrounds import Background

UA = {'User-Agent': 'pixelterm/1.0 (terminal weather background)'}
WMO = {0: 'clear', 1: 'mostly clear', 2: 'partly cloudy', 3: 'overcast', 45: 'fog', 48: 'rime fog',
       51: 'light drizzle', 53: 'drizzle', 55: 'dense drizzle', 56: 'freezing drizzle', 57: 'freezing drizzle',
       61: 'light rain', 63: 'rain', 65: 'heavy rain', 66: 'freezing rain', 67: 'freezing rain',
       71: 'light snow', 73: 'snow', 75: 'heavy snow', 77: 'snow grains', 80: 'showers', 81: 'showers',
       82: 'violent showers', 85: 'snow showers', 86: 'snow showers', 95: 'thunderstorm',
       96: 'thunderstorm + hail', 99: 'thunderstorm + hail'}
SIM = {
    'clear': dict(code=0, cloud=5, rain=0, snow=0, wind=3),
    'cloudy': dict(code=3, cloud=90, rain=0, snow=0, wind=6),
    'rain': dict(code=63, cloud=95, rain=3.0, snow=0, wind=8),
    'snow': dict(code=73, cloud=90, rain=0, snow=2.0, wind=4),
    'fog': dict(code=45, cloud=100, rain=0, snow=0, wind=1),
    'storm': dict(code=95, cloud=100, rain=6.0, snow=0, wind=16),
}
SOUND = None   # set by the app: fn(name)


def _get(url, timeout=8):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


class WeatherFeed:
    """background thread keeping .data fresh (shared by all weather layers)"""
    _inst = None

    @classmethod
    def get(cls, location='auto', refresh_min=10):
        if cls._inst is None or cls._inst.location != location:
            cls._inst = cls(location, refresh_min)
        return cls._inst

    def __init__(self, location, refresh_min):
        self.location = location
        self.refresh = max(2.0, float(refresh_min)) * 60
        self.data = None
        self.place = None
        self.error = None
        self.updated = 0.0
        threading.Thread(target=self._run, daemon=True).start()

    def _locate(self):
        loc = self.location
        if isinstance(loc, (list, tuple)) and len(loc) == 2:
            return float(loc[0]), float(loc[1]), '%.2f,%.2f' % (loc[0], loc[1])
        if loc and loc != 'auto':
            q = urllib.parse.quote(str(loc))
            j = _get('https://geocoding-api.open-meteo.com/v1/search?count=1&name=' + q)
            r = j['results'][0]
            return r['latitude'], r['longitude'], r.get('name', loc)
        for url in ('https://ipapi.co/json/', 'http://ip-api.com/json/?fields=status,lat,lon,city'):
            try:
                j = _get(url, 5)
                lat = j.get('latitude', j.get('lat'))
                lon = j.get('longitude', j.get('lon'))
                if lat is not None:
                    return float(lat), float(lon), j.get('city') or 'here'
            except Exception:
                continue
        raise RuntimeError('cannot determine location')

    def _run(self):
        while True:
            try:
                if self.place is None:
                    self.place = self._locate()
                lat, lon, name = self.place
                url = ('https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f'
                       '&current=temperature_2m,relative_humidity_2m,is_day,precipitation,rain,showers,snowfall,'
                       'weather_code,cloud_cover,wind_speed_10m,wind_direction_10m'
                       '&daily=sunrise,sunset&timezone=auto&forecast_days=1') % (lat, lon)
                j = _get(url)
                self.data = parse(j, name)
                self.data['lat'], self.data['lon'] = lat, lon
                self.error = None
                self.updated = time.time()
                time.sleep(self.refresh)
            except Exception as e:
                self.error = str(e)[:80]
                time.sleep(60)


def parse(j, name='here'):
    c = j.get('current', {})
    d = j.get('daily', {})
    code = int(c.get('weather_code', 0) or 0)
    out = {
        'place': name, 'code': code, 'text': WMO.get(code, 'weather %d' % code),
        'temp': c.get('temperature_2m'), 'humidity': c.get('relative_humidity_2m'), 'cloud': float(c.get('cloud_cover', 0) or 0),
        'rain': float(c.get('rain', 0) or 0) + float(c.get('showers', 0) or 0) + float(c.get('precipitation', 0) or 0) * 0.3,
        'snow': float(c.get('snowfall', 0) or 0) * 2,
        'wind': float(c.get('wind_speed_10m', 0) or 0) / 3.6, 'wind_dir': float(c.get('wind_direction_10m', 270) or 270),
        'is_day': int(c.get('is_day', 1) or 0), 'time': c.get('time'),
        'sunrise': (d.get('sunrise') or [None])[0], 'sunset': (d.get('sunset') or [None])[0],
    }
    if 51 <= code <= 67 or 80 <= code <= 82 or code >= 95:
        out['rain'] = max(out['rain'], 0.6 if code < 63 else 2.5)
    if 71 <= code <= 77 or code in (85, 86):
        out['snow'] = max(out['snow'], 1.5)
    return out


def _hm(s):
    try:
        t = s.split('T')[1]
        h, m = t.split(':')[:2]
        return int(h) + int(m) / 60
    except Exception:
        return None


# ============================================================================ astronomy (offline fallback)
def solar_times(lat, lon, when=None):
    """approximate local sunrise / sunset (hours) - good to a few minutes"""
    t = time.localtime(when)
    n = t.tm_yday
    tz = t.tm_gmtoff / 3600.0
    decl = math.radians(23.44) * math.sin(2 * math.pi * (284 + n) / 365)
    la = math.radians(lat)
    x = -math.tan(la) * math.tan(decl)
    x = max(-1.0, min(1.0, x))
    ha = math.degrees(math.acos(x))
    b = 2 * math.pi * (n - 81) / 364
    eot = (9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)) / 60.0
    noon = 12 - lon / 15.0 + tz - eot
    return noon - ha / 15, noon + ha / 15


def moon_phase(when=None):
    """0 = new, 0.5 = full"""
    ref = 947182440  # 2000-01-06 18:14 UTC new moon
    days = ((when or time.time()) - ref) / 86400.0
    return (days % 29.530588853) / 29.530588853


def season(lat=52):
    m = time.localtime().tm_mon
    if lat < 0:
        m = (m + 5) % 12 + 1
    return {12: 'winter', 1: 'winter', 2: 'winter', 3: 'spring', 4: 'spring', 5: 'spring',
            6: 'summer', 7: 'summer', 8: 'summer'}.get(m, 'autumn')


# ============================================================================ tiny 3x5 pixel font for the widget
_F = {
    'A': ".#.#.####.##.#", 'B': "##.#.###.#.###.", 'C': ".###..#..#...##", 'D': "##.#.##.##.###.",
    'E': "####..##.#..###", 'F': "####..##.#..#..", 'G': ".###..#.##.#.##", 'H': "#.##.####.##.#",
    'I': "###.#..#..#.###", 'J': "..#..#..##.#.#.", 'K': "#.##.###.#.##.#", 'L': "#..#..#..#..###",
    'M': "#.#####.##.#", 'N': "##.#.##.##.##.#", 'O': ".#.#.##.##.#.#.", 'P': "##.#.###.#..#..",
    'Q': ".#.#.##.###..##", 'R': "##.#.###.#.##.#", 'S': ".###...#...###.", 'T': "###.#..#..#..#.",
    'U': "#.##.##.##.####", 'V': "#.##.##.##.#.#.", 'W': "#.##.#######.#", 'X': "#.##.#.#.#.##.#",
    'Y': "#.##.#.#..#..#.", 'Z': "###..#.#.#..###", '0': "####.##.##.####", '1': ".#.##..#..#.###",
    '2': "##...#.#.#..###", '3': "##...#.#...###.", '4': "#.##.####..#..#", '5': "####..##...###.",
    '6': ".###..####.####", '7': "###..#.#..#..#.", '8': "####.#####.####", '9': "####.####..###.",
    '°': "##.##.........", '.': ".............#.", '-': "......###......", '/': "..#..#.#.#..#..",
    ':': "....#.....#....", '%': "#.#..#.#.#..#.#", '+': "....#.###.#....", ' ': "...............",
    '(': ".#.#..#..#...#.", ')': ".#...#..#..#.#.",
}
for _k, _v in list(_F.items()):  # normalise to 15 chars (some rows above were written short)
    if len(_v) != 15:
        _F[_k] = (_v + '.' * 15)[:15]
_F['A'] = ".#.#.#####.##.#"
_F['H'] = "#.##.#####.##.#"
_F['M'] = "#.########.##.#"
_F['W'] = "#.##.########.#"
_F['°'] = "##.##.........."


def tiny_text(surf, x, y, text, col):
    for ch in text.upper():
        g = _F.get(ch, _F[' '])
        for i, b in enumerate(g):
            if b == '#':
                surf.fill(col, (x + i % 3, y + i // 3, 1, 1))
        x += 4
    return x


BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16.0 - 0.5)


def _lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


# ============================================================================ the scene
class Weather(Background):
    name = 'weather'
    opaque = True

    def resize(self, w, h):
        super().resize(w, h)
        prm = self.params.get('weather', {}) if isinstance(self.params.get('weather'), dict) else {}
        self.prm = prm
        self.sim = prm.get('simulate')
        self.timelapse = float(prm.get('timelapse', 0) or 0)   # seconds per simulated day (0 = real time)
        self.hour_override = prm.get('hour')
        self.feed = None if self.sim else WeatherFeed.get(prm.get('location', 'auto'), prm.get('refresh_min', 10))
        self.lat, self.lon = prm.get('lat', 52.52), prm.get('lon', 13.40)
        self.cur = dict(cloud=0.3, rain=0.0, snow=0.0, fog=0.0, wind=2.0, storm=0.0, temp=10.0)
        self.wet = 0.0
        self.snow_cover = 0.0
        self.flash = 0.0
        self.flash_seq = []
        self.bolts = []
        self.thunder = []
        self.label = ''
        self.info = {}
        self.rng = random.Random(42)
        self.ground_y = int(h * 0.86)
        self._build_landscape()
        self._build_clouds()
        self._build_particles()
        self.sky_key = None
        self.cache = {}
        self.shoot = None
        self.birds = None

    # ------------------------------------------------------------ static scene
    def _mask_surface(self, mask):
        s = pygame.Surface(mask.shape, pygame.SRCALPHA)
        s.fill((255, 255, 255, 0))
        a = pygame.surfarray.pixels_alpha(s)
        a[:] = mask.astype(np.uint8) * 255
        del a
        return s

    def _edge(self, mask):
        e = np.zeros_like(mask)
        e[:, 1:] = mask[:, 1:] & ~mask[:, :-1]
        e[:, 2:] |= mask[:, 2:] & ~mask[:, :-2] & (self.h > 300)
        return e

    def _build_landscape(self):
        w, h = self.w, self.h
        r = self.rng
        gy = self.ground_y
        xs = np.arange(w)
        # far hills
        hills = gy - h * 0.10 - (np.sin(xs / w * 7 + 1) * 0.04 + np.sin(xs / w * 17) * 0.015 + np.sin(xs / w * 3.1) * 0.05) * h
        yy = np.arange(h)[None, :]
        far = yy >= hills[:, None]
        # city skyline
        city = np.zeros((w, h), bool)
        self.windows = []
        self.buildings = []
        x = int(w * 0.04)
        tower_x = int(w * 0.63)
        while x < w * 0.96:
            bw = r.randint(max(4, w // 70), max(6, w // 28))
            bh = int(h * r.uniform(0.07, 0.26))
            if abs(x - tower_x) < w * 0.05:
                bh = int(bh * 0.6)
            top = gy - bh
            city[x:x + bw, top:gy] = True
            self.buildings.append((x, top, bw, bh))
            if r.random() < 0.25:  # antenna
                ax = x + bw // 2
                city[ax, max(0, top - h // 30):top] = True
            if r.random() < 0.2 and bw > 6:  # stepped top
                city[x + 2:x + bw - 2, max(0, top - 3):top] = True
            for wx in range(x + 2, x + bw - 1, 3):
                for wy in range(top + 3, gy - 3, 4):
                    if r.random() < 0.55:
                        self.windows.append((wx, wy, r.random(), r.random() < 0.08))
            x += bw + r.randint(0, max(1, w // 120))
        # tv tower (generic needle with a sphere)
        th = int(h * 0.48)
        city[tower_x - 1:tower_x + 2, gy - th:gy] = True
        cy = gy - int(th * 0.72)
        rr = max(3, h // 45)
        yy2, xx2 = np.ogrid[-rr:rr + 1, -rr:rr + 1]
        disc = (xx2 * xx2 + yy2 * yy2) <= rr * rr
        city[tower_x - rr:tower_x + rr + 1, cy - rr:cy + rr + 1] |= disc.T
        city[tower_x, gy - th - h // 14:gy - th] = True
        self.tower_light = (tower_x, gy - th - h // 14)
        # near ground with bumps
        ground = gy + (np.sin(xs / w * 9) * 0.012 * h).astype(np.int32)
        near = yy >= ground[:, None]
        self.ground_top = ground
        self.layers = {'far': far, 'city': city, 'near': near}
        self.layer_surf = {k: self._mask_surface(m) for k, m in self.layers.items()}
        # facade detail: daytime window grid (dark) and a lit side per building
        self.facade = pygame.Surface((w, h), pygame.SRCALPHA)
        self.facade.fill((0, 0, 0, 0))
        self.side_l = pygame.Surface((w, h), pygame.SRCALPHA)
        self.side_l.fill((0, 0, 0, 0))
        self.side_r = pygame.Surface((w, h), pygame.SRCALPHA)
        self.side_r.fill((0, 0, 0, 0))
        for bx, by, bw, bh in self.buildings:
            for wx in range(bx + 2, bx + bw - 1, 3):
                for wy in range(by + 3, gy - 3, 4):
                    self.facade.fill((0, 0, 20, 70), (wx, wy, 1, 2))
            half = max(1, bw // 3)
            self.side_l.fill((255, 255, 255, 40), (bx, by, half, bh))
            self.side_r.fill((255, 255, 255, 40), (bx + bw - half, by, half, bh))
            self.side_l.fill((255, 255, 255, 70), (bx, by, bw, 1))
            self.side_r.fill((255, 255, 255, 70), (bx, by, bw, 1))
        # grass tufts along the ground line
        self.tufts = [(x, int(ground[x])) for x in range(0, w, 2) if r.random() < 0.5]
        self.edge_surf = {k: self._mask_surface(self._edge(m)) for k, m in self.layers.items()}
        # trees and lamps on the near ground
        self.trees = []
        nt = max(3, w // 90)
        for i in range(nt):
            tx = int(w * (0.05 + 0.9 * (i + r.random() * 0.6) / nt))
            if abs(tx - tower_x) < w * 0.04:
                continue
            self.trees.append(self._tree(tx, int(ground[min(w - 1, tx)]), r))
        self.lamps = []
        for i in range(max(3, w // 110)):
            lx = int(w * (0.1 + 0.8 * (i + 0.5) / max(3, w // 110)))
            self.lamps.append((lx, int(ground[min(w - 1, lx)])))
        rad = max(8, h // 10)
        self.lamp_glow = pygame.Surface((rad * 2, rad * 2))
        self.lamp_glow.fill((0, 0, 0))
        for i in range(rad, 0, -1):
            k = (1 - i / rad) ** 2
            pygame.draw.circle(self.lamp_glow, (int(120 * k), int(90 * k), int(40 * k)), (rad, rad), i)
        self.road_y = gy + max(3, (h - gy) // 2)
        self.cars = []
        self.car_t = 0.0
        self.stars = [(r.uniform(0, w), r.uniform(0, gy * 0.8), r.random(), r.random() < 0.08) for _ in range(w * h // 900)]

    def _tree(self, x, gy, r):
        h = self.h
        size = max(4, int(h * r.uniform(0.035, 0.06)))
        trunk = max(1, size // 4)
        blobs = sorted([(r.uniform(-size * 0.65, size * 0.65), r.uniform(-size * 0.55, size * 0.35), r.uniform(size * 0.28, size * 0.5))
                        for _ in range(11)], key=lambda b: -b[1])
        return {'x': x, 'gy': gy, 'size': size, 'trunk': trunk, 'blobs': blobs, 'phase': r.uniform(0, 6.28),
                'hue': r.random()}

    def _build_clouds(self):
        r = self.rng
        self.clouds = []
        for layer, n, scale in (('far', 8, 0.6), ('mid', 7, 1.0), ('near', 5, 1.5)):
            for _ in range(n):
                self.clouds.append(self._make_cloud(layer, scale, r))
        for c in self.clouds:
            c['x'] = r.uniform(-c['w'], self.w)

    def _make_cloud(self, layer, scale, r):
        cw = int(self.w * r.uniform(0.12, 0.26) * scale)
        ch = max(8, int(cw * r.uniform(0.42, 0.55)))
        X, Y = np.meshgrid(np.arange(cw, dtype=np.float32), np.arange(ch, dtype=np.float32), indexing='ij')
        base = ch * 0.86
        mask = np.zeros((cw, ch), bool)
        n = r.randint(5, 9)
        for i in range(n):
            px = cw * (0.12 + 0.76 * (i + r.random() * 0.8) / n)
            mid = 1 - abs(px / cw - 0.5) * 1.6
            rad = cw * r.uniform(0.10, 0.16) * (0.6 + mid)
            py = base - rad * r.uniform(0.25, 0.75)
            mask |= (X - px) ** 2 + ((Y - py) * 1.15) ** 2 < rad * rad
        mask |= ((X - cw * 0.5) / (cw * 0.46)) ** 2 + ((Y - base + ch * 0.08) / (ch * 0.16)) ** 2 < 1
        wav = (np.sin(X[:, 0] * 0.35 + r.random() * 6) * 1.2).astype(np.float32)
        mask &= Y < (base + wav[:, None])
        top = np.argmax(mask, axis=1).astype(np.float32)
        has = mask.any(axis=1)
        top[~has] = base
        depth = np.clip((Y - top[:, None]) / np.maximum(1, base - top[:, None]), 0, 1)
        noise = np.random.default_rng(r.randint(0, 10 ** 6)).random((cw // 2 + 2, ch // 2 + 2)).astype(np.float32)
        noise = np.kron(noise, np.ones((2, 2), np.float32))[:cw, :ch]
        shade = 1.05 - depth ** 0.8 * 0.85 + (noise - 0.5) * 0.18
        shade -= np.clip((Y - base * 0.8) / (base * 0.2), 0, 1) * 0.2           # darker belly
        rim = np.zeros_like(mask)
        rim[:, 1:] = mask[:, 1:] & ~mask[:, :-1]
        shade[rim] = 1.25
        er = mask.copy()
        er[1:, :] &= mask[:-1, :]
        er[:-1, :] &= mask[1:, :]
        er[:, 1:] &= mask[:, :-1]
        er[:, :-1] &= mask[:, 1:]
        alpha = np.where(er, 240, 140) * mask
        y = r.uniform(0.02, 0.20 if layer == 'far' else 0.36) * self.ground_y
        return {'layer': layer, 'w': cw, 'h': ch, 'mask': mask, 'alpha': alpha.astype(np.uint8), 'shade': shade,
                'x': 0.0, 'y': y, 'speed': {'far': 0.4, 'mid': 0.75, 'near': 1.2}[layer], 'surf': None, 'key': None,
                'thresh': r.random()}

    def _build_particles(self):
        w, h = self.w, self.h
        n = 3000
        g = np.random.default_rng(7)
        self.rx = g.uniform(0, w, n).astype(np.float32)
        self.ry = g.uniform(0, h, n).astype(np.float32)
        self.rz = g.uniform(0, 1, n).astype(np.float32) ** 1.5     # depth 0 far .. 1 near
        self.sx = g.uniform(0, w, n).astype(np.float32)
        self.sy = g.uniform(0, h, n).astype(np.float32)
        self.sz = g.uniform(0, 1, n).astype(np.float32)
        self.sp = g.uniform(0, 6.28, n).astype(np.float32)
        self.splash = np.zeros((0, 4), np.float32)   # x, y, vy, life
        m = 60
        self.lx = g.uniform(0, w, m).astype(np.float32)
        self.ly = g.uniform(0, self.ground_y, m).astype(np.float32)
        self.lp = g.uniform(0, 6.28, m).astype(np.float32)
        self.lc = g.integers(0, 4, m)

    # ------------------------------------------------------------ data -> targets
    def _hour(self):
        if self.hour_override is not None:
            return float(self.hour_override)
        if self.timelapse:
            return (self.t / self.timelapse * 24 + 6) % 24
        t = time.localtime()
        return t.tm_hour + t.tm_min / 60 + t.tm_sec / 3600

    def target(self):
        d = None
        live = False
        if self.sim:
            d = dict(SIM.get(self.sim, SIM['clear']))
            d.update(place='SIMULATED', text=WMO.get(d['code'], self.sim), temp=None)
        elif self.feed and self.feed.data:
            d = self.feed.data
            live = True
        else:
            names = list(SIM)
            k = names[int(self.t / 25) % len(names)]
            d = dict(SIM[k])
            d.update(place='OFFLINE DEMO', text=WMO.get(d['code'], k), temp=None)
        code = d.get('code', 0)
        lat, lon = d.get('lat', self.lat), d.get('lon', self.lon)
        sr, ss = _hm(d.get('sunrise') or ''), _hm(d.get('sunset') or '')
        if sr is None or ss is None or self.timelapse or self.hour_override is not None:
            sr, ss = solar_times(lat, lon)
        self.sun_times = (sr, ss)
        self.lat_used = lat
        temp = d.get('temp')
        self.info = dict(place=str(d.get('place', '')), text=str(d.get('text', '')), temp=temp, live=live,
                         wind=abs(d.get('wind', 0) or 0) * 3.6, wind_dir=d.get('wind_dir', 270), code=code,
                         humidity=d.get('humidity'))
        lbl = '%s  %s%s' % (self.info['place'], self.info['text'],
                            ('  %.0f°C' % temp) if isinstance(temp, (int, float)) else '')
        self.label = lbl + ('  (live)' if live else '')
        return dict(cloud=d.get('cloud', 0) / 100.0, rain=min(1.0, d.get('rain', 0) / 4.0),
                    snow=min(1.0, d.get('snow', 0) / 2.0), fog=1.0 if code in (45, 48) else 0.0,
                    wind=(d.get('wind', 2) or 0) * -math.sin(math.radians(d.get('wind_dir', 270) or 270)),
                    storm=1.0 if code >= 95 else 0.0,
                    temp=temp if isinstance(temp, (int, float)) else 10.0)

    def daylight(self):
        h = self._hour()
        sr, ss = self.sun_times
        if h < sr - 0.8 or h > ss + 0.8:
            return 0.0
        if h < sr + 0.8:
            return (h - (sr - 0.8)) / 1.6
        if h > ss - 0.8:
            return ((ss + 0.8) - h) / 1.6
        return 1.0

    # ------------------------------------------------------------ simulation
    def update(self, dt, energy):
        self.t += dt
        tg = self.target()
        k = 1 - math.exp(-dt * 0.35)
        for key, v in tg.items():
            self.cur[key] += (v - self.cur[key]) * k
        c = self.cur
        w, h, gy = self.w, self.h, self.ground_y
        wind = c['wind']
        self.day = self.daylight()
        # wetness & snow cover
        self.wet = min(1.0, self.wet + c['rain'] * dt * 0.2) if c['rain'] > 0.05 else max(0.0, self.wet - dt * 0.004)
        if c['snow'] > 0.05 and c['temp'] < 3:
            self.snow_cover = min(1.0, self.snow_cover + c['snow'] * dt * 0.02)
        else:
            self.snow_cover = max(0.0, self.snow_cover - dt * (0.002 + max(0, c['temp']) * 0.0008))
        # rain: depth controls speed
        sp = (0.9 + self.rz * 1.6) * h * 1.1
        self.ry += sp * dt
        self.rx += wind * (2 + self.rz * 6) * dt
        floor = gy + (h - gy) * self.rz
        hit = self.ry > floor
        nh = int(hit.sum())
        if nh:
            near = hit & (self.rz > 0.55) & (np.arange(len(self.rz)) < int(len(self.rz) * c['rain']))
            nn = int(near.sum())
            if nn:
                sp_new = np.stack([self.rx[near], floor[near], -np.random.uniform(20, 60, nn).astype(np.float32),
                                   np.full(nn, 0.25, np.float32)], 1)
                self.splash = np.concatenate([self.splash, sp_new])[-600:]
            self.ry[hit] = np.random.uniform(-h * 0.3, 0, nh)
            self.rx[hit] = np.random.uniform(-40, w + 40, nh)
        self.rx = (self.rx + 60) % (w + 120) - 60
        if len(self.splash):
            self.splash[:, 1] += self.splash[:, 2] * dt
            self.splash[:, 2] += 300 * dt
            self.splash[:, 3] -= dt
            self.splash = self.splash[self.splash[:, 3] > 0]
        # snow
        self.sy += h * (0.05 + self.sz * 0.12) * dt
        self.sx += (wind * (1 + self.sz * 3) + np.sin(self.sp + self.t * (0.8 + self.sz)) * (3 + self.sz * 8)) * dt
        m = self.sy > gy + (h - gy) * self.sz
        self.sy[m] = -2
        self.sx[m] = np.random.uniform(0, w, int(m.sum()))
        self.sx %= w
        # leaves (autumn wind)
        if season(self.lat_used) == 'autumn' and c['snow'] < 0.2:
            self.lx += (wind * 6 + np.sin(self.lp + self.t * 2) * 10) * dt
            self.ly += (12 + np.sin(self.lp * 3 + self.t * 3) * 10) * dt
            out = (self.ly > gy + 6) | (self.lx > w + 5) | (self.lx < -5)
            no = int(out.sum())
            if no:
                self.ly[out] = np.random.uniform(gy * 0.6, gy, no)
                self.lx[out] = (-4 if wind > 0 else w + 4) + np.random.uniform(-2, 2, no)
        # clouds
        for cl in self.clouds:
            cl['x'] += (2 + wind * 2.5) * cl['speed'] * dt
            if cl['x'] > w + 10:
                cl['x'] = -cl['w']
            elif cl['x'] < -cl['w'] - 10:
                cl['x'] = w
        # lightning
        if c['storm'] > 0.5 and random.random() < dt * 0.3:
            self._strike()
        if self.flash_seq:
            self.flash_seq[0][1] -= dt
            self.flash = self.flash_seq[0][0]
            if self.flash_seq[0][1] <= 0:
                self.flash_seq.pop(0)
        else:
            self.flash = max(0.0, self.flash - dt * 4)
            if self.flash < 0.05:
                self.bolts = []
        if self.thunder and time.time() >= self.thunder[0]:
            self.thunder.pop(0)
            if SOUND:
                SOUND('boom')
        # traffic
        self.car_t -= dt
        if self.car_t <= 0 and len(self.cars) < max(2, w // 120):
            self.car_t = random.uniform(1.5, 6.0)
            d = random.choice((-1, 1))
            col = random.choice([(200, 40, 40), (40, 90, 200), (230, 230, 230), (40, 40, 45), (220, 180, 40), (60, 150, 80)])
            self.cars.append([(-14.0 if d > 0 else w + 14.0), d, random.uniform(18, 34), col, random.random() < 0.15])
        slow = 1 - min(0.5, c['rain'] * 0.4 + c['snow'] * 0.5 + c['fog'] * 0.4)
        for car in self.cars:
            car[0] += car[1] * car[2] * slow * dt
        self.cars = [car for car in self.cars if -20 < car[0] < w + 20]
        # shooting stars & birds
        if self.day < 0.15 and c['cloud'] < 0.4 and self.shoot is None and random.random() < dt * 0.05:
            self.shoot = [random.uniform(w * 0.2, w), random.uniform(0, gy * 0.3), 1.0]
        if self.shoot:
            self.shoot[0] -= w * 0.6 * dt
            self.shoot[1] += h * 0.25 * dt
            self.shoot[2] -= dt * 1.4
            if self.shoot[2] <= 0:
                self.shoot = None
        if self.day > 0.7 and c['rain'] < 0.1 and c['storm'] < 0.1 and self.birds is None and random.random() < dt * 0.03:
            d = 1 if random.random() < 0.5 else -1
            self.birds = [d, -20 if d > 0 else w + 20, random.uniform(gy * 0.2, gy * 0.55),
                          [(random.uniform(-14, 0), random.uniform(-6, 6), random.uniform(0, 6)) for _ in range(random.randint(3, 6))]]
        if self.birds:
            self.birds[1] += self.birds[0] * 22 * dt
            if not (-40 < self.birds[1] < w + 40):
                self.birds = None

    def _strike(self):
        w, gy = self.w, self.ground_y
        x0 = random.uniform(w * 0.1, w * 0.9)
        bolts = []

        def branch(x, y, ang, length, depth):
            pts = [(x, y)]
            seg = max(3, length / 10)
            while length > 0 and y < gy:
                ang += random.uniform(-0.5, 0.5)
                ang = max(0.3, min(2.8, ang))
                x += math.cos(ang) * seg
                y += math.sin(ang) * seg
                pts.append((x, y))
                length -= seg
                if depth < 2 and random.random() < 0.12:
                    branch(x, y, ang + random.choice((-0.7, 0.7)), length * 0.4, depth + 1)
            bolts.append((pts, depth))
        branch(x0, 0, math.pi / 2, gy * 1.2, 0)
        self.bolts = bolts
        self.flash_seq = [[1.0, 0.05], [0.25, 0.06], [0.9, 0.05], [0.5, 0.08], [0.15, 0.1]]
        dist_km = random.uniform(0.8, 8)
        self.thunder.append(time.time() + dist_km * 3.0)

    # ------------------------------------------------------------ palette
    def palette(self):
        c = self.cur
        day = self.day
        dusk = max(0.0, 1 - abs(day - 0.5) * 2) if 0.02 < day < 0.98 else 0.0
        grey = min(1.0, c['cloud'] * 0.75 + c['rain'] * 0.35 + c['storm'] * 0.4 + c['fog'] * 0.5)
        night = ((6, 8, 26), (14, 18, 48), (28, 30, 66))
        dayc = ((38, 102, 214), (84, 152, 236), (170, 214, 250))
        dawn = ((58, 56, 128), (196, 92, 120), (255, 170, 90))
        sky = [_lerp(night[i], dayc[i], day) for i in range(3)]
        sky = [_lerp(sky[i], dawn[i], dusk * 0.85) for i in range(3)]
        gday = ((108, 116, 130), (138, 146, 158), (168, 174, 184))
        gnight = ((14, 15, 20), (20, 22, 28), (28, 30, 36))
        gg = [_lerp(gnight[i], gday[i], day) for i in range(3)]
        sky = [_lerp(sky[i], gg[i], grey) for i in range(3)]
        night = 1 - min(1.0, day * 2.5)
        glow = night * (0.25 + 0.6 * min(1.0, c['cloud'] + c['fog']))
        sky[2] = _lerp(sky[2], (92, 62, 52), glow * 0.7)
        sky[1] = _lerp(sky[1], (52, 40, 48), glow * 0.45)
        amb = _lerp((48, 52, 92), (255, 255, 255), day)
        amb = _lerp(amb, (255, 170, 120), dusk * 0.5)
        amb = _lerp(amb, (150, 155, 165), grey * 0.5 * day)
        return sky, amb, dusk, grey

    def _sky_surface(self, sky, sun):
        w, h = self.w, self.h
        key = tuple(int(v) // 3 for col in sky for v in col) + (int(sun[0]) // 6, int(sun[1]) // 6, int(sun[2] * 10))
        if key == self.sky_key:
            return self.sky_surf
        self.sky_key = key
        top, mid, hor = [np.array(c, np.float32) for c in sky]
        y = np.linspace(0, 1, h, dtype=np.float32)
        hz = self.ground_y / h
        t1 = np.clip(y / (hz * 0.55), 0, 1)[:, None]
        t2 = np.clip((y - hz * 0.55) / (hz * 0.45), 0, 1)[:, None]
        rows = np.where(y[:, None] < hz * 0.55, top + (mid - top) * t1, mid + (hor - mid) * t2)
        img = np.repeat(rows[None, :, :], w, 0)
        sx, sy, glow = sun
        if glow > 0.01:
            X = np.arange(w, dtype=np.float32)[:, None]
            Y = np.arange(h, dtype=np.float32)[None, :]
            dd = np.sqrt((X - sx) ** 2 + ((Y - sy) * 1.4) ** 2) / (w * 0.45)
            g = np.clip(1 - dd, 0, 1) ** 2 * glow
            img += g[..., None] * np.array([110, 70, 25], np.float32)
        by = np.tile(BAYER, (w // 4 + 1, h // 4 + 1))[:w, :h]
        img = np.clip(np.floor(img / 6 + by[..., None] + 0.5) * 6, 0, 255).astype(np.uint8)
        if not hasattr(self, 'sky_surf') or self.sky_surf.get_size() != (w, h):
            self.sky_surf = pygame.Surface((w, h))
        pygame.surfarray.blit_array(self.sky_surf, img)
        return self.sky_surf

    def _tinted(self, name, surf, col):
        key = (name, tuple(int(v) // 4 for v in col))
        s = self.cache.get(key)
        if s is None:
            if len(self.cache) > 300:
                self.cache.clear()
            s = surf.copy()
            s.fill((int(col[0]), int(col[1]), int(col[2]), 255), special_flags=pygame.BLEND_RGBA_MULT)
            self.cache[key] = s
        return s

    def _cloud_surface(self, cl, lit, dark):
        key = (tuple(int(v) // 6 for v in lit), tuple(int(v) // 6 for v in dark))
        if cl['key'] != key:
            cl['key'] = key
            sh = cl['shade'][..., None]
            rgb = np.array(dark, np.float32) + (np.array(lit, np.float32) - np.array(dark, np.float32)) * np.clip(sh, 0, 1.3)
            by = np.tile(BAYER, (cl['w'] // 4 + 1, cl['h'] // 4 + 1))[:cl['w'], :cl['h']]
            rgb = np.clip(np.floor(rgb / 8 + by[..., None] + 0.5) * 8, 0, 255).astype(np.uint8)
            s = pygame.Surface((cl['w'], cl['h']), pygame.SRCALPHA)
            pygame.surfarray.pixels3d(s)[:] = rgb
            a = pygame.surfarray.pixels_alpha(s)
            a[:] = cl['alpha']
            del a
            cl['surf'] = s
        return cl['surf']

    # ------------------------------------------------------------ render
    def draw(self, surf, first):
        c = self.cur
        w, h, gy = self.w, self.h, self.ground_y
        day = getattr(self, 'day', 1.0)
        sky, amb, dusk, grey = self.palette()
        hour = self._hour()
        sr, ss = self.sun_times
        # sun / moon positions
        if sr - 0.8 <= hour <= ss + 0.8:
            f = (hour - sr) / max(0.1, ss - sr)
            sunx, suny = w * (0.08 + 0.84 * f), gy - math.sin(max(0.0, min(1.0, f)) * math.pi) * gy * 0.75 + gy * 0.05
        else:
            sunx, suny = -100, gy + 50
        glow = (0.35 + dusk * 0.9) * (1 - c['cloud'] * 0.85) if sunx > -50 else 0.0
        surf.blit(self._sky_surface(sky, (sunx, suny, glow)), (0, 0))
        # stars
        star_a = (1 - min(1.0, day / 0.35)) * (1 - min(1.0, c['cloud'] * 1.15)) * (1 - c['fog'])
        if star_a > 0.03:
            for x, y, tw, big in self.stars:
                b = star_a * (0.45 + 0.55 * math.sin(self.t * (1.5 + tw * 3) + tw * 40))
                if b > 0.08:
                    v = int(255 * b)
                    surf.fill((v, v, min(255, v + 20)), (int(x), int(y), 1 + big, 1))
            if self.shoot:
                x, y, life = self.shoot
                for i in range(10):
                    v = int(255 * life * (1 - i / 10))
                    surf.fill((v, v, v), (int(x + i * 3), int(y - i * 1.3), 1, 1))
        # sun
        if sunx > -50:
            r = max(3, h // 22)
            sc = _lerp((255, 245, 200), (255, 140, 60), dusk)
            k = max(0.0, 1 - c['cloud'] * 0.85 - c['fog'] * 0.6 - c['storm'] * 0.5 - c['rain'] * 0.3)
            if k > 0.08:
                pygame.draw.circle(surf, tuple(int(v * k + sky[1][i] * (1 - k)) for i, v in enumerate(sc)), (int(sunx), int(suny)), r)
            if c['cloud'] < 0.6 and day > 0.6 and k > 0.4:
                for i in range(8):
                    a = self.t * 0.15 + i * math.pi / 4
                    x1, y1 = sunx + math.cos(a) * r * 1.6, suny + math.sin(a) * r * 1.6
                    x2, y2 = sunx + math.cos(a) * r * 2.3, suny + math.sin(a) * r * 2.3
                    pygame.draw.line(surf, (255, 240, 180), (x1, y1), (x2, y2))
        # moon (real phase)
        if day < 0.6:
            if hour >= ss:
                f = (hour - ss) / max(0.1, 24 - ss + sr)
            else:
                f = (hour + 24 - ss) / max(0.1, 24 - ss + sr)
            mx, my = w * (0.12 + 0.76 * f), gy * (0.75 - 0.6 * math.sin(max(0, min(1, f)) * math.pi))
            self._moon(surf, int(mx), int(my), max(3, h // 26), (1 - day / 0.6) * (1 - c['cloud'] * 0.8))
        # clouds
        lit = _lerp(_lerp((70, 74, 96), (252, 252, 255), day), (255, 170, 130), dusk * 0.7)
        lit = _lerp(lit, _lerp((40, 42, 50), (150, 154, 164), day), min(1.0, c['rain'] * 0.8 + c['storm']))
        dark = _lerp(_lerp((22, 24, 40), (150, 160, 182), day), (140, 80, 110), dusk * 0.5)
        dark = _lerp(dark, _lerp((14, 15, 20), (80, 84, 94), day), min(1.0, c['rain'] * 0.8 + c['storm']))
        nightk = 1 - min(1.0, day * 2.5)
        dark = _lerp(dark, (60, 42, 40), nightk * 0.5)     # city light pollution on the cloud bellies
        lit = _lerp(lit, (90, 80, 96), nightk * 0.35)
        cover = min(1.0, c['cloud'] * 1.1 + c['storm'] * 0.3)
        if cover > 0.75:   # overcast deck
            deck = self._tinted('deck', self._deck(), dark)
            deck.set_alpha(int(255 * min(1.0, (cover - 0.75) * 4)))
            surf.blit(deck, (0, 0))
        for cl in self.clouds:
            if cl['thresh'] < cover:
                surf.blit(self._cloud_surface(cl, lit, dark), (int(cl['x']), int(cl['y'])))
        # lightning (behind the city)
        if self.bolts and self.flash > 0.2:
            for pts, depth in self.bolts:
                if len(pts) > 1:
                    col = (255, 255, 235) if depth == 0 else (190, 190, 255)
                    pygame.draw.lines(surf, col, False, pts, 2 if depth == 0 else 1)
        # landscape
        hor = sky[2]
        far_c = _lerp(_lerp((90, 120, 150), hor, 0.55), (0, 0, 0), 0) if day > 0 else hor
        far_c = tuple(far_c[i] * (0.35 + 0.65 * amb[i] / 255) for i in range(3))
        far_c = _lerp(far_c, hor, 0.45)
        city_c = tuple((58, 64, 82)[i] * amb[i] / 255 for i in range(3))
        city_c = _lerp(city_c, hor, 0.18 + c['fog'] * 0.5)
        near_c = tuple((26, 38, 30)[i] * (0.4 + 0.6 * amb[i] / 255) for i in range(3))
        if self.flash > 0.3:
            city_c = _lerp(city_c, (200, 200, 230), self.flash * 0.35)
            far_c = _lerp(far_c, (200, 200, 230), self.flash * 0.25)
        surf.blit(self._tinted('far', self.layer_surf['far'], far_c), (0, 0))
        if self.snow_cover > 0.02:
            e = self._tinted('efar', self.edge_surf['far'], (235, 240, 250))
            e.set_alpha(int(255 * self.snow_cover))
            surf.blit(e, (0, 0))
        surf.blit(self._tinted('city', self.layer_surf['city'], city_c), (0, 0))
        if day > 0.05:
            side = self.side_r if sunx > w / 2 or sunx < -50 else self.side_l
            k = int(255 * day * (1 - grey * 0.7))
            if k > 10:
                side.set_alpha(k)
                surf.blit(side, (0, 0))
            self.facade.set_alpha(int(255 * day))
            surf.blit(self.facade, (0, 0))
        if self.snow_cover > 0.02:
            e = self._tinted('ecity', self.edge_surf['city'], (230, 236, 248))
            e.set_alpha(int(255 * self.snow_cover))
            surf.blit(e, (0, 0))
        # windows & tower light at night
        night = max(0.0, 1 - day / 0.45)
        if night > 0.05:
            tt = int(self.t * 0.2)
            for i, (x, y, p, flick) in enumerate(self.windows):
                on = p < 0.55 + 0.25 * night and ((i * 7 + tt) % 23 != 0)
                if flick and int(self.t * 6 + i) % 9 == 0:
                    on = not on
                if on:
                    v = night * (0.6 + 0.4 * p)
                    surf.fill((int(255 * v), int(205 * v), int(120 * v)), (x, y, 1, 2))
        if int(self.t * 1.2) % 2:
            surf.fill((255, 40, 40), (self.tower_light[0], self.tower_light[1], 1, 1))
        # fog (in front of the city)
        if c['fog'] > 0.03 or c['rain'] > 0.6:
            fa = max(c['fog'], (c['rain'] - 0.6) * 0.6)
            fog = self.cache.get('fogsurf')
            if fog is None or fog.get_size() != (w, h):
                fog = pygame.Surface((w, h), pygame.SRCALPHA)
                self.cache['fogsurf'] = fog
            fog.fill((0, 0, 0, 0))
            fcol = _lerp(hor, (200, 204, 210), 0.4 * day)
            for i in range(12):
                yy = int(gy * (0.45 + i * 0.05) + math.sin(self.t * 0.25 + i * 1.7) * h * 0.02)
                xo = int(math.sin(self.t * 0.1 + i) * w * 0.05)
                fog.fill((int(fcol[0]), int(fcol[1]), int(fcol[2]), int(26 * fa)), (xo - 20, yy, w + 40, h // 7))
            surf.blit(fog, (0, 0))
        # near ground + trees + lamps
        surf.blit(self._tinted('near', self.layer_surf['near'], near_c), (0, 0))
        gc = tuple(int(min(255, near_c[i] * (1.6 + 0.5 * day))) for i in range(3))
        sway = int(round(math.sin(self.t * 2) * min(1.0, abs(c['wind']) / 8)))
        for x, y in self.tufts:
            surf.fill(gc, (x + sway * ((x // 2) % 2), y - 1, 1, 1))
        self._draw_trees(surf, near_c, amb)
        if self.snow_cover > 0.02:
            e = self._tinted('enear', self.edge_surf['near'], (240, 244, 252))
            e.set_alpha(int(255 * self.snow_cover))
            surf.blit(e, (0, 0))
            surf.fill(tuple(int(v * self.snow_cover * 0.5) for v in (200, 205, 215)), (0, gy + 3, w, h - gy),
                      special_flags=pygame.BLEND_RGB_ADD)
        lamp_on = day < 0.5 or (grey > 0.85 and day < 0.8)
        for lx, ly in self.lamps:
            ph = max(4, h // 14)
            surf.fill((20, 22, 26), (lx, ly - ph, 1, ph))
            surf.fill((20, 22, 26), (lx - 1, ly - ph, 3, 1))
            if lamp_on:
                surf.fill((255, 220, 150), (lx - 1, ly - ph + 1, 3, 1))
                g = self.lamp_glow
                surf.blit(g, (lx - g.get_width() // 2, ly - ph - g.get_height() // 2 + 2), special_flags=pygame.BLEND_RGB_ADD)
        # road
        ry = self.road_y
        road_c = tuple(int(v) for v in _lerp(_lerp((22, 24, 30), (70, 72, 78), day), (200, 205, 215), self.snow_cover * 0.6))
        surf.fill(road_c, (0, ry, w, 4))
        lane = tuple(min(255, int(v * 1.8) + 30) for v in road_c)
        for x in range(0, w, 8):
            surf.fill(lane, (x, ry + 2, 4, 1))
        # wet ground: rippling reflection of the scene + lamp streaks
        if self.wet > 0.05:
            self._reflection(surf, lamp_on)
        self._draw_cars(surf, day, lamp_on)
        # precipitation
        self._draw_rain(surf, day)
        self._draw_snow(surf)
        self._draw_leaves(surf, amb)
        if self.birds:
            d, bx, by, flock = self.birds
            for ox, oy, ph in flock:
                x, y = int(bx + ox * d * -1), int(by + oy)
                up = int(math.sin(self.t * 9 + ph) > 0)
                col = (30, 30, 40)
                surf.fill(col, (x, y, 1, 1))
                surf.fill(col, (x - 1, y - up, 1, 1))
                surf.fill(col, (x + 1, y - up, 1, 1))
        # lightning flash
        if self.flash > 0.02:
            v = int(150 * self.flash)
            surf.fill((v, v, v + 15), (0, 0, w, gy), special_flags=pygame.BLEND_RGB_ADD)
        # frost / heat tint
        if c['temp'] < 0:
            k = int(min(1.0, -c['temp'] / 10) * 18)
            surf.fill((0, k // 2, k), special_flags=pygame.BLEND_RGB_ADD)
        if self.prm.get('widget', True):
            self._widget(surf)

    def _deck(self):
        d = self.cache.get('deck_src')
        if d is None:
            w, gy = self.w, self.ground_y
            d = pygame.Surface((w, int(gy * 0.5)), pygame.SRCALPHA)
            arr = np.zeros((w, int(gy * 0.5)), np.float32)
            g = np.random.default_rng(3)
            for i in range(30):
                cx, cy, r = g.uniform(0, w), g.uniform(0, gy * 0.3), g.uniform(w * 0.05, w * 0.15)
                X, Y = np.meshgrid(np.arange(w), np.arange(arr.shape[1]), indexing='ij')
                arr += np.exp(-(((X - cx) / r) ** 2 + ((Y - cy) / (r * 0.4)) ** 2))
            a = np.clip(arr * 255, 0, 255)
            a[:, :int(gy * 0.15)] = 255
            pygame.surfarray.pixels3d(d)[:] = 255
            al = pygame.surfarray.pixels_alpha(d)
            al[:] = (a * np.linspace(1, 0.0, arr.shape[1])[None, :] ** 0.5).astype(np.uint8)
            del al
            self.cache['deck_src'] = d
        return d

    def _moon(self, surf, cx, cy, r, alpha):
        if alpha < 0.05:
            return
        p = moon_phase()
        key = ('moon', r, round(p, 2), round(alpha, 1))
        s = self.cache.get(key)
        if s is None:
            y, x = np.mgrid[-r:r + 1, -r:r + 1].astype(np.float32)
            disc = x * x + y * y <= r * r
            xn, yn = x / r, y / r
            term = np.cos(2 * math.pi * p) * np.sqrt(np.clip(1 - yn * yn, 0, 1))
            lit = (xn > term) if p < 0.5 else (xn < -term)
            s = pygame.Surface((2 * r + 1, 2 * r + 1), pygame.SRCALPHA)
            rgb = np.zeros((2 * r + 1, 2 * r + 1, 3), np.uint8)
            rgb[...] = (40, 44, 60)
            rgb[lit.T] = (235, 232, 205)
            crater = ((x - r * 0.3) ** 2 + (y + r * 0.2) ** 2 < (r * 0.25) ** 2) | ((x + r * 0.35) ** 2 + (y - r * 0.35) ** 2 < (r * 0.18) ** 2)
            rgb[(crater & lit).T] = (200, 196, 172)
            pygame.surfarray.pixels3d(s)[:] = rgb
            a = pygame.surfarray.pixels_alpha(s)
            a[:] = (disc.T * 255 * alpha * np.where(lit.T, 1.0, 0.35)).astype(np.uint8)
            del a
            self.cache[key] = s
        hk = ('moonhalo', r, round(alpha, 1))
        halo = self.cache.get(hk)
        if halo is None:
            halo = pygame.Surface((r * 8, r * 8))
            halo.fill((0, 0, 0))
            for i in range(4 * r, r, -1):
                v = int(26 * alpha * (1 - i / (4 * r)) ** 2)
                pygame.draw.circle(halo, (v, v, v + v // 4), (4 * r, 4 * r), i)
            self.cache[hk] = halo
        surf.blit(halo, (cx - 4 * r, cy - 4 * r), special_flags=pygame.BLEND_RGB_ADD)
        surf.blit(s, (cx - r, cy - r))

    def _draw_trees(self, surf, near_c, amb):
        sea = season(getattr(self, 'lat_used', 52))
        wind = self.cur['wind']
        palettes = {'spring': [(250, 170, 200), (120, 190, 90), (240, 200, 220)],
                    'summer': [(40, 120, 50), (60, 150, 60), (30, 100, 45)],
                    'autumn': [(220, 120, 30), (190, 70, 30), (230, 180, 60), (140, 90, 40)],
                    'winter': []}
        cols = palettes[sea]
        trunk_c = tuple(int(v) for v in near_c)
        for tr in self.trees:
            x, gy, size = tr['x'], tr['gy'], tr['size']
            sway = math.sin(self.t * (1.2 + abs(wind) * 0.15) + tr['phase']) * min(3.0, 0.4 + abs(wind) * 0.25)
            surf.fill(trunk_c, (x, gy - size, tr['trunk'], size))
            if not cols:
                for i in range(4):
                    a = -math.pi / 2 + (i - 1.5) * 0.5
                    pygame.draw.line(surf, trunk_c, (x, gy - size), (x + math.cos(a) * size * 0.8 + sway, gy - size + math.sin(a) * size * 0.8))
                if self.snow_cover > 0.2:
                    surf.fill((230, 235, 245), (x - size // 2 + int(sway), gy - size - size // 2, size, 1))
                continue
            for j, (bx, by, br) in enumerate(tr['blobs']):
                col = cols[(j + int(tr['hue'] * 10)) % len(cols)]
                lightk = 0.6 + 0.4 * (1 - (by + size * 0.55) / (size * 0.9))   # higher blobs catch more light
                col = tuple(int(min(255, col[i] * lightk * (0.22 + 0.78 * amb[i] / 255))) for i in range(3))
                px, py = int(x + bx + sway * (1 - by / size)), int(gy - size * 1.3 + by)
                pygame.draw.circle(surf, col, (px, py), int(br))
                if br >= 3:
                    hl = tuple(min(255, int(v * 1.25)) for v in col)
                    surf.fill(hl, (px - int(br * 0.4), py - int(br * 0.6), max(1, int(br * 0.5)), 1))
            if self.snow_cover > 0.2:
                pygame.draw.arc(surf, (235, 240, 250), (x - size * 0.7 + sway, gy - size * 1.9, size * 1.4, size), 0.3, 2.8, 1)

    def _reflection(self, surf, lamp_on):
        w, h, gy = self.w, self.h, self.ground_y
        band = h - gy - 3
        if band < 3:
            return
        src = surf.subsurface((0, gy - band, w, band)).copy()
        src = pygame.transform.flip(src, False, True)
        src.fill((150, 150, 170), special_flags=pygame.BLEND_RGB_MULT)
        rain = self.cur['rain']
        refl = pygame.Surface((w, band))
        refl.fill((0, 0, 0))
        for y in range(band):
            dx = int(math.sin(self.t * 6 + y * 1.3) * (0.5 + rain * 2.5) * (y / band + 0.3))
            refl.blit(src, (dx, y), (0, y, w, 1))
        refl.set_alpha(int(150 * self.wet))
        surf.blit(refl, (0, gy + 3))
        if lamp_on:
            for lx, ly in self.lamps:
                for y in range(gy + 4, h, 2):
                    k = 1 - (y - gy) / (h - gy)
                    dx = int(math.sin(self.t * 5 + y) * 1.5)
                    v = int(90 * k * self.wet)
                    surf.fill((v, int(v * 0.8), int(v * 0.4)), (lx + dx - 1, y, 3, 1), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_cars(self, surf, day, lights):
        ry = self.road_y
        for x, d, sp, col, bus in self.cars:
            L = 11 if bus else 7
            xi = int(x) - (L if d > 0 else 0)
            body = tuple(int(col[i] * (0.3 + 0.7 * day)) for i in range(3))
            if bus:
                surf.fill(body, (xi, ry - 4, L, 4))
                for wx in range(xi + 1, xi + L - 1, 2):
                    surf.fill((255, 220, 140) if lights else (150, 190, 220), (wx, ry - 3, 1, 1))
            else:
                surf.fill(body, (xi, ry - 2, L, 2))
                surf.fill(body, (xi + 2, ry - 3, L - 4, 1))
                surf.fill((150, 190, 220) if not lights else (60, 60, 70), (xi + 3, ry - 3, 1, 1))
            surf.fill((10, 10, 10), (xi + 1, ry, 1, 1))
            surf.fill((10, 10, 10), (xi + L - 2, ry, 1, 1))
            front = xi + L if d > 0 else xi - 1
            back = xi - 1 if d > 0 else xi + L
            if lights:
                surf.fill((255, 250, 210), (front, ry - 2, 1, 1))
                surf.fill((255, 40, 30), (back, ry - 2, 1, 1))
                # headlight beam
                for i in range(1, 14):
                    v = int(70 * (1 - i / 14))
                    surf.fill((v, v, int(v * 0.8)), (front + d * i, ry - 2 + i // 6, 1, 1 + i // 5), special_flags=pygame.BLEND_RGB_ADD)
                if self.wet > 0.2:
                    for i in range(1, 5):
                        surf.fill((60, 15, 10), (back, ry + i, 1, 1), special_flags=pygame.BLEND_RGB_ADD)
            if self.cur['rain'] > 0.3 and random.random() < 0.5:
                surf.fill((170, 180, 200), (back - d * random.randint(1, 4), ry - random.randint(1, 3), 1, 1))

    def _draw_rain(self, surf, day):
        n = int(len(self.rx) * self.cur['rain'])
        if n <= 0 and not len(self.splash):
            return
        w, h = self.w, self.h
        arr = pygame.surfarray.pixels3d(surf)
        if n > 0:
            z = self.rz[:n]
            x = self.rx[:n]
            y = self.ry[:n]
            base = (np.array([120, 135, 165], np.float32) if day > 0.3 else np.array([70, 80, 110], np.float32))
            col = (base[None, :] * (0.45 + 0.75 * z[:, None])).clip(0, 255).astype(np.uint8)
            length = (2 + z * 7).astype(np.int32)
            slant = self.cur['wind'] * 0.06
            for seg in range(9):
                m = length > seg
                xx = (x[m] - slant * seg).astype(np.int32)
                yy = (y[m] - seg).astype(np.int32)
                ok = (xx >= 0) & (xx < w) & (yy >= 0) & (yy < h)
                arr[xx[ok], yy[ok]] = col[m][ok]
        if len(self.splash):
            xs = self.splash[:, 0].astype(np.int32)
            ys = self.splash[:, 1].astype(np.int32)
            ok = (xs >= 1) & (xs < w - 1) & (ys >= 0) & (ys < h)
            for dx in (-1, 1):
                arr[xs[ok] + dx, ys[ok]] = (170, 180, 205)
        del arr

    def _draw_snow(self, surf):
        n = int(len(self.sx) * self.cur['snow'])
        if n <= 0:
            return
        w, h = self.w, self.h
        arr = pygame.surfarray.pixels3d(surf)
        x = self.sx[:n].astype(np.int32) % w
        y = self.sy[:n].astype(np.int32)
        z = self.sz[:n]
        ok = (y >= 0) & (y < h - 1)
        v = (170 + z * 85).astype(np.uint8)
        col = np.stack([v, v, np.minimum(255, v.astype(np.int32) + 10).astype(np.uint8)], 1)
        arr[x[ok], y[ok]] = col[ok]
        big = ok & (z > 0.7) & (x < w - 1)
        arr[x[big] + 1, y[big]] = col[big]
        arr[x[big], y[big] + 1] = col[big]
        arr[x[big] + 1, y[big] + 1] = col[big]
        del arr

    def _draw_leaves(self, surf, amb):
        if season(getattr(self, 'lat_used', 52)) != 'autumn' or abs(self.cur['wind']) < 1.5 or self.cur['snow'] > 0.2:
            return
        cols = [(220, 120, 30), (190, 70, 30), (230, 180, 60), (150, 90, 40)]
        n = int(min(len(self.lx), 10 + abs(self.cur['wind']) * 4))
        for i in range(n):
            c = cols[self.lc[i]]
            c = tuple(int(c[j] * (0.3 + 0.7 * amb[j] / 255)) for j in range(3))
            flip = int(math.sin(self.t * 6 + self.lp[i]) > 0)
            surf.fill(c, (int(self.lx[i]), int(self.ly[i]), 2 - flip, 1 + flip))

    def _widget(self, surf):
        info = self.info
        if not info:
            return
        w = self.w
        lines = [info['place'][:18]]
        t = info.get('temp')
        lines.append(('%d°C ' % round(t) if isinstance(t, (int, float)) else '') + info['text'][:16])
        arrows = '>'
        lines.append('WIND %d KM/H' % round(info.get('wind', 0)))
        if info.get('humidity') is not None:
            lines.append('HUM %d%%' % round(info['humidity']))
        lines.append('LIVE' if info.get('live') else ('SIM' if self.sim else 'OFFLINE'))
        pw = max(len(l) for l in lines) * 4 + 22
        ph = len(lines) * 7 + 6
        x0, y0 = w - pw - 4, 4
        panel = self.cache.get(('panel', pw, ph))
        if panel is None:
            panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
            panel.fill((0, 0, 0, 120))
            pygame.draw.rect(panel, (255, 255, 255, 60), (0, 0, pw, ph), 1)
            self.cache[('panel', pw, ph)] = panel
        surf.blit(panel, (x0, y0))
        self._icon(surf, x0 + 3, y0 + 4, info.get('code', 0))
        for i, l in enumerate(lines):
            tiny_text(surf, x0 + 18, y0 + 3 + i * 7, l, (235, 240, 255) if i else (255, 220, 120))
        # wind arrow
        a = math.radians((info.get('wind_dir', 270) + 180) % 360)
        cx, cy = x0 + 8, y0 + 22
        ex, ey = cx + math.sin(a) * 5, cy - math.cos(a) * 5
        pygame.draw.line(surf, (160, 220, 255), (cx, cy), (ex, ey))
        surf.fill((255, 255, 255), (int(ex), int(ey), 1, 1))
        del arrows

    def _icon(self, surf, x, y, code):
        t = self.t
        night = getattr(self, 'day', 1) < 0.3
        if code in (0, 1):
            if night:
                pygame.draw.circle(surf, (235, 232, 205), (x + 5, y + 5), 4)
                pygame.draw.circle(surf, (0, 0, 0), (x + 7, y + 3), 3)
            else:
                pygame.draw.circle(surf, (255, 210, 60), (x + 5, y + 5), 3)
                for i in range(8):
                    a = t + i * math.pi / 4
                    surf.fill((255, 210, 60), (x + 5 + int(math.cos(a) * 5), y + 5 + int(math.sin(a) * 5), 1, 1))
            return
        cloud = (220, 225, 235) if code < 95 else (120, 125, 140)
        if code == 2:
            pygame.draw.circle(surf, (255, 210, 60), (x + 7, y + 3), 3)
        pygame.draw.circle(surf, cloud, (x + 4, y + 6), 3)
        pygame.draw.circle(surf, cloud, (x + 7, y + 5), 3)
        surf.fill(cloud, (x + 2, y + 6, 8, 3))
        if 51 <= code <= 67 or 80 <= code <= 82 or code >= 95:
            for i in range(3):
                yy = y + 10 + int((t * 8 + i * 2) % 4)
                surf.fill((120, 170, 255), (x + 3 + i * 3, yy, 1, 2))
        if 71 <= code <= 77 or code in (85, 86):
            for i in range(3):
                yy = y + 10 + int((t * 3 + i * 2) % 4)
                surf.fill((255, 255, 255), (x + 3 + i * 3, yy, 1, 1))
        if code >= 95 and int(t * 3) % 3 == 0:
            pygame.draw.lines(surf, (255, 240, 120), False, [(x + 6, y + 8), (x + 4, y + 11), (x + 7, y + 11), (x + 5, y + 14)])
        if code in (45, 48):
            for i in range(3):
                surf.fill((200, 200, 210), (x + 1 + (i % 2) * 2, y + 10 + i * 2, 8, 1))
