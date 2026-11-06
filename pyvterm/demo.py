"""Built-in show: boot intro + demo script + a tiny command shell (used with
--demo, --studio previews and for testing without a real shell)."""
from __future__ import annotations

import math
import platform

import numpy as np
import pygame

E = '\x1b['
R = E + '0m'


def rgb(r, g, b, bg=False):
    return '%s%d;2;%d;%d;%dm' % (E, 48 if bg else 38, r, g, b)


def rainbow(text, phase=0.0):
    out = []
    for i, c in enumerate(text):
        a = phase + i * 0.25
        out.append(rgb(int(127 + 127 * math.sin(a)), int(127 + 127 * math.sin(a + 2.1)), int(127 + 127 * math.sin(a + 4.2))) + c)
    return ''.join(out) + R


def color_table():
    s = []
    for i in range(16):
        s.append('%s48;5;%dm  ' % (E, i))
    s.append(R + '\r\n')
    for row in range(6):
        for col in range(36):
            s.append('%s48;5;%dm ' % (E, 16 + row * 36 + col))
        s.append(R + '\r\n')
    for i in range(24):
        s.append('%s48;5;%dm  ' % (E, 232 + i))
    s.append(R + '\r\n')
    for i in range(72):
        t = i / 71
        s.append(rgb(int(255 * (1 - t)), int(255 * math.sin(t * math.pi)), int(255 * t), bg=True) + ' ')
    return ''.join(s) + R + '\r\n'


def boxes():
    c1, c2, c3 = rgb(80, 220, 255), rgb(255, 200, 60), rgb(255, 90, 170)
    return (c1 + '┌──────────────┐ ' + c2 + '╔══════════════╗ ' + c3 + '┏━━━━━━━━━━━━━━┓\r\n' +
            c1 + '│ ' + R + 'light  boxes ' + c1 + '│ ' + c2 + '║ ' + R + 'double boxes ' + c2 + '║ ' + c3 + '┃ ' + R + 'heavy  boxes ' + c3 + '┃\r\n' +
            c1 + '├──────┬───────┤ ' + c2 + '╠══════╦═══════╣ ' + c3 + '┣━━━━━━╋━━━━━━━┫\r\n' +
            c1 + '│ ░▒▓█ │ ▁▂▃▅▇ │ ' + c2 + '║ ▖▗▘▙ ║ ▚▛▜▝▞ ║ ' + c3 + '┃ ⣿⡇⠿⢸ ┃ ●○■□▲ ┃\r\n' +
            c1 + '╰──────┴───────╯ ' + c2 + '╚══════╩═══════╝ ' + c3 + '┗━━━━━━┻━━━━━━━┛' + R + '\r\n')


def braille_wave(width=60):
    rows = 2
    dots = np.zeros((width * 2, rows * 4), bool)
    for x in range(width * 2):
        y = int((math.sin(x / 9) * 0.45 + 0.5) * (rows * 4 - 1))
        dots[x, y] = True
    bitpos = [(0, 0, 0), (0, 1, 1), (0, 2, 2), (1, 0, 3), (1, 1, 4), (1, 2, 5), (0, 3, 6), (1, 3, 7)]
    out = []
    for r in range(rows):
        line = []
        for cx in range(width):
            v = 0
            for dx, dy, b in bitpos:
                if dots[cx * 2 + dx, r * 4 + dy]:
                    v |= 1 << b
            line.append(chr(0x2800 + v))
        out.append(rgb(120, 255, 160) + ''.join(line) + R)
    return '\r\n'.join(out) + '\r\n'


def ansi_art(w=64, h=10):
    """procedural cp437-style block art: a sunset over mountains"""
    out = []
    for y in range(h):
        line = []
        for x in range(w):
            t = y / h
            mount = h * 0.55 + math.sin(x / 7) * 2 + math.sin(x / 3.1) * 0.8
            if y > mount:
                c = (30 + int(20 * math.sin(x)), 20, 60)
                ch = '▓' if (x + y) % 5 else '▒'
            else:
                c = (255, int(80 + 150 * t), int(60 + 80 * (1 - t)))
                ch = '█'
                sun = math.hypot(x - w * 0.7, (y - h * 0.4) * 2)
                if sun < 5:
                    c = (255, 240, 140)
            line.append(rgb(*c) + ch)
        out.append(''.join(line) + R)
    return '\r\n'.join(out) + '\r\n'


_L = [('█▀▀▄', '█▄▄▀', '█   '), ('▀▄ ▄▀', '  █  ', '  █  '), ('█   █', ' █ █ ', '  ▀  '),
      ('▀▀█▀▀', '  █  ', '  █  '), ('█▀▀▀', '█▀▀ ', '█▄▄▄'), ('█▀▀▄', '█▄▄▀', '█  █'), ('█▄ ▄█', '█ ▀ █', '█   █')]
LOGO = [' '.join(letter[r] for letter in _L) for r in range(3)]


def logo():
    out = []
    for i, l in enumerate(LOGO):
        out.append('  ' + rainbow(l, i * 0.6))
    return '\r\n'.join(out) + '\r\n'


def sysinfo():
    lines = [
        ('OS', platform.system() + ' ' + platform.release()),
        ('Python', platform.python_version()),
        ('pygame', pygame.version.ver),
        ('Machine', platform.machine()),
        ('Terminal', 'pyvterm - pixel art overkill edition'),
    ]
    return ''.join('  %s%-9s%s %s\r\n' % (rgb(255, 200, 60), k, R, v) for k, v in lines)


HELP = (rgb(120, 220, 255) + 'pyvterm demo shell' + R + ' - commands:\r\n'
        '  help  colors  boxes  art  braille  logo  info  lorem  clear  flood  error  sleep <s>\r\n'
        '  emoji  image  sixel  kitty  animfont  font <spec>  fonts\r\n'
        '  effect <name>   delete <name>   bg <name[,name]>   theme <name>   miner\r\n'
        '  cursor <style> [effect ...|none]   e.g.  cursor hero ripple trail\r\n'
        '  effects  themes  bgs  cursors      (names may be random, random:a,b or pick)\r\n'
        '  alarm <redalert|warning|doorbell|timer|calm> [message]   alarm stop   splash <name>\r\n'
        'Hotkeys: Ctrl+Shift+H shows all.\r\n')

LOREM = ('Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut '
         'labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris '
         'nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate.')


def emoji_table():
    from . import emoji
    out = [rgb(255, 220, 80) + 'built-in pixel emoji (animated ones marked *):' + R + '\r\n']
    items = list(emoji.EMOJI.items())
    line = ''
    for i, (c, name) in enumerate(items):
        line += '%s%s %-9s ' % (c, '*' if name in emoji.ANIMATED else ' ', name[:9])
        if i % 5 == 4:
            out.append(line + '\r\n')
            line = ''
    if line:
        out.append(line + '\r\n')
    out.append('\r\n  ' + ' '.join(c for c, n in items if n in emoji.ANIMATED) + '\r\n')
    return ''.join(out)


def demo_script(prompt):
    s = [
        (0.2, logo()),
        (0.6, '\r\n' + sysinfo()),
        (0.8, '\r\n' + boxes()),
        (0.8, '\r\n' + color_table()),
        (0.8, '\r\n' + braille_wave()),
        (0.6, '\r\n' + ansi_art()),
        (0.5, '\r\n' + rgb(255, 255, 255) + 'Type ' + rgb(255, 200, 0) + 'help' + R + ' for demo commands. '
              'Emojis: 😀 😎 😂 😍 😉 🤩 🔥 ⭐ 👻 🚀  unicode: äöüß € → ✓ ✗ ♪\r\n\r\n' + MARK_A + prompt + MARK_B),
    ]
    return s


MARK_A, MARK_B = '\x1b]133;A\x07', '\x1b]133;B\x07'


def image_demo(kind='all'):
    """render a little plasma picture and send it with the inline image protocols"""
    import io
    from . import images
    w, h = 192, 108
    x = np.linspace(0, 6, w)[:, None]
    y = np.linspace(0, 4, h)[None, :]
    v = np.sin(x * 2) + np.sin(y * 3 + x) + np.sin(np.sqrt(x * x + y * y) * 3)
    rgbarr = np.stack([127 + 127 * np.sin(v * 2), 127 + 127 * np.sin(v * 2 + 2), 127 + 127 * np.sin(v * 2 + 4)], -1)
    surf = pygame.Surface((w, h))
    pygame.surfarray.blit_array(surf, rgbarr.astype(np.uint8))
    pygame.draw.circle(surf, (255, 255, 255), (w // 2, h // 2), 30, 3)
    buf = io.BytesIO()
    pygame.image.save(surf, buf, 'img.png')
    png = buf.getvalue()
    out = []
    if kind in ('all', 'sixel'):
        out.append('sixel:\r\n' + images.encode_sixel(surf) + '\r\n')
    if kind in ('all', 'kitty'):
        out.append('kitty graphics protocol (12 cells wide):\r\n' + images.encode_kitty(png, cols=24) + '\r\n')
    if kind == 'all':
        out.append('iTerm2 inline image:\r\n' + images.encode_iterm(png) + '\r\n')
    return ''.join(out)


PROMPT = rgb(80, 255, 140) + 'demo' + R + '@' + rgb(80, 180, 255) + 'pyvterm' + R + ':~$ '


# ============================================================================ intro
class Intro:
    """demoscene boot sequence drawn over the terminal for a few seconds"""
    DURATION = 5.2

    def __init__(self, font, w, h, sound=None):
        self.font = font
        self.w, self.h = w, h
        self.t = 0.0
        self.done = False
        self.sound = sound
        self.post = ['pyBIOS (C) 1989-2026 Overkill Megatrends Inc.', '',
                     'CPU: %s  %s' % (platform.machine() or 'x86', platform.processor()[:30]),
                     'Memory Test: ', 'Detecting pixel accelerator ...... OK',
                     'Loading effects .................. 12 letter / 6 vanish / 9 bg',
                     'Initializing CRT phosphor ........ OK', 'Booting PYVTERM ...']
        # logo pixels
        text = 'PYVTERM'
        k = max(3, min(w // (len(text) * font.cw * 1.4), h // (font.ch * 4)))
        self.k = int(k)
        pts = []
        for i, c in enumerate(text):
            xs, ys = font.pixels(c)
            for x, y in zip(xs, ys):
                pts.append((i * font.cw + x, y))
        pts = np.array(pts, np.float32) if pts else np.zeros((1, 2), np.float32)
        lw = len(text) * font.cw * self.k
        self.tx = (w - lw) / 2 + pts[:, 0] * self.k
        self.ty = h * 0.33 + pts[:, 1] * self.k
        n = len(pts)
        ang = np.random.uniform(0, 6.283, n)
        r = np.random.uniform(w * 0.6, w * 1.2, n)
        self.sx = w / 2 + np.cos(ang) * r
        self.sy = h / 2 + np.sin(ang) * r
        self.delay = np.random.uniform(0, 0.6, n)
        self.vx = np.random.uniform(-300, 300, n)
        self.vy = np.random.uniform(-400, 50, n)
        self.scroll_text = ('   ***  PYVTERM  ***  greetings to all demosceners, ANSI artists and terminal junkies  ***  '
                            'press any key  ***  ')
        self.played = False
        self.scroller = None

    def skip(self):
        if self.t < 4.4:
            self.t = 4.4

    def update(self, dt):
        self.t += dt
        if not self.played and self.sound and self.t > 1.5:
            self.played = True
            self.sound.play('boot', min_gap=1)
        if self.t >= self.DURATION:
            self.done = True

    def draw(self, surf, colored):
        t = self.t
        w, h = self.w, self.h
        fade = 1.0 if t < 4.4 else max(0.0, 1 - (t - 4.4) / 0.8)
        if fade <= 0:
            return
        layer = pygame.Surface((w, h))
        layer.fill((0, 0, 0))
        cw, ch = self.font.cw, self.font.ch
        if t < 1.7:
            n_chars = int(t * 260)
            y = ch
            for line in self.post:
                if line.startswith('Memory Test'):
                    line = line + '%d KB OK' % min(65536, int(t * 50000))
                part = line[:max(0, n_chars)]
                n_chars -= len(line) + 6
                x = cw * 2
                for c in part:
                    if c != ' ':
                        layer.blit(colored(c, 0, False, (170, 170, 170)), (x, y))
                    x += cw
                y += ch
                if n_chars <= 0:
                    break
        else:
            lt = t - 1.7
            # copper bars
            for i in range(6):
                yy = h * 0.5 + math.sin(lt * 2 + i * 0.5) * h * 0.35
                col = [(255, 50, 50), (255, 170, 0), (255, 255, 80), (60, 255, 90), (60, 180, 255), (200, 80, 255)][i]
                for j in range(8):
                    k = 1 - abs(j - 4) / 4
                    layer.fill((int(col[0] * k * 0.5), int(col[1] * k * 0.5), int(col[2] * k * 0.5)),
                               (0, yy + j * 2, w, 2), special_flags=pygame.BLEND_RGB_ADD)
            # logo assembly
            p = np.clip((lt - self.delay) / 1.1, 0, 1)
            e = 1 + 2.70158 * (p - 1) ** 3 + 1.70158 * (p - 1) ** 2
            x = self.sx + (self.tx - self.sx) * e
            y = self.sy + (self.ty - self.sy) * e
            if t > 3.9:
                q = t - 3.9
                x = self.tx + self.vx * q
                y = self.ty + self.vy * q + 600 * q * q
            k = self.k
            for i in range(len(x)):
                a = lt * 3 + self.tx[i] * 0.02
                c = (int(127 + 127 * math.sin(a)), int(127 + 127 * math.sin(a + 2.1)), int(127 + 127 * math.sin(a + 4.2)))
                layer.fill(c, (int(x[i]), int(y[i] + math.sin(lt * 4 + self.tx[i] * 0.03) * 3 * (p[i] >= 1)), k - 1, k - 1))
            # sine scroller in the big chrome demo font
            if self.scroller is None:
                from .scroller import SineScroller
                self.scroller = SineScroller(self.scroll_text.upper(), speed=150)
            self.scroller.t, self.scroller.x = lt, lt * 150
            sch = self.scroller.font.ch
            self.scroller.draw(layer, pygame.Rect(0, 0, w, h), h * 0.8, min(h * 0.08, sch * 0.5))
        if fade < 1:
            layer.set_alpha(int(255 * fade))
        surf.blit(layer, (0, 0))
