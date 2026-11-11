"""Boot splash sequences (pluggable).

A theme picks one with  splash: c64  (config / command line:  splash: NAME, --splash NAME|none|random).
Built in:
  demo   the demoscene intro: BIOS text, particle logo, copper bars, sine scroller
  c64    a Commodore 64 powering up: READY., LOAD"$",8,1 / LIST / LOAD"PYTERM",8,1 with the
         loading stripes and a picture building up, then RUN
  c64_clean  the same boot as plain text: no loading stripes, no picture
  uplink a hacker's deck coming online: boot log, uplink key cracked digit by digit, ACCESS GRANTED
  none   straight to the terminal

Write your own (plugin):

    from pyterm.splash import Splash

    class Hello(Splash):
        duration = 3
        def draw(self, surf, colored):
            surf.fill((0, 0, 0))
            surf.blit(colored('H', 0, False, (255, 255, 0)), (10, 10))

    def register(api):
        api.register_splash('hello', Hello)

Every splash gets: self.app, self.font, self.w / self.h (virtual pixels), self.sound, self.t; any key
calls skip(). Set self.done = True when finished (the base class does it after `duration`).
"""
from __future__ import annotations

import random

import numpy as np
import pygame


class Splash:
    name = 'base'
    duration = 4.0

    def __init__(self, app):
        self.app = app
        self.font = app.font
        self.w, self.h = app.vw, app.vh
        self.sound = app.sound
        self.t = 0.0
        self.done = False
        self.start()

    def start(self):
        pass

    def skip(self):
        self.done = True

    def update(self, dt):
        self.t += dt
        if self.t >= self.duration:
            self.done = True

    def draw(self, surf, colored):
        pass


class DemoSplash(Splash):
    """the original demoscene intro (pyterm.demo.Intro)"""
    name = 'demo'

    def start(self):
        from .demo import Intro
        self.inner = Intro(self.font, self.w, self.h, self.sound)

    def skip(self):
        self.inner.skip()

    def update(self, dt):
        self.inner.update(dt)
        self.done = self.inner.done

    def draw(self, surf, colored):
        self.inner.draw(surf, colored)


# ============================================================================ Commodore 64
C64 = {'black': (0, 0, 0), 'white': (255, 255, 255), 'red': (136, 57, 50), 'cyan': (103, 182, 189),
       'purple': (139, 63, 150), 'green': (85, 160, 73), 'blue': (53, 40, 121), 'yellow': (191, 206, 114),
       'orange': (139, 84, 41), 'brown': (87, 66, 0), 'lred': (184, 105, 98), 'dgrey': (80, 80, 80),
       'grey': (120, 120, 120), 'lgreen': (148, 224, 137), 'lblue': (108, 94, 181), 'lgrey': (159, 159, 159)}
STRIPES = [C64[k] for k in ('red', 'cyan', 'purple', 'green', 'blue', 'yellow', 'orange', 'lred', 'lgreen', 'lblue')]


class C64Boot(Splash):
    """power on, LOAD"$",8,1, LIST, LOAD"PYTERM",8,1 (loading screen), RUN"""
    name = 'c64'
    COLS, ROWS = 40, 25

    def start(self):
        from . import fonts
        self.cfont = self.font if (self.font.cw, self.font.ch) == (8, 8) else fonts.load_font('builtin:fat8')
        self.lines = [''] * self.ROWS
        self.row, self.col = 0, 0
        self.cursor = True
        self.gcache = {}
        self.mode = 'text'          # text | loading | picture
        self.load_p = 0.0
        self.load_secs = 2.6
        self.pic = None
        self.queue = self._script()
        self.wait = 0.0
        self.typing = None          # [text, i]
        self.fade = None
        self.reverse_rows = set()

    def _script(self):
        return [('wait', 0.35), ('print', ''), ('print', '    **** COMMODORE 64 BASIC V2 ****'), ('print', ''),
                ('print', ' 64K RAM SYSTEM  38911 BASIC BYTES FREE'), ('print', ''), ('print', 'READY.'),
                ('wait', 0.9), ('type', 'LOAD"$",8,1'), ('print', ''), ('print', 'SEARCHING FOR $'), ('wait', 0.55),
                ('print', 'LOADING'), ('wait', 0.8), ('print', 'READY.'), ('wait', 0.35), ('type', 'LIST'), ('print', ''),
                ('rprint', '0 "PYTERM DISK   " PY 2A'),
                ('print', '42   "PYTERM"          PRG'), ('print', '17   "THEMES"           PRG'),
                ('print', '9    "PLUGINS"          PRG'), ('print', '6    "FONTS"            PRG'),
                ('print', '1    "README"           SEQ'), ('print', '589 BLOCKS FREE.'), ('print', 'READY.'),
                ('wait', 0.8), ('type', 'LOAD"PYTERM",8,1'), ('print', ''), ('print', 'SEARCHING FOR PYTERM'),
                ('wait', 0.45), ('print', 'LOADING'), ('load', None), ('wait', 0.7), ('text', None),
                ('print', 'READY.'), ('wait', 0.3), ('type', 'RUN'), ('print', ''), ('wait', 0.25), ('clear', None),
                ('wait', 0.35), ('end', None)]

    # ------------------------------------------------------------ screen buffer
    def _newline(self):
        self.row += 1
        self.col = 0
        if self.row >= self.ROWS:
            self.lines = self.lines[1:] + ['']
            self.reverse_rows = {r - 1 for r in self.reverse_rows if r > 0}
            self.row = self.ROWS - 1

    def _print(self, text, reverse=False):
        self.lines[self.row] = text[:self.COLS]
        if reverse:
            self.reverse_rows.add(self.row)
        self._newline()

    def skip(self):
        if not self.fade:
            self.fade = 0.0

    def update(self, dt):
        self.t += dt
        if self.fade is not None:
            self.fade += dt
            if self.fade > 0.35:
                self.done = True
            return
        if self.mode == 'loading':
            self.load_p = min(1.0, self.load_p + dt / self.load_secs)
            if self.load_p >= 1.0:
                self.mode = 'picture'
            return
        if self.typing:
            text, i, acc = self.typing
            acc += dt
            while acc >= 1 / 13 and i < len(text):
                acc -= 1 / 13
                self.lines[self.row] += text[i]
                i += 1
                self.sound.play('key', min_gap=0.02)
            self.typing = [text, i, acc] if i < len(text) else None
            if self.typing is None:
                self.lines[self.row] = self.lines[self.row][:self.COLS]
                self._newline()
                self.wait = 0.15
            return
        if self.wait > 0:
            self.wait -= dt
            return
        while self.queue and self.wait <= 0 and not self.typing and self.mode != 'loading':
            op, arg = self.queue.pop(0)
            if op == 'wait':
                self.wait = arg
            elif op == 'print':
                self._print(arg)
            elif op == 'rprint':
                self._print(arg, reverse=True)
            elif op == 'type':
                self.typing = [arg, 0, 0.0]
            elif op == 'load':
                from .scenes2 import C64 as PAL, _c64_picture
                img = _c64_picture(random.randrange(3))
                rgb = np.array(PAL, np.uint8)[img]
                pic = pygame.Surface(img.shape)
                pygame.surfarray.blit_array(pic, rgb)
                self.pic = pygame.transform.scale(pic, (320, 200))
                H = 200
                self.order = [r * 8 + k for k in range(8) for r in range(H // 8) if r * 8 + k < H]
                self.mode = 'loading'
                self.load_p = 0.0
            elif op == 'text':
                self.mode = 'text'
            elif op == 'off':
                self.mode = 'off'
                self.wait = arg
            elif op == 'clear':
                self.lines = [''] * self.ROWS
                self.reverse_rows = set()
                self.row = self.col = 0
            elif op == 'end':
                self.fade = 0.0
        if not self.queue and self.fade is None and not self.typing and self.wait <= 0:
            self.fade = 0.0

    # ------------------------------------------------------------ drawing
    def _glyph(self, c, rgb):
        key = (c, rgb)
        g = self.gcache.get(key)
        if g is None:
            g = self.cfont.glyph(c).copy()
            g.fill(rgb + (255,), special_flags=pygame.BLEND_RGBA_MULT)
            self.gcache[key] = g
        return g

    def _screen(self):
        s = pygame.Surface((320, 200))
        bg, fg = C64['blue'], C64['lblue']
        s.fill(bg)
        if self.mode in ('loading', 'picture'):
            done = int(len(self.order) * self.load_p)
            for r in self.order[:done]:
                s.blit(self.pic, (0, r), (0, r, 320, 1))
            return s
        for y, line in enumerate(self.lines):
            rev = y in self.reverse_rows
            if rev:
                s.fill(fg, (0, y * 8, len(line) * 8, 8))
            for x, c in enumerate(line):
                if c != ' ':
                    s.blit(self._glyph(c, bg if rev else fg), (x * 8, y * 8))
        if not self.typing and int(self.t * 3) % 2 == 0 or self.typing:
            cx = len(self.lines[self.row]) if self.typing else 0
            if cx < self.COLS:
                s.fill(fg, (cx * 8, self.row * 8, 8, 8))
        return s

    def draw(self, surf, colored):
        W, H = surf.get_size()
        border = C64['lblue']
        if self.mode == 'off':                   # power switch not flipped yet: black screen
            surf.fill((0, 0, 0))
            return
        if self.mode == 'loading':
            # tape-style loading stripes in the border while the picture comes in
            rng = random.Random(int(self.t * 30))
            y = 0
            while y < H:
                hh = rng.randint(2, 7)
                surf.fill(rng.choice(STRIPES), (0, y, W, hh))
                y += hh
        else:
            surf.fill(border)
        scr = self._screen()
        # same rule as the theme's fixed screen: 320x200 plus at least half of the original border
        k = max(1, min(W // 352, H // 236)) if W >= 320 and H >= 200 else 0
        if k:
            sw, sh = 320 * k, 200 * k
            if k > 1:
                scr = pygame.transform.scale(scr, (sw, sh))
        else:
            f = min(W / 352, H / 236)
            sw, sh = max(1, int(320 * f)), max(1, int(200 * f))
            scr = pygame.transform.smoothscale(scr, (sw, sh))
        surf.blit(scr, ((W - sw) // 2, (H - sh) // 2))


class C64Clean(C64Boot):
    """the same C64 start without the show: power on, LOAD"$",8,1, LIST, LOAD, RUN - plain text only,
    no loading stripes, no picture, a quick and quiet boot"""
    name = 'c64_clean'

    def _script(self):
        out = [('off', 0.4), ('text', None)]
        for op, arg in super()._script():
            if op == 'load':
                out.append(('wait', 1.1))
            elif op == 'text':
                continue
            elif op == 'wait':
                out.append((op, arg * 0.8))
            else:
                out.append((op, arg))
        return out


# ============================================================================ uplink
class Uplink(Splash):
    """a hacker's deck coming online: boot log, an uplink key cracked digit by digit,
    ACCESS GRANTED in big glitching letters, shutter wipe to the shell"""
    name = 'uplink'
    duration = 5.4
    HEX = '0123456789ABCDEF'
    CY, MG, GR, DIM = (0, 255, 208), (255, 48, 128), (60, 255, 120), (0, 120, 100)
    LOG = [('', 'ZERODAY//OS 9.1   kernel 6.66-ghost   deck online'),
           ('OK', 'entropy pool seeded'),
           ('OK', 'mac address spoofed    de:ad:be:ef:13:37'),
           ('OK', 'onion circuit built    3 hops  NL > IS > CH'),
           ('OK', 'tunnel up              wg0  10.66.6.1'),
           ('OK', 'satellite relay        SAT-7  lock'),
           ('..', 'cracking uplink key')]
    T_LOG, T_KEY, T_GRANT, T_WIPE = 0.24, 1.9, 3.7, 4.95

    def start(self):
        self.key = ''.join(random.choice(self.HEX) for _ in range(16))
        self.big = {}
        self.said = set()
        self.rain = [[random.randrange(0, max(1, self.w)), random.uniform(-self.h, self.h), random.uniform(40, 140)]
                     for _ in range(max(8, self.w // 14))]

    def _beep(self, tag, kind, **kw):
        if tag not in self.said:
            self.said.add(tag)
            if self.sound:
                self.sound.play(kind, **kw)

    def update(self, dt):
        super().update(dt)
        for r in self.rain:
            r[1] += r[2] * dt
            if r[1] > self.h:
                r[1] = -random.uniform(10, self.h * 0.5)
                r[0] = random.randrange(0, max(1, self.w))
        t = self.t
        n = min(len(self.LOG), int(t / self.T_LOG))
        if n:
            self._beep('log%d' % n, 'key', pitch=n * 2, min_gap=0)
        if self.T_KEY < t < self.T_GRANT:
            self._beep('key%d' % int((t - self.T_KEY) / (self.T_GRANT - self.T_KEY) * 16), 'key', pitch=int(t * 40), min_gap=0)
        if t >= self.T_GRANT:
            self._beep('grant', 'boot', min_gap=0)

    def _text(self, surf, colored, x, y, s, rgb):
        cw = self.font.cw
        for i, c in enumerate(s):
            if c != ' ':
                surf.blit(colored(c, 0, False, rgb), (x + i * cw, y))

    def _big(self, colored, s, rgb, n):
        key = (s, rgb, n)
        b = self.big.get(key)
        if b is None:
            cw, ch = self.font.cw, self.font.ch
            b = pygame.Surface((len(s) * cw, ch))
            b.fill((0, 0, 0))
            self._text(b, colored, 0, 0, s, rgb)
            b = pygame.transform.scale(b, (b.get_width() * n, b.get_height() * n))
            self.big[key] = b
        return b

    def draw(self, surf, colored):
        w, h, t = self.w, self.h, self.t
        cw, ch = self.font.cw, self.font.ch
        surf.fill((2, 4, 9))
        for x, y, v in self.rain:                              # falling data streaks
            c = int(v * 0.35)
            surf.fill((0, c, int(c * 0.8)), (x, int(y), 1, int(v * 0.12)))
        cols = max(20, w // cw)
        x0 = max(cw, (w - min(cols - 2, 54) * cw) // 2)
        y0 = max(ch, int(h * 0.16))
        ADD = pygame.BLEND_RGB_ADD
        if t < self.T_GRANT + 0.25:
            for i, (tag, line) in enumerate(self.LOG):
                age = t - i * self.T_LOG
                if age < 0:
                    break
                y = y0 + i * (ch + 2)
                if tag:
                    done = tag == 'OK' or t >= self.T_GRANT
                    self._text(surf, colored, x0, y, '[', self.DIM)
                    self._text(surf, colored, x0 + cw, y, ' OK ' if done else (' .. ', ' ·· ')[int(t * 6) % 2], self.GR if done else self.MG)
                    self._text(surf, colored, x0 + 5 * cw, y, ']', self.DIM)
                    shown = line[:int(age * 90)]
                    self._text(surf, colored, x0 + 7 * cw, y, shown, self.CY)
                else:
                    self._text(surf, colored, x0, y, line[:int(age * 90)], (255, 255, 255))
            if t >= self.T_KEY:                                # the key locks in digit by digit
                k = min(1.0, (t - self.T_KEY) / (self.T_GRANT - self.T_KEY))
                locked = int(k * 16)
                y = y0 + (len(self.LOG) + 1) * (ch + 2)
                self._text(surf, colored, x0, y, 'KEY', self.DIM)
                for i in range(16):
                    gx = x0 + (5 + i * 2 + i // 4) * cw
                    if i < locked:
                        self._text(surf, colored, gx, y, self.key[i], (255, 255, 255) if i == locked - 1 else self.GR)
                    else:
                        self._text(surf, colored, gx, y, random.choice(self.HEX), self.DIM)
                bw = min(w - 2 * x0, 40 * cw)
                y += ch + 4
                pygame.draw.rect(surf, self.DIM, (x0, y, bw, ch), 1)
                surf.fill(self.CY, (x0 + 2, y + 2, int((bw - 4) * k), ch - 4))
                self._text(surf, colored, x0 + bw + cw, y, '%3d%%' % int(k * 100), self.CY)
        if t >= self.T_GRANT:                                  # ACCESS GRANTED
            g = t - self.T_GRANT
            surf.fill((0, 0, 0), (0, 0, w, h)) if g > 0.25 else None
            for x, y, v in self.rain:
                c = int(v * 0.5)
                surf.fill((0, c, int(c * 0.6)), (x, int(y), 1, int(v * 0.2)))
            n = max(1, min(4, (w - 2 * cw) // (14 * cw)))
            lines = ['ACCESS GRANTED'] if n > 1 or w >= 14 * cw else ['ACCESS', 'GRANTED']
            a = int(max(0.0, 0.5 - g) * 24) + (random.randint(1, 3) if random.random() < 0.12 else 0)
            for li, s in enumerate(lines):
                bx = (w - len(s) * cw * n) // 2
                by = h // 2 - (len(lines) * ch * n) // 2 + li * ch * n + (random.randint(-2, 2) if a > 3 else 0)
                if a:
                    surf.blit(self._big(colored, s, self.CY, n), (bx - a, by), special_flags=ADD)
                    surf.blit(self._big(colored, s, self.MG, n), (bx + a, by), special_flags=ADD)
                surf.blit(self._big(colored, s, (255, 255, 255) if g < 0.5 else self.GR, n), (bx, by),
                          special_flags=ADD if a else 0)
            sub = 'welcome back, operator'
            if g > 0.45:
                self._text(surf, colored, (w - len(sub) * cw) // 2, h // 2 + ch * n, sub[:int((g - 0.45) * 60)], self.CY)
            yb = h // 2 - ch * n - 6
            lw = int(min(1.0, g * 3) * w * 0.4)
            surf.fill(self.GR, (w // 2 - lw, yb, lw * 2, 1))
            surf.fill(self.GR, (w // 2 - lw, h - yb + ch, lw * 2, 1))
            if g < 0.18:
                v = int(200 * (1 - g / 0.18))
                surf.fill((v // 3, v, v // 2), special_flags=ADD)
        if t >= self.T_WIPE:                                   # shutter wipe
            k = min(1.0, (t - self.T_WIPE) / (self.duration - self.T_WIPE))
            bar = max(4, h // 12)
            for y in range(0, h, bar):
                surf.fill((0, 0, 0), (0, y, w, int(bar * k) + 1))


SPLASHES = {'demo': DemoSplash, 'c64': C64Boot, 'c64_clean': C64Clean, 'uplink': Uplink, 'none': None}


def make_splash(app):
    """the splash for this start: config 'splash' > theme 'splash' > demo"""
    cfg, th = app.cfg, app.theme
    name = cfg.get('splash') or 'auto'
    if name == 'auto':
        name = th.get('splash') or 'demo'
    if name == 'random':
        name = random.choice([n for n, c in SPLASHES.items() if c])
    cls = SPLASHES.get(name, DemoSplash)
    return cls(app) if cls else None
