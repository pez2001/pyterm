"""Cell grid -> pixels. Incremental: only dirty rows are re-rendered and
scrolling is done with Surface.scroll, so `cat hugefile` stays cheap."""
from __future__ import annotations


import pygame

from . import emoji
from .themes import hex2rgb
from .vt import BLINK, BOLD, DIM, HIDDEN, ITALIC, REVERSE, STRIKE, TRUECOLOR, UNDERLINE

try:  # pygame-ce >= 2.1.4 / pygame >= 2.0
    _BLITS_KW = {'doreturn': False}
    pygame.Surface((1, 1)).blits([], **_BLITS_KW)
except TypeError:  # pragma: no cover
    _BLITS_KW = {'doreturn': 0}


class Renderer:
    def __init__(self, font, theme, gcache=None):
        self.font = font
        self.cw, self.ch = font.cw, font.ch
        self.tsurf = None
        self.cols = self.rows = 0
        self.gcache = gcache if gcache is not None else {}  # shared between panes
        self._last_view = 0
        self.attr_cache = {}
        self.extra_dirty = set()
        self.blink_on = True
        self.blink_rows = set()
        self.anim_rows = set()
        self.anim_tick = 0
        self.font_frame = 0
        self.set_theme(theme)

    # ------------------------------------------------------------ setup
    def set_theme(self, theme, cell_alpha=None):
        self.theme = theme
        self.pal = theme.build_palette()
        self.fg = hex2rgb(theme['fg'])
        self.bg = hex2rgb(theme['bg'])
        self.bg_alpha = int(theme.get('bg_alpha', 255))
        # cells with their own background color (mc, htop bars, powerline...): see-through over scenes.
        # default: opaque on opaque themes, 170 where the theme shows a background scene
        ca = cell_alpha if cell_alpha is not None else theme.get('cell_bg_alpha')
        self.cell_alpha = max(0, min(255, int(ca))) if ca is not None else (255 if self.bg_alpha >= 255 else 170)
        self.shadow = bool(theme.get('text_shadow'))
        self.bold_bright = bool(theme.get('bold_bright', True))
        self.cursor_rgb = hex2rgb(theme.get('cursor', '#ffcc00'))
        key = (tuple(self.pal[:16]), self.fg, self.bg, self.bg_alpha, self.cell_alpha, self.shadow, self.bold_bright)
        if key != getattr(self, '_theme_key', None):
            self._theme_key = key
            self.attr_cache.clear()
            if self.gcache.get('__theme__') != key:
                self.gcache.clear()
                self.gcache['__theme__'] = key
        self.full = True

    def set_font(self, font):
        self.font = font
        self.cw, self.ch = font.cw, font.ch
        self.gcache.clear()
        self.tsurf = None

    def ensure(self, cols, rows):
        if self.tsurf is None or (cols, rows) != (self.cols, self.rows):
            self.cols, self.rows = cols, rows
            self.tsurf = pygame.Surface((cols * self.cw, rows * self.ch), pygame.SRCALPHA)
            self.tsurf.fill((0, 0, 0, 0))
            self.full = True

    # ------------------------------------------------------------ colors
    def color(self, c, default):
        if c < 0:
            return default
        if c >= TRUECOLOR:
            return ((c >> 16) & 255, (c >> 8) & 255, c & 255)
        return self.pal[c]

    def resolve(self, attr):
        r = self.attr_cache.get(attr)
        if r is not None:
            return r
        fg, bg, fl = attr
        if fl & BOLD and self.bold_bright and 0 <= fg < 8:
            fg += 8
        f = self.color(fg, self.fg)
        b = None if bg < 0 else self.color(bg, self.bg)
        if fl & REVERSE:
            f, b = (b or self.bg), f
        if fl & DIM:
            f = (f[0] * 3 // 5, f[1] * 3 // 5, f[2] * 3 // 5)
        if fl & HIDDEN:
            f = None
        if b is None:
            bgc = (self.bg + (self.bg_alpha,)) if self.bg_alpha > 0 else None
        elif fl & REVERSE:
            bgc = b + (max(self.cell_alpha, 210),)      # reverse video = selection bars: keep them solid
        else:
            bgc = b + (self.cell_alpha,) if self.cell_alpha > 0 else None
        r = (f, bgc, fl & (BOLD | ITALIC), fl)
        self.attr_cache[attr] = r
        return r

    def set_anim(self, t):
        """advance animated emoji (8 fps) and animated fonts (their own fps)"""
        tick = int(t * emoji.FRAMES)
        if tick != self.anim_tick:
            self.anim_tick = tick
            if self.anim_rows:
                self.extra_dirty |= self.anim_rows
        f = self.font
        if f.animated:
            hold = getattr(f, 'hold', None)
            ff = (hold if hold is not None else int(t * f.fps)) % len(f.frames)
            if ff != self.font_frame:
                self.font_frame = ff
                self.full = True
            f.set_frame(ff)

    def colored(self, c, style, wide, rgb):
        if c in emoji.EMOJI:
            return emoji.surface(c, self.cw * (2 if wide else 1), self.ch, self.anim_tick)
        if self.font.animated:
            self.font.set_frame(self.font_frame)
            key = (c, style, wide, rgb, self.font_frame)
        else:
            key = (c, style, wide, rgb)
        s = self.gcache.get(key)
        if s is None:
            if len(self.gcache) > 30000:
                k = self.gcache.get('__theme__')
                self.gcache.clear()
                self.gcache['__theme__'] = k
            g = self.font.glyph(c, style, wide)
            s = g.copy()
            if getattr(self.font, 'colored', False) and not emoji.is_emoji(c):
                # colored font: keep its own colors, tinted a little by the ANSI color
                m = getattr(self.font, 'tint_mix', 0.55)
                tint = tuple(int(255 + (v - 255) * m) for v in rgb)
                s.fill(tint + (255,), special_flags=pygame.BLEND_RGBA_MULT)
            else:
                s.fill(rgb + (255,), special_flags=pygame.BLEND_RGBA_MULT)
            if self.shadow:
                sh = g.copy()
                sh.fill((0, 0, 0, 190), special_flags=pygame.BLEND_RGBA_MULT)
                o = pygame.Surface(g.get_size(), pygame.SRCALPHA)
                o.fill((0, 0, 0, 0))
                d = max(1, self.ch // 12)
                o.blit(sh, (d, d))
                o.blit(s, (0, 0))
                s = o
            self.gcache[key] = s
        return s

    # ------------------------------------------------------------ render
    def render(self, screen, hidden_rows, view_offset=0):
        self.ensure(screen.cols, screen.rows)
        ts = self.tsurf
        if view_offset != self._last_view:
            self.full = True
            self._last_view = view_offset
        if view_offset and not (screen.dirty or screen.scroll_ops or screen.full_dirty or self.full
                                or self.extra_dirty or self._blink_changed):
            return
        if screen.full_dirty or self.full or view_offset:
            rows = range(screen.rows)
            screen.scroll_ops.clear()
            screen.full_dirty = False
            self.full = False
        else:
            W = ts.get_width()
            ch = self.ch
            for top, bot, n in screen.scroll_ops:
                if n:
                    ts.set_clip((0, top * ch, W, (bot - top + 1) * ch))
                    ts.scroll(0, -n * ch)
                    ts.set_clip(None)
            screen.scroll_ops.clear()
            rows = screen.dirty | self.extra_dirty
            if self.blink_rows and self._blink_changed:
                rows |= self.blink_rows
        self._blink_changed = False
        for y in rows:
            if 0 <= y < screen.rows:
                r = screen.get_view_row(y, view_offset)
                self.render_row(y, r, None if view_offset else hidden_rows.get(y))
        screen.dirty.clear()
        self.extra_dirty.clear()

    _blink_changed = False

    def set_blink(self, on):
        if on != self.blink_on:
            self.blink_on = on
            self._blink_changed = True

    def render_extra(self, screen, view_offset, n):
        """n rows *above* the visible window (for smooth scrolling) as a surface"""
        s = pygame.Surface((self.cols * self.cw, n * self.ch), pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        for i in range(n):
            r = screen.get_view_row(-n + i, view_offset)
            if r is not None:
                self.render_row(i, r, None, dst=s)
        return s

    def render_row(self, y, row, hid, dst=None):
        cw, ch = self.cw, self.ch
        ts = self.tsurf if dst is None else dst
        py = y * ch
        ts.fill((0, 0, 0, 0), (0, py, self.cols * cw, ch))
        if dst is None:
            self.blink_rows.discard(y)
            self.anim_rows.discard(y)
        if row is None:
            return
        rowc, rowa = row
        cols = min(self.cols, len(rowc))
        blits = []
        x = 0
        resolve = self.resolve
        colored = self.colored
        while x < cols:
            a = rowa[x]
            x2 = x + 1
            while x2 < cols and rowa[x2] is a:
                x2 += 1
            f, bgc, style, fl = resolve(a)
            if bgc:
                ts.fill(bgc, (x * cw, py, (x2 - x) * cw, ch))
            if f is not None:
                if fl & BLINK and dst is None:
                    self.blink_rows.add(y)
                if not (fl & BLINK) or self.blink_on:
                    for i in range(x, x2):
                        c = rowc[i]
                        if c == ' ' or c == '' or (hid and i in hid):
                            continue
                        wide = i + 1 < cols and rowc[i + 1] == ''
                        blits.append((colored(c, style, wide, f), (i * cw, py)))
                        if dst is None and c in emoji.EMOJI and emoji.is_animated(c):
                            self.anim_rows.add(y)
                    if fl & UNDERLINE:
                        ts.fill(f + (255,), (x * cw, py + ch - max(2, ch // 7), (x2 - x) * cw, max(1, ch // 12)))
                    if fl & STRIKE:
                        ts.fill(f + (255,), (x * cw, py + ch // 2, (x2 - x) * cw, max(1, ch // 12)))
            x = x2
        if blits:
            ts.blits(blits, **_BLITS_KW)

    # ------------------------------------------------------------ selection
    def draw_selection(self, surf, ox, oy, sel, cols):
        (x0, y0), (x1, y1) = sel
        if (y1, x1) < (y0, x0):
            (x0, y0), (x1, y1) = (x1, y1), (x0, y0)
        hl = pygame.Surface((cols * self.cw, self.ch), pygame.SRCALPHA)
        hl.fill((90, 160, 255, 90))
        for y in range(y0, y1 + 1):
            a = x0 if y == y0 else 0
            b = x1 if y == y1 else cols - 1
            surf.blit(hl, (ox + a * self.cw, oy + y * self.ch), (0, 0, (b - a + 1) * self.cw, self.ch))
