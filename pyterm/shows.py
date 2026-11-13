"""Shows - full-window celebration / atmosphere effects that run on top of everything and never touch the
keyboard (unlike alarms, nothing is dismissed and several can run at once).

Built in:
  fireworks   a scripted display: peony, chrysanthemum, willow, ring, heart, crossette, palm, strobe, spiral,
              saturn and two-colour shells with trails, flashes, mortar thumps and a finale barrage
  confetti    cannons left and right plus a paper rain (fluttering, spinning)
  lightning   a thunderstorm: forked bolts, flickering flashes, thunder and a darker sky
  meteors     a shower of streaks that burn up in sparks at the bottom
  lasers      a club: sweeping coloured beams, haze and a strobing beat
  shockwave   rings rolling out from the cursor, with a thump and a shake

Start one from ...
  the demo shell      show fireworks style=willow duration=15 palette=gold     (show stop)
  a theme             events:  success: fireworks       fail: lightning        bell: shockwave ...
  Home Assistant      a button per show; or publish "fireworks style=heart" to  pyterm/<id>/set/show
  a plugin            app.trigger_show('confetti', duration=6, intensity=2)

Options every show understands: duration (seconds), intensity (0.2 .. 4, default 1), palette (a name from
PALETTES or "#ff0000,#00ff00" or "theme"), sound (true/false); fireworks also takes style=NAME|mix and
finale=true/false.  Write your own:

    from pyterm.shows import Show

    class Rain(Show):
        duration = 8
        label = 'Pink rain'              # Home Assistant button "Show Pink rain"
        def start(self): ...
        def step(self, dt): ...          # called every frame
        def draw(self, surf, app): ...   # virtual pixel surface, on top of the terminal

    def register(api):
        api.register_show('pinkrain', Rain)
"""
from __future__ import annotations

import math
import random

import numpy as np
import pygame

from . import particles as P

ADD = pygame.BLEND_RGB_ADD
SHOWS = {}

PALETTES = {
    'classic': [(255, 70, 70), (80, 255, 120), (90, 160, 255), (255, 220, 60), (255, 90, 255), (255, 255, 255)],
    'gold': [(255, 200, 60), (255, 160, 30), (255, 235, 150), (255, 255, 255)],
    'ice': [(120, 200, 255), (200, 240, 255), (255, 255, 255), (90, 140, 255)],
    'neon': [(255, 0, 200), (0, 255, 220), (190, 255, 0), (150, 80, 255)],
    'pastel': [(255, 170, 200), (170, 220, 255), (200, 255, 190), (255, 240, 170), (220, 190, 255)],
    'fire': [(255, 60, 20), (255, 140, 20), (255, 210, 60), (255, 255, 200)],
    'rainbow': [(255, 60, 60), (255, 160, 30), (250, 240, 60), (60, 230, 90), (60, 160, 255), (170, 90, 255)],
    'mono': [(255, 255, 255), (200, 210, 230)],
}


def palette_of(app, spec):
    """'gold' | '#f00,#0f0' | 'theme' | list of rgb -> list of rgb tuples"""
    if isinstance(spec, (list, tuple)) and spec and isinstance(spec[0], (list, tuple)):
        return [tuple(c[:3]) for c in spec]
    if not spec:
        return PALETTES['classic']
    spec = str(spec).strip()
    if spec == 'theme':
        try:
            from . import themes
            pal = app.theme['palette']
            cols = [themes.hex2rgb(pal[i]) for i in (1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14)]
            return [c for c in cols if max(c) > 60] or PALETTES['classic']
        except Exception:
            return PALETTES['classic']
    if spec in PALETTES:
        return PALETTES[spec]
    out = []
    for part in spec.replace(' ', ',').split(','):
        part = part.strip()
        if part in PALETTES:
            out += PALETTES[part]
        elif part.startswith('#') and len(part) in (4, 7):
            h = part[1:]
            if len(h) == 3:
                h = ''.join(c * 2 for c in h)
            out.append(tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)))
    return out or PALETTES['classic']


def _coerce(v):
    if isinstance(v, str):
        low = v.lower()
        if low in ('true', 'yes', 'on'):
            return True
        if low in ('false', 'no', 'off'):
            return False
        try:
            return float(v) if ('.' in v or 'e' in low) else int(v)
        except ValueError:
            return v
    return v


def parse(spec):
    """'fireworks style=willow duration=15'  |  {'show': 'fireworks', 'style': 'willow'}  |  '{"show": ...}' (json)
    -> (name, {options})"""
    import json
    if isinstance(spec, str) and spec.strip().startswith('{'):
        try:
            spec = json.loads(spec)
        except ValueError:
            pass
    if isinstance(spec, dict):
        d = dict(spec)
        name = str(d.pop('show', d.pop('name', '')))
        return name, {k: _coerce(v) for k, v in d.items()}
    parts = str(spec).split()
    if not parts:
        return '', {}
    opts = {}
    for p in parts[1:]:
        if '=' in p:
            k, v = p.split('=', 1)
            opts[k.strip()] = _coerce(v.strip())
    return parts[0], opts


def specs(value):
    """a theme `events:` value (string, dict or list of them) -> list of (name, opts)"""
    if not value:
        return []
    if isinstance(value, (str, dict)):
        value = [value]
    out = []
    for v in value:
        name, opts = parse(v)
        if name:
            out.append((name, opts))
    return out


def register(name):
    def deco(cls):
        cls.name = name
        SHOWS[name] = cls
        return cls
    return deco


class Show:
    name = 'base'
    duration = 8.0
    label = None              # Home Assistant button name ("Show <label>"), default: the registered name
    ha_icon = 'mdi:party-popper'

    def __init__(self, app, duration=None, intensity=1.0, palette=None, sound=True, **opts):
        self.app = app
        self.t = 0.0
        self.done = False
        self.duration = float(duration) if duration else self.duration
        self.intensity = max(0.1, min(6.0, float(intensity or 1.0)))
        self.pal = palette_of(app, palette)
        self.sound = bool(sound) and app.sound.ok and app.cfg.get('sound') is not False
        self.opts = opts
        self.W, self.H = app.vw, app.vh
        self.k = max(0.5, self.H / 240.0)
        self._layer = None
        self.start()

    # ---- override
    def start(self):
        pass

    def step(self, dt):
        pass

    def draw(self, surf, app):
        pass

    def retrigger(self, opts):
        """the same show was started again while running: default = restart it"""
        self.t = 0.0
        self.start()

    # ---- machinery
    def update(self, dt):
        self.t += dt
        self.W, self.H = self.app.vw, self.app.vh
        self.k = max(0.5, self.H / 240.0)
        self.step(dt)
        if self.t >= self.duration:
            self.done = True

    def stop(self):
        self.done = True

    @property
    def fade(self):
        """0..1..0 envelope over the show (quick in, slow out)"""
        return max(0.0, min(1.0, self.t / 0.4, (self.duration - self.t) / 1.0))

    def color(self):
        return random.choice(self.pal)

    def voff(self):
        return self.app.fx.voff * self.app.font.ch

    def emit(self, n, x, y, **kw):
        """particles in terminal space; on big windows every spark is a small 2x2 blob (4 copies)"""
        pr = self.app.fx.particles
        y = y + self.voff()
        b = 2 if self.H >= 420 else 1
        got = 0
        for dx in range(b):
            for dy in range(b):
                got = pr.emit(n, x + dx, y + dy, **kw)
        return got

    def snd(self, kind, vol=1.0, gap=0.04):
        if self.sound:
            self.app.sound.play(kind, min_gap=gap, vol=vol)

    def layer(self, surf):
        """black scratch surface of the same size, to be blitted back additively"""
        if self._layer is None or self._layer.get_size() != surf.get_size():
            self._layer = pygame.Surface(surf.get_size()).convert()
        self._layer.fill((0, 0, 0))
        return self._layer

    def glow(self, surf, x, y, radius, col, amount=1.0):
        """soft additive blob"""
        radius = int(radius)
        if radius < 2 or amount <= 0.02:
            return
        key = ('glow', radius)
        g = _GLOWS.get(key)
        if g is None:
            if len(_GLOWS) > 80:
                _GLOWS.clear()
            n = 2 * radius
            yy, xx = np.mgrid[-radius:radius, -radius:radius].astype(np.float32)
            d = np.sqrt(xx * xx + yy * yy) / radius
            a = np.clip(1.0 - d, 0, 1) ** 2
            g = pygame.Surface((n, n)).convert()
            pygame.surfarray.blit_array(g, np.repeat((a * 255).astype(np.uint8).T[:, :, None], 3, 2))
            _GLOWS[key] = g
        t = g.copy()
        t.fill(tuple(int(c * min(1.0, amount)) for c in col[:3]), special_flags=pygame.BLEND_RGB_MULT)
        surf.blit(t, (int(x) - radius, int(y) - radius), special_flags=ADD)


_GLOWS = {}


# ====================================================================================== fireworks
STYLES = ('peony', 'chrysanthemum', 'willow', 'ring', 'heart', 'crossette', 'palm', 'strobe', 'spiral', 'saturn',
          'double')


@register('fireworks')
class Fireworks(Show):
    duration = 12.0
    label = 'Fireworks'
    ha_icon = 'mdi:firework'

    def start(self):
        self.style = str(self.opts.get('style') or 'mix')
        if self.style != 'mix' and self.style not in STYLES:
            self.style = 'mix'
        self.finale = self.opts.get('finale', True) is not False
        self.shells = []
        self.comets = []
        self.flares = []         # [x, y, age, life, rgb, radius]
        self.later = []          # [time, fn]
        self.queue = []          # launch times
        self._schedule(0.0, self.duration)

    def _schedule(self, t0, t1):
        body = t1 - (2.4 if self.finale and t1 - t0 > 5 else 0.0)
        n = max(1, int((body - t0) * 1.15 * self.intensity))
        ts = sorted(t0 + 0.15 + (body - t0 - 0.6) * (i + random.uniform(-0.3, 0.3)) / max(1, n) for i in range(n))
        self.queue += [max(t0, t) for t in ts]
        if self.finale and t1 - t0 > 5:
            m = int(9 * self.intensity)
            self.queue += [body + 0.2 * i + random.uniform(0, 0.12) for i in range(m + 3)]
            self.queue += [body + 0.25 + 0.38 * i for i in range(3)]       # the big ones at the end
        self.queue.sort()

    def retrigger(self, opts):
        """more fireworks while a show is running: extend it instead of restarting"""
        extra = float(opts.get('duration') or 6.0)
        self.intensity = max(self.intensity, float(opts.get('intensity') or 1.0))
        self._schedule(self.t, self.t + extra)
        self.duration = max(self.duration, self.t + extra)
        self.done = False

    def _launch(self, big=False):
        W, H, k = self.W, self.H, self.k
        x = random.uniform(0.12, 0.88) * W
        top = random.uniform(0.12, 0.45) * H
        # ballistic: reach `top` at the apex
        g = 150 * k
        vy = -math.sqrt(2 * g * max(10, H - top))
        fuse = -vy / g
        vx = (random.uniform(0.15, 0.85) * W - x) / fuse * 0.4
        style = self.style if self.style != 'mix' else random.choice(STYLES)
        self.shells.append({'x': x, 'y': H + 2, 'vx': vx, 'vy': vy, 'g': g, 'fuse': fuse, 'style': style,
                            'big': big, 'col': self.color(), 'col2': self.color()})
        self.snd('whoosh', 0.25, 0.06)

    def step(self, dt):
        while self.queue and self.queue[0] <= self.t:
            big = self.finale and self.queue[0] > self.duration - 1.4
            self.queue.pop(0)
            self._launch(big)
        for item in [l for l in self.later if l[0] <= self.t]:
            self.later.remove(item)
            item[1]()
        keep = []
        for s in self.shells:
            s['x'] += s['vx'] * dt
            s['y'] += s['vy'] * dt
            s['vy'] += s['g'] * dt
            s['fuse'] -= dt
            self.emit(3, s['x'] + np.random.uniform(-.6, .6, 3).astype(np.float32) * self.k, s['y'],
                      vy=np.random.uniform(10, 50, 3).astype(np.float32) * self.k,
                      vx=np.random.uniform(-12, 12, 3).astype(np.float32), life=np.random.uniform(.25, .6, 3).astype(np.float32),
                      col=(255, 205, 120), pal=P.FADE, add=True, grav=40 * self.k)
            if s['fuse'] <= 0:
                self._explode(s)
            else:
                keep.append(s)
        self.shells = keep
        ck = []
        for c in self.comets:
            c['x'] += c['vx'] * dt
            c['y'] += c['vy'] * dt
            c['vx'] *= (1 - c['drag'] * dt)
            c['vy'] = c['vy'] * (1 - c['drag'] * dt) + c['g'] * dt
            c['life'] -= dt
            self.emit(2, c['x'], c['y'], vx=np.random.uniform(-8, 8, 2).astype(np.float32),
                      vy=np.random.uniform(-8, 8, 2).astype(np.float32),
                      life=np.random.uniform(.25, .5, 2).astype(np.float32), col=c['col'], pal=P.FADE, add=True,
                      grav=30 * self.k)
            if c['life'] <= 0:
                if c.get('split'):
                    self._burst(c['x'], c['y'], 'peony', c['col'], c['col'], 0.35, n=44, life=0.9)
                else:
                    self._burst(c['x'], c['y'], 'strobe', c['col'], c['col'], 0.25, n=30, life=1.2)
            else:
                ck.append(c)
        self.comets = ck
        self.flares = [f for f in self.flares if f[2] < f[3]]
        for f in self.flares:
            f[2] += dt

    # ---- bursts
    def _explode(self, s):
        x, y, big = s['x'], s['y'], s['big']
        scale = (1.35 if big else 1.0) * random.uniform(0.85, 1.15)
        self._burst(x, y, s['style'], s['col'], s['col2'], scale)
        self.snd('boom', 0.2 + 0.2 * (1 if big else 0), 0.05)
        self.later.append([self.t + 0.12, lambda: self.snd('break', 0.45, 0.05)])
        self.flares.append([x, y, 0.0, 0.35 if big else 0.25, (255, 240, 220) if random.random() < .5 else s['col'],
                            (60 if big else 38) * self.k])
        if big:
            self.app.post.flash = max(self.app.post.flash, 0.12)
            self.app.post.flash_rgb = s['col']
            self.app.shake = max(self.app.shake, 0.05)

    def _burst(self, x, y, style, c1, c2, scale=1.0, n=None, life=None):
        k = self.k * scale
        base = 120 * k
        two = np.float32(6.2831853)

        def emit(n, ang, sp, col, life, grav=70, drag=1.4, pal=P.FADE, delay=0.0):
            vx = (np.cos(ang) * sp).astype(np.float32)
            vy = (np.sin(ang) * sp).astype(np.float32)
            self.emit(n, np.float32(x), np.float32(y), vx=vx, vy=vy, life=life, col=col, pal=pal, add=True,
                      grav=grav * self.k, drag=drag, delay=delay)

        def rnd(a, b, m):
            return np.random.uniform(a, b, m).astype(np.float32)

        if style == 'peony':
            m = n or 380
            emit(m, rnd(0, two, m), base * rnd(.86, 1.0, m), c1, rnd(.9, 1.5, m) if life is None else life)
        elif style == 'chrysanthemum':
            m = n or 180
            ang = rnd(0, two, m)
            sp = base * rnd(.82, 1.0, m)
            for i, d in enumerate((0.0, 0.07, 0.14, 0.21)):      # same path, born later -> a streak behind each spark
                emit(m, ang, sp, c1, 1.3 - i * 0.12, delay=d, pal=P.FADE)
        elif style == 'willow':
            m = n or 170
            ang = rnd(0, two, m)
            sp = base * 0.8 * rnd(.5, 1.0, m)
            gold = (255, 190, 70)
            for i, d in enumerate((0.0, 0.1, 0.2, 0.3, 0.4)):
                emit(m, ang, sp, gold, 2.8 - i * 0.2, grav=62, drag=1.5, delay=d)
            emit(m // 2, ang[:m // 2], sp[:m // 2], (255, 255, 235), 3.0, grav=62, drag=1.5, pal=P.SPARKLE)
        elif style == 'ring':
            m = n or 70
            ang = np.linspace(0, two, m, endpoint=False).astype(np.float32)
            tilt = random.uniform(0.25, 1.0)
            rot = random.uniform(0, 3.14)
            vx0 = np.cos(ang) * base
            vy0 = np.sin(ang) * base * tilt
            vx = vx0 * math.cos(rot) - vy0 * math.sin(rot)
            vy = vx0 * math.sin(rot) + vy0 * math.cos(rot)
            self.emit(m, np.float32(x), np.float32(y), vx=vx.astype(np.float32), vy=vy.astype(np.float32),
                      life=1.5, col=c1, pal=P.FADE, add=True, grav=35 * self.k, drag=1.3)
            if random.random() < 0.5:
                self.emit(m // 2, np.float32(x), np.float32(y), vx=vx[::2].astype(np.float32) * 0.5,
                          vy=vy[::2].astype(np.float32) * 0.5, life=1.3, col=c2, pal=P.FADE, add=True,
                          grav=35 * self.k, drag=1.3)
        elif style == 'heart':
            m = n or 90
            t = np.linspace(0, math.tau, m, endpoint=False).astype(np.float32)
            hx = 16 * np.sin(t) ** 3
            hy = -(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t))
            f = base / 16 * 0.95
            self.emit(m, np.float32(x), np.float32(y), vx=(hx * f).astype(np.float32), vy=(hy * f).astype(np.float32),
                      life=1.7, col=(255, 70, 120), pal=P.FADE, add=True, grav=14 * self.k, drag=1.25)
            self.emit(m // 3, np.float32(x), np.float32(y), vx=(hx[::3] * f * .5).astype(np.float32),
                      vy=(hy[::3] * f * .5).astype(np.float32), life=1.4, col=(255, 200, 220), pal=P.FADE, add=True,
                      grav=14 * self.k, drag=1.25)
        elif style == 'crossette':
            for i in range(8):
                a = i / 8 * math.tau + random.uniform(-.1, .1)
                self.comets.append({'x': x, 'y': y, 'vx': math.cos(a) * base * .9, 'vy': math.sin(a) * base * .9,
                                    'g': 40 * self.k, 'drag': 1.5, 'life': random.uniform(.55, .75), 'col': c1,
                                    'split': True})
        elif style == 'palm':
            for i in range(7):
                a = -math.pi / 2 + (i - 3) * 0.42 + random.uniform(-.08, .08)
                self.comets.append({'x': x, 'y': y, 'vx': math.cos(a) * base * 1.25, 'vy': math.sin(a) * base * 1.25,
                                    'g': 80 * self.k, 'drag': 0.7, 'life': random.uniform(1.0, 1.3),
                                    'col': (255, 200, 90) if i % 2 else c1})
            emit(60, rnd(0, two, 60), base * .3 * rnd(.4, 1, 60), (255, 230, 180), 1.0)
        elif style == 'strobe':
            m = n or 230
            emit(m, rnd(0, two, m), base * rnd(.3, 1.0, m), (255, 255, 255) if life is None else c1,
                 (rnd(1.4, 2.4, m) if life is None else life), grav=40, drag=1.7, pal=P.SPARKLE)
        elif style == 'spiral':
            m = n or 200
            arms = random.choice((2, 3, 4))
            i = np.arange(m, dtype=np.float32)
            delay = (i / m * 0.55).astype(np.float32)
            ang = (i % arms) / arms * math.tau + delay * 9.0
            emit(m, ang.astype(np.float32), base * .75 * np.ones(m, np.float32), c1, 1.3, delay=delay, drag=1.0)
        elif style == 'saturn':
            m = 90
            emit(m, rnd(0, two, m), base * .55 * rnd(.6, 1, m), c1, 1.3)
            ang = np.linspace(0, two, 80, endpoint=False).astype(np.float32)
            self.emit(80, np.float32(x), np.float32(y), vx=(np.cos(ang) * base * 1.2).astype(np.float32),
                      vy=(np.sin(ang) * base * 0.25).astype(np.float32), life=1.5, col=c2, pal=P.FADE, add=True,
                      grav=25 * self.k, drag=1.3)
        else:                                        # double: inner and outer colour
            m = n or 230
            ang = rnd(0, two, m)
            emit(m, ang, base * rnd(.9, 1.0, m), c1, 1.4)
            emit(m // 2, rnd(0, two, m // 2), base * .5 * rnd(.8, 1.0, m // 2), c2, 1.3, pal=P.SPARKLE)

    def draw(self, surf, app):
        if not self.flares:
            return
        lay = self.layer(surf)
        for x, y, age, life, rgb, r in self.flares:
            q = 1 - age / life
            self.glow(lay, x, y, r * (1.0 + (1 - q) * 1.4), rgb, q * q * 0.9)
        surf.blit(lay, (0, 0), special_flags=ADD)


# ====================================================================================== confetti
@register('confetti')
class Confetti(Show):
    duration = 8.0
    label = 'Confetti'
    ha_icon = 'mdi:party-popper'

    def start(self):
        self.n = 0
        cap = 900
        self.x = np.zeros(cap, np.float32)
        self.y = np.zeros(cap, np.float32)
        self.vx = np.zeros(cap, np.float32)
        self.vy = np.zeros(cap, np.float32)
        self.ph = np.zeros(cap, np.float32)
        self.col = np.zeros((cap, 3), np.uint8)
        self.sz = np.ones(cap, np.int32)
        self.cap = cap
        self.next_cannon = 0.0
        self.rain = 0.0
        self.snd('boom', 0.25)

    def _spawn(self, n, x, y, vx, vy):
        n = min(n, self.cap - self.n)
        if n <= 0:
            return
        a, b = self.n, self.n + n
        self.x[a:b], self.y[a:b] = x, y
        self.vx[a:b], self.vy[a:b] = vx, vy
        self.ph[a:b] = np.random.uniform(0, 6.28, n)
        self.col[a:b] = [random.choice(self.pal) if random.random() < .8 else (255, 255, 255) for _ in range(n)] \
            if len(self.pal) < 6 else [random.choice(self.pal) for _ in range(n)]
        self.sz[a:b] = np.random.randint(2, 5, n) * max(1, int(self.k * 0.8 + .5))
        self.n = b

    def step(self, dt):
        W, H, k = self.W, self.H, self.k
        if self.t >= self.next_cannon and self.t < self.duration - 2.0:
            self.next_cannon = self.t + 2.4 / self.intensity
            for side in (0, 1):
                n = int(110 * self.intensity)
                ang = np.radians(np.random.uniform(-82, -52, n)) if side == 0 else np.radians(np.random.uniform(-128, -98, n))
                sp = np.random.uniform(250, 620, n) * k
                self._spawn(n, 0 if side == 0 else W, H, np.cos(ang) * sp, np.sin(ang) * sp)
            self.snd('break', 0.5, 0.2)
        if self.t < self.duration - 2.0:
            self.rain += dt * 60 * self.intensity
            n = int(self.rain)
            self.rain -= n
            self._spawn(n, np.random.uniform(0, W, n), -4, np.random.uniform(-20, 20, n), np.random.uniform(10, 60, n) * k)
        m = self.n
        if m:
            self.ph[:m] += dt * 9
            self.vx[:m] *= 1 - min(1, 1.6 * dt)
            self.vy[:m] = self.vy[:m] * (1 - min(1, 2.2 * dt)) + 70 * k * 2.2 * dt
            self.x[:m] += (self.vx[:m] + np.sin(self.ph[:m]) * 26 * k) * dt
            self.y[:m] += self.vy[:m] * dt
            alive = self.y[:m] < H + 6
            if not alive.all():
                idx = np.nonzero(alive)[0]
                c = len(idx)
                for arr in (self.x, self.y, self.vx, self.vy, self.ph, self.sz):
                    arr[:c] = arr[idx]
                self.col[:c] = self.col[idx]
                self.n = c

    def draw(self, surf, app):
        for i in range(self.n):
            s = int(self.sz[i])
            w = max(1, int(s * abs(math.cos(self.ph[i]))))        # tumbling
            surf.fill(self.col[i], (int(self.x[i]), int(self.y[i]), w, s))

    @property
    def fade(self):
        return 1.0


# ====================================================================================== lightning
def _bolt(x0, y0, x1, y1, spread, depth=0, out=None):
    out = [] if out is None else out
    pts = [(x0, y0), (x1, y1)]
    for it in range(6):
        nxt = [pts[0]]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            mx = (ax + bx) / 2 + random.uniform(-spread, spread)
            my = (ay + by) / 2 + random.uniform(-spread, spread) * 0.3
            nxt += [(mx, my), (bx, by)]
        pts = nxt
        spread *= 0.55
    out.append((pts, depth))
    if depth < 2:
        for _ in range(random.randint(1, 3 - depth)):
            i = random.randint(len(pts) // 5, 4 * len(pts) // 5)
            bx, by = pts[i]
            ang = math.pi / 2 + random.uniform(-.9, .9)
            ln = (y1 - by) * random.uniform(.25, .6)
            _bolt(bx, by, bx + math.cos(ang) * ln, by + math.sin(ang) * ln, spread * 3, depth + 1, out)
    return out


@register('lightning')
class Lightning(Show):
    duration = 8.0
    label = 'Lightning storm'
    ha_icon = 'mdi:weather-lightning'

    def start(self):
        self.bolt = None
        self.age = 9.0
        self.flash = 0.0
        self.next = 0.3
        self.thunder = []
        self.col = self.pal[0] if self.opts.get('palette') else (200, 215, 255)

    def step(self, dt):
        self.age += dt
        self.flash = max(0.0, self.flash - dt * 3.5)
        if self.t >= self.next and self.t < self.duration - 1.2:
            self.next = self.t + random.uniform(0.7, 2.0) / self.intensity
            self._strike()
        for th in [x for x in self.thunder if x <= self.t]:
            self.thunder.remove(th)
            self.snd('boom', 0.6, 0.2)
            self.app.shake = max(self.app.shake, 0.18)
        if self.bolt and self.age > 0.35:
            self.bolt = None

    def _strike(self):
        W, H = self.W, self.H
        x0 = random.uniform(0.1, 0.9) * W
        x1 = x0 + random.uniform(-0.25, 0.25) * W
        self.bolt = _bolt(x0, -4, x1, random.uniform(0.7, 1.0) * H, H * 0.09)
        self.age = 0.0
        self.flash = 1.0
        self.thunder.append(self.t + random.uniform(0.15, 0.5))
        self.snd('break', 0.6, 0.1)

    def draw(self, surf, app):
        f = self.fade
        dark = int(34 * f)
        if dark:
            surf.fill((dark, dark, dark), special_flags=pygame.BLEND_RGB_SUB)
        flick = 1.0 if self.age < 0.08 else (0.3 if self.age < 0.14 else (1.0 if self.age < 0.2 else max(0.0, 1 - (self.age - 0.2) / 0.15)))
        if self.bolt and flick > 0:
            lay = self.layer(surf)
            w = max(1, int(self.k * 1.6))
            for pts, depth in self.bolt:
                q = 1.0 - depth * 0.3
                for width, mul in ((w * 4, 0.16), (w * 2, 0.4), (max(1, w // (1 + depth)), 1.0)):
                    c = tuple(int(min(255, ch * mul * q * flick)) for ch in (self.col if mul < 1 else (255, 255, 255)))
                    pygame.draw.lines(lay, c, False, pts, width)
            surf.blit(lay, (0, 0), special_flags=ADD)
        v = int(70 * self.flash * flick * min(1.0, self.intensity))
        if v > 2:
            surf.fill((int(v * self.col[0] / 255), int(v * self.col[1] / 255), int(v * self.col[2] / 255)), special_flags=ADD)


# ====================================================================================== meteors
@register('meteors')
class Meteors(Show):
    duration = 9.0
    label = 'Meteor shower'
    ha_icon = 'mdi:shooting-star'

    def start(self):
        self.m = []
        self.acc = 0.0
        self.dir = random.choice((-1, 1))

    def step(self, dt):
        W, H, k = self.W, self.H, self.k
        if self.t < self.duration - 2.0:
            self.acc += dt * 3.2 * self.intensity
            while self.acc >= 1:
                self.acc -= 1
                a = math.radians(random.uniform(52, 72))
                sp = random.uniform(380, 760) * k
                x = random.uniform(-0.1, 1.0) * W + (0.35 * W if self.dir < 0 else 0)
                self.m.append({'x': x, 'y': -10.0, 'vx': -self.dir * math.cos(a) * sp, 'vy': math.sin(a) * sp,
                               'len': random.uniform(0.05, 0.14), 'col': random.choice(self.pal) if self.opts.get('palette')
                               else random.choice(((255, 245, 220), (200, 230, 255), (255, 190, 120))),
                               'w': random.choice((1, 1, 2))})
                if random.random() < 0.3:
                    self.snd('whoosh', 0.12, 0.2)
        keep = []
        for s in self.m:
            s['x'] += s['vx'] * dt
            s['y'] += s['vy'] * dt
            if s['y'] > H * 0.97 or s['x'] < -20 or s['x'] > W + 20:
                if s['y'] > H * 0.9:
                    n = 24
                    self.emit(n, np.float32(s['x']), np.float32(H - 2), vx=np.random.uniform(-70, 70, n).astype(np.float32) * k,
                              vy=np.random.uniform(-150, -30, n).astype(np.float32) * k,
                              life=np.random.uniform(.3, .8, n).astype(np.float32), col=s['col'], pal=P.FIRE, add=True,
                              grav=260 * k, drag=0.8)
                    self.snd('break', 0.18, 0.1)
            else:
                keep.append(s)
        self.m = keep

    def draw(self, surf, app):
        lay = self.layer(surf)
        for s in self.m:
            dx, dy = s['vx'] * s['len'], s['vy'] * s['len']
            steps = 9
            for i in range(steps):
                q = 1 - i / steps
                c = tuple(int(ch * q * q) for ch in s['col'])
                pygame.draw.line(lay, c, (s['x'] - dx * i / steps, s['y'] - dy * i / steps),
                                 (s['x'] - dx * (i + 1) / steps, s['y'] - dy * (i + 1) / steps), max(1, int(s['w'] * self.k * q + .5)))
            self.glow(lay, s['x'], s['y'], 5 * self.k, s['col'], 0.8)
        surf.blit(lay, (0, 0), special_flags=ADD)


# ====================================================================================== lasers
@register('lasers')
class Lasers(Show):
    duration = 10.0
    label = 'Laser show'
    ha_icon = 'mdi:laser-pointer'

    def start(self):
        self.n = int(5 + 2 * min(3, self.intensity))
        self.ph = [random.uniform(0, 6.28) for _ in range(self.n)]
        self.bpm = 124.0
        self.beat = 0
        self.strobe = 0.0
        self.snd('whoosh', 0.3)

    def step(self, dt):
        b = int(self.t * self.bpm / 60)
        if b != self.beat:
            self.beat = b
            self.strobe = 1.0
            if b % 4 == 0:
                self.snd('boom', 0.25, 0.2)
        self.strobe = max(0.0, self.strobe - dt * 5)

    def draw(self, surf, app):
        W, H, k = self.W, self.H, self.k
        f = self.fade
        lay = self.layer(surf)
        reach = math.hypot(W, H)
        for i in range(self.n):
            from_top = i % 2
            ox = (i + 0.5) / self.n * W
            oy = -2 if from_top else H + 2
            swing = math.sin(self.t * (0.9 + i * 0.13) + self.ph[i]) * 0.9
            ang = (math.pi / 2 if from_top else -math.pi / 2) + swing + (0.4 * math.sin(self.t * 0.5 + i) if i % 3 == 0 else 0)
            c = self.pal[(i + self.beat // 4) % len(self.pal)] if self.opts.get('palette') else \
                tuple(int(127 + 127 * math.sin(self.t * 0.7 + i * 1.3 + p)) for p in (0, 2.09, 4.18))
            ex, ey = ox + math.cos(ang) * reach, oy + math.sin(ang) * reach
            on = 0.55 + 0.45 * self.strobe if (self.beat + i) % 2 == 0 else 0.45
            on *= f
            for w, mul in ((int(k * 5), 0.10), (int(k * 2.5), 0.30), (max(1, int(k)), 1.0)):
                col = tuple(int(ch * mul * on) for ch in (c if mul < 1 else (255, 255, 255)) )
                pygame.draw.line(lay, col, (ox, oy), (ex, ey), max(1, w))
        surf.blit(lay, (0, 0), special_flags=ADD)
        v = int(40 * self.strobe * f)
        if v > 3:
            surf.fill((v, v, v), special_flags=ADD)


# ====================================================================================== shockwave
@register('shockwave')
class Shockwave(Show):
    duration = 3.0
    label = 'Shockwave'
    ha_icon = 'mdi:radar'

    def start(self):
        from . import signals
        cx = signals.cursor_x if signals.cursor_x is not None else self.W / 2
        cy = signals.cursor_y if signals.cursor_y is not None else self.H / 2
        self.c = (cx, cy)
        self.rings = [0.0, -0.18, -0.36]
        self.app.shake = max(self.app.shake, 0.35)
        self.app.post.flash = max(self.app.post.flash, 0.25)
        self.app.post.flash_rgb = self.pal[0]
        self.snd('boom', 0.7)
        n = int(120 * self.intensity)
        ang = np.random.uniform(0, 6.283, n).astype(np.float32)
        sp = np.random.uniform(40, 260, n).astype(np.float32) * self.k
        self.emit(n, np.float32(cx), np.float32(cy), vx=np.cos(ang) * sp, vy=np.sin(ang) * sp,
                  life=np.random.uniform(.4, 1.2, n).astype(np.float32), col=self.pal[0], pal=P.FADE, add=True, drag=2.0)

    def step(self, dt):
        self.rings = [r + dt for r in self.rings]

    def draw(self, surf, app):
        lay = self.layer(surf)
        reach = math.hypot(self.W, self.H)
        for i, r in enumerate(self.rings):
            if r <= 0 or r > 2.2:
                continue
            q = r / 2.2
            rad = int(reach * (1 - (1 - q) ** 2))
            if rad < 2:
                continue
            a = (1 - q) ** 1.5
            c = tuple(int(ch * a) for ch in self.pal[i % len(self.pal)])
            pygame.draw.circle(lay, c, (int(self.c[0]), int(self.c[1])), rad, max(1, int(self.k * (4 - 3 * q))))
            pygame.draw.circle(lay, tuple(ch // 4 for ch in c), (int(self.c[0]), int(self.c[1])), rad, max(2, int(self.k * 9 * (1 - q))))
        surf.blit(lay, (0, 0), special_flags=ADD)
