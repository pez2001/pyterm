"""Alarms - sound + full-window display effect, triggered from Home Assistant (MQTT), the demo shell
(`alarm redalert Washing machine done`) or a plugin (app.trigger_alarm('doorbell', 'Someone is at the door')).

Built in:
  redalert   rotating red beacons, pulsing red screen edges, a klaxon, big ALERT card
  warning    yellow/black hazard tape crawling around the border, an urgent beep-beep
  doorbell   a friendly ding-dong, a bell swinging on a card that slides in
  timer      an old alarm clock shaking and ringing like crazy
  calm       a soft blue breathing glow and gentle rising tones (wake-up / reminder)

Any key or mouse click dismisses an alarm (the key is not passed to the program); it also stops by
itself after `duration` seconds. Alarms ring even when the theme's key sounds are off - only a
missing audio device or --no-sound keeps them silent.

Write your own:

    from pixelterm.alarms import Alarm

    class Party(Alarm):
        duration = 10
        color = (255, 0, 255)
        def sound(self, snd):                    # -> (pygame Sound, repeat seconds) or None
            ...
        def draw(self, surf, app):               # virtual pixel surface, after everything else
            ...

    def register(api):
        api.register_alarm('party', Party)
"""
from __future__ import annotations

import math
import time

import numpy as np
import pygame

ADD = pygame.BLEND_RGB_ADD


class Alarm:
    name = 'base'
    duration = 30.0
    color = (255, 60, 60)
    title = 'ALERT'
    label = None              # Home Assistant button name ("Alarm <label>"), default: the registered name
    ha_icon = 'mdi:alarm-light'

    def __init__(self, app, message='', duration=None, sound=True):
        self.app = app
        self.message = (message or '').strip()
        self.t = 0.0
        self.done = False
        self.dismissed = False
        self.duration = float(duration) if duration else self.duration
        self.snd = None
        self.repeat = 0.0
        self.next_sound = 0.0
        if sound and app.sound.ok and not app.cfg.get('sound') is False:
            try:
                r = self.sound(app.sound)
                if r:
                    self.snd, self.repeat = r
            except Exception as e:
                print('[pixelterm] alarm sound: %s' % e)
        self.start()

    # ---- override
    def start(self):
        pass

    def sound(self, snd):
        return None

    def draw(self, surf, app):
        pass

    # ---- machinery
    def update(self, dt):
        self.t += dt
        if self.snd is not None and self.t >= self.next_sound:
            ch = pygame.mixer.find_channel(True)
            if ch:
                ch.set_volume(max(0.35, self.app.sound.volume))
                ch.play(self.snd)
            self.next_sound = self.t + (self.repeat or 1e9)
        if self.t >= self.duration:
            self.stop()

    def stop(self, dismissed=False):
        if self.done:
            return
        self.done = True
        self.dismissed = dismissed
        if self.snd is not None:
            self.snd.stop()

    # ---- helpers for subclasses
    def big(self, app, text, color, k=2, shadow=True):
        """text in the terminal font, scaled up k times (blocky), with a hard drop shadow"""
        cw, ch = app.font.cw, app.font.ch
        s = pygame.Surface((len(text) * cw + 1, ch + 1), pygame.SRCALPHA)
        if shadow:
            app.draw_text(s, 1, 1, text, (0, 0, 0))
        app.draw_text(s, 0, 0, text, color)
        return pygame.transform.scale(s, (s.get_width() * k, s.get_height() * k))

    def card(self, surf, app, title, color, y=None, icon=None, alpha=220, k=None):
        """centred message card: big blocky title, the (wrapped) message, a blinking hint and an optional
        icon(surf, x, y, size) drawn in a column on the left"""
        cw, ch = app.font.cw, app.font.ch
        W, H = surf.get_size()
        k = k or max(2, min(3, W // (cw * (len(title) + 10) * 2) + 1))
        ts = self.big(app, title, color, k)
        lines = _wrap(self.message, max(16, min(48, W // cw - 16)))[:4]
        hint = 'press any key'
        pad = cw * 2
        isz = ch * 3 if icon else 0
        tw = max([ts.get_width()] + [len(x) * cw for x in lines + [hint]])
        w = tw + pad * 2 + (isz + pad if icon else 0)
        h = pad + ts.get_height() + ch // 2 + len(lines) * ch + ch * 2 + pad // 2
        h = max(h, isz + pad * 2)
        x = (W - w) // 2
        y = (H - h) // 2 if y is None else y
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((8, 6, 12, alpha))
        surf.blit(panel, (x, y))
        lw = max(1, ch // 8)
        glow = 0.6 + 0.4 * math.sin(self.t * 6)
        pygame.draw.rect(surf, tuple(int(c * glow) for c in color), (x - lw * 2, y - lw * 2, w + lw * 4, h + lw * 4), lw)
        pygame.draw.rect(surf, color, (x, y, w, h), lw)
        tx = x + pad + (isz + pad if icon else 0)
        cx = tx + tw // 2
        if icon:
            icon(surf, x + pad, y + (h - isz) // 2, isz)
        yy = y + pad
        surf.blit(ts, (cx - ts.get_width() // 2, yy))
        yy += ts.get_height() + ch // 2
        for line in lines:
            app.draw_text(surf, cx - len(line) * cw // 2, yy, line, (255, 255, 255))
            yy += ch
        if int(self.t * 2) % 2 == 0:
            app.draw_text(surf, cx - len(hint) * cw // 2, yy + ch // 2, hint, (140, 140, 155))
        return pygame.Rect(x, y, w, h)

    def edge(self, surf, color, width, k=1.0):
        """soft additive glow along the window edges (cached gradient, scaled by k)"""
        W, H = surf.get_size()
        key = (W, H, width, color)
        g = _EDGE.get(key)
        if g is None:
            _EDGE.clear()
            x = np.minimum(np.arange(W), np.arange(W)[::-1])[:, None]
            y = np.minimum(np.arange(H), np.arange(H)[::-1])[None, :]
            d = np.minimum(x, y).astype(np.float32)
            a = np.clip(1 - d / width, 0, 1) ** 2
            g = pygame.Surface((W, H))
            pygame.surfarray.blit_array(g, (a[..., None] * np.array(color, np.float32)).astype(np.uint8))
            _EDGE[key] = g
        if k >= 0.99:
            surf.blit(g, (0, 0), special_flags=ADD)
        elif k > 0.01:
            c = g.copy()
            v = int(255 * k)
            c.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
            surf.blit(c, (0, 0), special_flags=ADD)

    @staticmethod
    def tint(surf, rgb):
        """multiply the whole picture (rgb 0..255 per channel) - darken / color-grade what's behind"""
        surf.fill(rgb, special_flags=pygame.BLEND_RGB_MULT)


_EDGE = {}


def _wrap(text, n):
    out, line = [], ''
    for w in (text or '').split():
        while len(w) > n:
            if line:
                out.append(line)
                line = ''
            out.append(w[:n])
            w = w[n:]
        if line and len(line) + 1 + len(w) > n:
            out.append(line)
            line = w
        else:
            line = (line + ' ' + w).strip()
    if line:
        out.append(line)
    return out


def _env(n, a=0.01, r=0.05, sr=44100):
    e = np.ones(n)
    na, nr = min(int(a * sr), n // 2), min(int(r * sr), n // 2)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] = np.linspace(1, 0, nr)
    return e


def _tone(f, dur, wave='sine', sr=44100, vol=1.0):
    t = np.arange(int(sr * dur)) / sr
    if wave == 'square':
        s = np.sign(np.sin(2 * np.pi * f * t))
    elif wave == 'saw':
        s = 2 * ((t * f) % 1) - 1
    else:
        s = np.sin(2 * np.pi * f * t)
    return s * _env(len(t)) * vol


# ============================================================================ red alert
class RedAlert(Alarm):
    label = 'red alert'
    ha_icon = 'mdi:alarm-light'
    name = 'redalert'
    duration = 30.0
    color = (255, 50, 40)

    def sound(self, snd):
        sr = 44100
        t = np.arange(int(sr * 1.4)) / sr
        f = 520 + 380 * np.abs(np.sin(np.pi * t / 1.4))           # whooping klaxon sweep
        ph = 2 * np.pi * np.cumsum(f) / sr
        s = (np.sign(np.sin(ph)) * 0.5 + np.sin(ph * 2) * 0.3) * _env(len(t), 0.02, 0.1)
        return snd._mk(s, 0.9), 1.6

    def draw(self, surf, app):
        W, H = surf.get_size()
        on = 0.5 + 0.5 * math.sin(self.t * 7)
        # grade everything red and darker, pulsing with the klaxon
        self.tint(surf, (int(170 + 70 * on), int(40 + 30 * on), int(36 + 26 * on)))
        self.edge(surf, (255, 30, 16), max(12, min(W, H) // 6), 0.35 + 0.65 * on)
        # rotating beacon on top: two light cones swept around
        r = max(6, min(W, H) // 28)
        bx, by = W // 2, r + 2
        beams = pygame.Surface((W, H))
        beams.fill((0, 0, 0))
        L = math.hypot(W, H)
        for k in (0, math.pi):
            a = self.t * 4.5 + k
            for spread, col in ((0.30, (60, 8, 4)), (0.16, (110, 18, 8)), (0.06, (160, 40, 20))):
                pygame.draw.polygon(beams, col, [(bx, by), (bx + math.cos(a - spread) * L, by + math.sin(a - spread) * L),
                                                 (bx + math.cos(a + spread) * L, by + math.sin(a + spread) * L)])
        surf.blit(beams, (0, 0), special_flags=ADD)
        pygame.draw.rect(surf, (40, 40, 48), (bx - r * 2, 0, r * 4, r // 2 + 2))            # base
        pygame.draw.circle(surf, (200, 20, 10), (bx, by), r)
        pygame.draw.circle(surf, (255, 120, 90), (bx - r // 3, by - r // 3), max(1, r // 3))
        flash = abs(math.cos(self.t * 4.5))
        pygame.draw.circle(surf, (int(255 * flash), int(200 * flash), int(170 * flash)), (bx, by), max(1, r // 2))
        self.card(surf, app, 'RED ALERT', (255, 70, 50), icon=_icon_siren(self.t))


# ============================================================================ warning (hazard tape)
class Warning(Alarm):
    label = 'warning'
    ha_icon = 'mdi:alert'
    name = 'warning'
    duration = 20.0
    color = (255, 210, 40)

    def sound(self, snd):
        s = np.concatenate([_tone(1800, 0.12, 'square'), np.zeros(4410), _tone(1800, 0.12, 'square'), np.zeros(26000)])
        return snd._mk(s, 0.6), 0.9

    def draw(self, surf, app):
        W, H = surf.get_size()
        self.tint(surf, (170, 160, 140))
        band = max(8, min(W, H) // 16)
        stripe = band
        key = (W, H, band)
        if getattr(self, '_tk', None) != key:              # long tape strip, scrolled every frame
            self._tk = key
            n = W + H + stripe * 4
            t = pygame.Surface((n, band))
            t.fill((255, 200, 0))
            for x in range(-band, n, stripe * 2):
                pygame.draw.polygon(t, (24, 22, 20), [(x, 0), (x + stripe, 0), (x + stripe - band, band), (x - band, band)])
            t.fill((255, 235, 120), (0, 0, n, max(1, band // 10)))
            t.fill((120, 90, 0), (0, band - max(1, band // 10), n, max(1, band // 10)))
            self._tape = t
        off = int(self.t * band * 2) % (stripe * 2)
        t = self._tape
        surf.blit(t, (0, 0), (off, 0, W, band))
        surf.blit(t, (0, H - band), (stripe * 2 - off, 0, W, band))
        side = pygame.transform.rotate(t.subsurface((0, 0, H + stripe * 2, band)), 90)
        surf.blit(side, (0, 0), (0, off, band, H))
        surf.blit(side, (W - band, 0), (0, stripe * 2 - off, band, H))
        blink = int(self.t * 3) % 2 == 0
        for cx in (band // 2, W - band // 2):              # flashing amber lamps in the corners
            for cy in (band // 2, H - band // 2):
                pygame.draw.circle(surf, (255, 170, 0) if blink else (90, 50, 0), (cx, cy), band // 2 + 1)
        self.card(surf, app, 'WARNING', (255, 205, 30), icon=_icon_hazard(self.t))


# ============================================================================ doorbell
class Doorbell(Alarm):
    label = 'doorbell'
    ha_icon = 'mdi:doorbell'
    name = 'doorbell'
    duration = 8.0
    color = (120, 200, 255)

    def sound(self, snd):
        sr = 44100
        ding = sum(np.sin(2 * np.pi * 660 * h * np.arange(int(sr * 1.2)) / sr) * a for h, a in ((1, 1), (2.76, 0.3), (5.4, 0.1)))
        dong = sum(np.sin(2 * np.pi * 523 * h * np.arange(int(sr * 1.6)) / sr) * a for h, a in ((1, 1), (2.76, 0.3), (5.4, 0.1)))
        ding *= np.exp(-np.arange(len(ding)) / sr * 3)
        dong *= np.exp(-np.arange(len(dong)) / sr * 2.5)
        s = np.concatenate([ding[:int(sr * 0.45)], dong])
        return snd._mk(s, 0.8), 99

    def draw(self, surf, app):
        W, H = surf.get_size()
        ch = app.font.ch
        slide = min(1.0, self.t / 0.45)
        e = 1 - (1 - slide) ** 3 + math.sin(slide * math.pi) * 0.08          # ease out with a small bounce
        self.edge(surf, (40, 110, 200), max(10, min(W, H) // 8), 0.5 + 0.3 * math.sin(self.t * 3))
        y0 = -ch * 10
        self.card(surf, app, 'DING DONG', (120, 200, 255), y=int(y0 + (ch * 3 - y0) * e), icon=_icon_bell(self.t))


# ============================================================================ timer (alarm clock)
class Timer(Alarm):
    label = 'timer'
    ha_icon = 'mdi:timer-alert'
    name = 'timer'
    duration = 30.0
    color = (255, 140, 60)

    def sound(self, snd):
        sr = 44100
        ring = np.concatenate([_tone(2600 if i % 2 else 2300, 0.035, 'square') for i in range(40)] + [np.zeros(int(sr * 0.4))])
        return snd._mk(ring, 0.55), 1.8

    def draw(self, surf, app):
        W, H = surf.get_size()
        self.tint(surf, (190, 180, 170))
        ringing = (self.t % 1.8) < 1.4
        self.edge(surf, (255, 120, 30), max(10, min(W, H) // 8), 0.8 if ringing else 0.25)
        r = max(14, min(W, H) // 8)
        rect = self.card(surf, app, 'TIME IS UP', (255, 150, 60), y=H // 2 - r // 2)
        _clock(surf, W // 2, rect.top - int(r * 1.45), r, self.t, ringing)


# ============================================================================ calm
class Calm(Alarm):
    label = 'calm reminder'
    ha_icon = 'mdi:bell-ring-outline'
    name = 'calm'
    duration = 20.0
    color = (100, 170, 255)

    def sound(self, snd):
        sr = 44100
        notes = [523.25, 659.25, 783.99, 1046.5]
        parts = []
        for f in notes:
            n = int(sr * 0.9)
            t = np.arange(n) / sr
            parts.append(np.sin(2 * np.pi * f * t) * np.exp(-t * 3) * 0.8 + np.sin(4 * np.pi * f * t) * np.exp(-t * 5) * 0.2)
        s = np.zeros(int(sr * 3.2))
        for i, p in enumerate(parts):
            st = int(i * sr * 0.45)
            s[st:st + len(p)] += p
        return snd._mk(s, 0.5), 4.5

    def draw(self, surf, app):
        W, H = surf.get_size()
        b = 0.5 + 0.5 * math.sin(self.t * 1.3)
        fade = min(1.0, self.t / 1.5)
        v = int(255 - 60 * fade)
        self.tint(surf, (int(v * 0.86), int(v * 0.93), v))
        self.edge(surf, (40, 110, 255), max(16, min(W, H) // 4), (0.35 + 0.65 * b) * fade)
        self.card(surf, app, 'REMINDER', (130, 190, 255), alpha=185, icon=_icon_moon(self.t))



# ---------------------------------------------------------------------------- card icons: f(surf, x, y, size)
def _icon_siren(t):
    def f(s, x, y, n):
        cx = x + n // 2
        on = int(t * 6) % 2
        pygame.draw.rect(s, (60, 60, 70), (x + n // 8, y + n * 3 // 4, n * 3 // 4, n // 6))
        pygame.draw.ellipse(s, (255, 40, 30) if on else (120, 10, 10), (x + n // 5, y + n // 6, n * 3 // 5, n * 3 // 4))
        s.fill((60, 60, 70), (x + n // 5, y + n * 9 // 16, n * 3 // 5, n // 5))
        pygame.draw.circle(s, (255, 200, 180), (cx - n // 9, y + n // 3), max(1, n // 12))
        if on:
            for a in (-0.9, -0.45, 0, 0.45, 0.9):
                ang = a - math.pi / 2
                pygame.draw.line(s, (255, 120, 90), (cx + math.cos(ang) * n * 0.48, y + n * 0.45 + math.sin(ang) * n * 0.48),
                                 (cx + math.cos(ang) * n * 0.62, y + n * 0.45 + math.sin(ang) * n * 0.62), max(1, n // 16))
    return f


def _icon_hazard(t):
    def f(s, x, y, n):
        pts = [(x + n // 2, y + n // 10), (x + n - 1, y + n - n // 10), (x, y + n - n // 10)]
        pygame.draw.polygon(s, (24, 22, 20), [(px, py + 2) for px, py in pts])
        pygame.draw.polygon(s, (255, 205, 30), pts)
        lw = max(2, n // 9)
        s.fill((24, 22, 20), (x + n // 2 - lw // 2, y + n * 7 // 20, lw, n * 3 // 10))
        s.fill((24, 22, 20), (x + n // 2 - lw // 2, y + n * 3 // 4, lw, lw))
    return f


def _icon_bell(t):
    def f(s, x, y, n):
        a = math.sin(t * 14) * 0.45 * max(0.0, 1 - t / 2.2)
        cx, cy = x + n / 2, y + n * 0.12

        def rot(px, py):
            dx, dy = px - cx, py - cy
            return cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)
        prof = [(-0.08, 0.05), (-0.22, 0.15), (-0.28, 0.4), (-0.32, 0.62), (-0.44, 0.74),
                (0.44, 0.74), (0.32, 0.62), (0.28, 0.4), (0.22, 0.15), (0.08, 0.05)]
        pts = [rot(cx + px * n, cy + py * n) for px, py in prof]
        pygame.draw.polygon(s, (190, 130, 30), [(px + 1, py + 1) for px, py in pts])
        pygame.draw.polygon(s, (255, 205, 70), pts)
        pygame.draw.line(s, (255, 245, 190), rot(cx - n * 0.18, cy + n * 0.2), rot(cx - n * 0.24, cy + n * 0.55), max(1, n // 14))
        pygame.draw.circle(s, (230, 160, 40), [int(v) for v in rot(cx + math.sin(a * 2) * n * 0.12, cy + n * 0.82)], max(2, n // 9))
        pygame.draw.circle(s, (200, 200, 210), (int(cx), int(cy)), max(1, n // 16))
    return f


def _icon_moon(t):
    def f(s, x, y, n):
        cx, cy, r = x + n // 2, y + n // 2, n * 2 // 5
        pygame.draw.circle(s, (230, 235, 255), (cx, cy), r)
        pygame.draw.circle(s, (8, 6, 12), (cx + r // 2, cy - r // 3), r)
        for i, (sx, sy) in enumerate(((0.85, 0.15), (0.95, 0.55), (0.7, 0.85))):
            tw = 0.5 + 0.5 * math.sin(t * 3 + i * 2)
            v = int(120 + 135 * tw)
            px, py = int(x + sx * n), int(y + sy * n)
            s.fill((v, v, 255), (px, py, max(1, n // 20), max(1, n // 20)))
    return f


def _clock(surf, cx, cy, r, t, ringing):
    shake = math.sin(t * 55) * r * 0.07 if ringing else 0.0
    tilt = math.sin(t * 55) * 0.08 if ringing else 0.0
    cx += int(shake)
    hit = math.sin(t * 55) > 0
    for sgn in (-1, 1):                                                    # bells + hammer
        bxy = (int(cx + sgn * r * 0.72 + math.sin(tilt) * r), int(cy - r * 0.82))
        pygame.draw.circle(surf, (120, 120, 130), (bxy[0] + 1, bxy[1] + 1), int(r * 0.36))
        pygame.draw.circle(surf, (225, 225, 235), bxy, int(r * 0.36))
        pygame.draw.circle(surf, (255, 255, 255), (bxy[0] - r // 9, bxy[1] - r // 9), max(1, r // 12))
    hx = cx + (r * 0.22 if hit else -r * 0.22) * (1 if ringing else 0)
    pygame.draw.line(surf, (70, 70, 80), (cx, cy - r * 0.95), (hx, cy - r * 1.18), max(2, r // 9))
    pygame.draw.circle(surf, (70, 70, 80), (int(hx), int(cy - r * 1.18)), max(2, r // 8))
    for sgn in (-1, 1):                                                    # feet
        pygame.draw.line(surf, (70, 70, 80), (cx + sgn * r * 0.55, cy + r * 0.8), (cx + sgn * r * 0.85, cy + r * 1.15), max(2, r // 7))
    pygame.draw.circle(surf, (110, 20, 20), (cx + 2, cy + 2), r)
    pygame.draw.circle(surf, (215, 50, 40), (cx, cy), r)
    pygame.draw.circle(surf, (255, 140, 120), (cx - r // 3, cy - r // 2), max(1, r // 8))
    pygame.draw.circle(surf, (250, 248, 236), (cx, cy), int(r * 0.8))
    for i in range(12):
        a = i * math.pi / 6
        d = max(1, r // 14) * (2 if i % 3 == 0 else 1)
        surf.fill((40, 40, 40), (int(cx + math.cos(a) * r * 0.68) - d // 2, int(cy + math.sin(a) * r * 0.68) - d // 2, d, d))
    now = time.localtime()
    for frac, ln, w in ((((now.tm_hour % 12) + now.tm_min / 60) / 12, 0.42, max(2, r // 9)),
                        (now.tm_min / 60, 0.62, max(1, r // 13)), (now.tm_sec / 60, 0.66, 1)):
        ang = frac * math.tau - math.pi / 2
        col = (200, 30, 30) if ln == 0.66 else (30, 30, 30)
        pygame.draw.line(surf, col, (cx, cy), (cx + math.cos(ang) * r * ln, cy + math.sin(ang) * r * ln), w)
    pygame.draw.circle(surf, (30, 30, 30), (cx, cy), max(2, r // 12))
    if ringing:                                                            # "RRRING" vibration marks
        for sgn in (-1, 1):
            for k in range(3):
                rr = r * (1.25 + k * 0.18)
                a0 = -math.pi / 2 + sgn * 0.9
                pygame.draw.arc(surf, (255, 200, 120), (cx - rr, cy - rr, rr * 2, rr * 2),
                                min(a0, a0 + sgn * 0.5), max(a0, a0 + sgn * 0.5), max(1, r // 16))

ALARMS = {c.name: c for c in (RedAlert, Warning, Doorbell, Timer, Calm)}


def parse(payload):
    """'redalert' | 'redalert Washing machine done' | JSON {"type": .., "message": .., "duration": .., "sound": ..}"""
    import json
    p = (payload or '').strip()
    if p.startswith('{'):
        try:
            d = json.loads(p)
            return str(d.get('type') or d.get('alarm') or 'redalert'), str(d.get('message') or ''), d.get('duration'), \
                d.get('sound', True) is not False
        except ValueError:
            pass
    name, _, msg = p.partition(' ')
    if name not in ALARMS:
        name, msg = 'redalert', p
    return name, msg, None, True
