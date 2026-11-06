"""VT100 / xterm compatible terminal state machine.

Screen holds the cell grid; Parser turns a decoded text stream into screen
operations. Designed for throughput: printable runs are matched with a regex
and written as list slices, escape sequences are matched with regexes too.

Every visible change can be recorded as an *event* so the effect engine knows
which letters appeared / vanished and when the screen scrolled.
"""
from __future__ import annotations

import re
import unicodedata
from collections import deque

# ---------------------------------------------------------------- attributes
BOLD, DIM, ITALIC, UNDERLINE, BLINK, REVERSE, HIDDEN, STRIKE = (1 << i for i in range(8))
DEFAULT = -1
TRUECOLOR = 0x1000000          # fg/bg >= TRUECOLOR  ->  0x1RRGGBB

_ATTR_INTERN: dict = {}


def mkattr(fg=DEFAULT, bg=DEFAULT, flags=0):
    t = (fg, bg, flags)
    return _ATTR_INTERN.setdefault(t, t)


DEFAULT_ATTR = mkattr()

# ---------------------------------------------------------------- events
EV_PUT = 1      # (EV_PUT, x, y, ch, attr)    letter appeared
EV_DEL = 2      # (EV_DEL, x, y, ch, attr)    letter vanished
EV_SCROLL = 3   # (EV_SCROLL, top, bottom, n) n>0: content moved up
EV_RESET = 4    # (EV_RESET,)                 everything invalid (alt screen, resize, RIS)
EV_BELL = 5     # (EV_BELL,)
EV_NL = 6       # (EV_NL,)                    newline (sound)
EV_CMD = 7      # (EV_CMD, mark)              shell integration: command finished
EV_IMAGE = 8    # (EV_IMAGE, image)           inline image placed

import time as _time
from urllib.parse import unquote as _unquote

DEC_GRAPHICS = {
    '`': '◆', 'a': '▒', 'b': '␉', 'c': '␌', 'd': '␍', 'e': '␊', 'f': '°', 'g': '±',
    'h': '␤', 'i': '␋', 'j': '┘', 'k': '┐', 'l': '┌', 'm': '└', 'n': '┼', 'o': '⎺',
    'p': '⎻', 'q': '─', 'r': '⎼', 's': '⎽', 't': '├', 'u': '┤', 'v': '┴', 'w': '┬',
    'x': '│', 'y': '≤', 'z': '≥', '{': 'π', '|': '≠', '}': '£', '~': '·',
}
_DEC_TABLE = str.maketrans(DEC_GRAPHICS)

_wcache: dict = {}


def char_width(c: str) -> int:
    w = _wcache.get(c)
    if w is None:
        cat = unicodedata.category(c)
        if cat in ('Mn', 'Me', 'Cf') or unicodedata.combining(c):
            w = 0
        elif unicodedata.east_asian_width(c) in ('W', 'F'):
            w = 2
        else:
            w = 1
        _wcache[c] = w
    return w


# ============================================================================
class Screen:
    def __init__(self, cols=80, rows=25, scrollback=5000):
        self.cols = max(2, cols)
        self.rows = max(2, rows)
        self.scrollback = deque(maxlen=scrollback)
        self.events: list = []
        self.record = True
        self.event_cap = 6000
        self.overflow = False
        self.dirty: set = set()
        self.scroll_ops: list = []
        self.full_dirty = True
        self.replies: list = []
        self.title = 'pixelterm'
        self.title_changed = False
        self.last_char = ' '
        self.total_scrolled = 0
        self.images = []           # inline images (sixel / kitty / iTerm2), anchored to absolute lines
        self.sixel_layer = None    # alternate screen: one screen-sized layer all sixels paint into
        self.sixel_hold = 0.0
        self.kitty_store = {}      # kitty image id -> surface
        self._kitty_chunks = None
        self.cell_px = (8, 16)     # cell size in *window* pixels (set by the pane, used for images)
        self.marks = []            # shell integration command blocks (OSC 133)
        self.cwd = None            # OSC 7 / OSC 9;9
        self.reset()

    # ------------------------------------------------------------ helpers
    def _blank(self, attr=None):
        a = attr if attr is not None else self._erase_attr()
        return [' '] * self.cols, [a] * self.cols

    def _erase_attr(self):
        bg = self.attr[1]
        return DEFAULT_ATTR if bg == DEFAULT else mkattr(DEFAULT, bg, 0)

    def reset(self):
        self.attr = DEFAULT_ATTR
        self.cx = self.cy = 0
        self.wrap_pending = False
        self.top, self.bottom = 0, self.rows - 1
        self.autowrap = True
        self.insert = False
        self.origin = False
        self.cursor_visible = True
        self.app_cursor = False
        self.app_keypad = False
        self.bracketed_paste = False
        self.clip_ops = []          # OSC 52 from programs: ('set', text) | ('get', selection)
        self.mouse_mode = 0
        self.mouse_sgr = False
        self.cursor_shape = 0
        self.charsets = ['B', 'B']
        self.gl = 0
        self.saved = None
        self.tabs = set(range(0, self.cols, 8))
        self.chars = [[' '] * self.cols for _ in range(self.rows)]
        self.attrs = [[DEFAULT_ATTR] * self.cols for _ in range(self.rows)]
        self.alt_saved = None
        self.using_alt = False
        self.full_dirty = True
        self.events.append((EV_RESET,))

    def take_events(self):
        ev = self.events
        self.events = []
        self.overflow = False
        return ev

    def _mark_full(self):
        self.full_dirty = True
        self.scroll_ops.clear()
        self.dirty.clear()

    # ------------------------------------------------------------ text output
    def draw(self, s: str):
        if self.charsets[self.gl] == '0':
            s = s.translate(_DEC_TABLE)
        if self.insert or not s.isascii():
            for c in s:
                self._put_char(c)
            return
        cols = self.cols
        rec = self.record and not self.overflow
        self.last_char = s[-1]
        while s:
            if self.wrap_pending:
                self.wrap_pending = False
                if self.autowrap:
                    self.cx = 0
                    self._linefeed()
            x, y = self.cx, self.cy
            n = min(len(s), cols - x)
            chunk, s = s[:n], s[n:]
            rowc, rowa, a = self.chars[y], self.attrs[y], self.attr
            if rec:
                self._record(x, y, chunk, rowc, rowa, a)
            rowc[x:x + n] = chunk
            rowa[x:x + n] = [a] * n
            self.dirty.add(y)
            x += n
            if x >= cols:
                self.cx = cols - 1
                if self.autowrap:
                    self.wrap_pending = True
                elif s:
                    rowc[cols - 1] = s[-1]
                    s = ''
            else:
                self.cx = x

    def _record(self, x, y, chunk, rowc, rowa, a):
        ev = self.events
        app = ev.append
        for i, c in enumerate(chunk):
            xi = x + i
            oc = rowc[xi]
            if c == oc and rowa[xi] == a:
                continue
            if c == ' ':
                if oc != ' ' and oc != '':
                    app((EV_DEL, xi, y, oc, rowa[xi]))
            else:
                app((EV_PUT, xi, y, c, a))
        if len(ev) > self.event_cap:
            self.overflow = True

    def _put_char(self, c):
        w = char_width(c)
        if w == 0:
            return
        if self.wrap_pending:
            self.wrap_pending = False
            if self.autowrap:
                self.cx = 0
                self._linefeed()
        cols = self.cols
        if w == 2 and self.cx >= cols - 1:
            if self.autowrap:
                self.chars[self.cy][self.cx] = ' '
                self.cx = 0
                self._linefeed()
            else:
                return
        if self.insert:
            self._insert_blanks(w)
        x, y = self.cx, self.cy
        rowc, rowa = self.chars[y], self.attrs[y]
        if rowc[x] == '' and x > 0:
            rowc[x - 1] = ' '
        if self.record and not self.overflow:
            oc = rowc[x]
            if c != oc or rowa[x] != self.attr:
                if c == ' ':
                    if oc not in (' ', ''):
                        self.events.append((EV_DEL, x, y, oc, rowa[x]))
                else:
                    self.events.append((EV_PUT, x, y, c, self.attr))
        rowc[x] = c
        rowa[x] = self.attr
        if w == 2:
            rowc[x + 1] = ''
            rowa[x + 1] = self.attr
        elif x + 1 < cols and rowc[x + 1] == '':
            rowc[x + 1] = ' '
        self.dirty.add(y)
        self.last_char = c
        x += w
        if x >= cols:
            self.cx = cols - 1
            self.wrap_pending = self.autowrap
        else:
            self.cx = x

    # ------------------------------------------------------------ scrolling
    def _linefeed(self):
        if self.cy == self.bottom:
            self.scroll_up(1, to_scrollback=True)
        elif self.cy < self.rows - 1:
            self.cy += 1

    def scroll_up(self, n=1, top=None, bottom=None, to_scrollback=False):
        top = self.top if top is None else top
        bottom = self.bottom if bottom is None else bottom
        n = min(n, bottom - top + 1)
        if n <= 0:
            return
        sb = to_scrollback and top == 0 and not self.using_alt
        for _ in range(n):
            rc = self.chars.pop(top)
            ra = self.attrs.pop(top)
            if sb:
                self.scrollback.append((rc, ra))
            bc, ba = self._blank()
            self.chars.insert(bottom, bc)
            self.attrs.insert(bottom, ba)
        if sb:
            self.total_scrolled += n
        self.events.append((EV_SCROLL, top, bottom, n))
        self._shift_dirty(top, bottom, n)

    def scroll_down(self, n=1, top=None, bottom=None):
        top = self.top if top is None else top
        bottom = self.bottom if bottom is None else bottom
        n = min(n, bottom - top + 1)
        if n <= 0:
            return
        for _ in range(n):
            self.chars.pop(bottom)
            self.attrs.pop(bottom)
            bc, ba = self._blank()
            self.chars.insert(top, bc)
            self.attrs.insert(top, ba)
        self.events.append((EV_SCROLL, top, bottom, -n))
        self._shift_dirty(top, bottom, -n)

    def _shift_dirty(self, top, bottom, n):
        if self.full_dirty:
            return
        self.scroll_ops.append((top, bottom, n))
        if len(self.scroll_ops) > self.rows:
            self._mark_full()
            return
        nd = set()
        for y in self.dirty:
            if top <= y <= bottom:
                y2 = y - n
                if top <= y2 <= bottom:
                    nd.add(y2)
            else:
                nd.add(y)
        if n > 0:
            nd.update(range(bottom - n + 1, bottom + 1))
        else:
            nd.update(range(top, top - n))
        self.dirty = nd

    # ------------------------------------------------------------ erasing
    def _erase(self, y, x0, x1):
        """erase cells [x0, x1) in row y"""
        x0 = max(0, x0)
        x1 = min(self.cols, x1)
        if x1 <= x0:
            return
        rowc, rowa = self.chars[y], self.attrs[y]
        if self.record and not self.overflow:
            ev = self.events
            for x in range(x0, x1):
                c = rowc[x]
                if c != ' ' and c != '':
                    ev.append((EV_DEL, x, y, c, rowa[x]))
            if len(ev) > self.event_cap:
                self.overflow = True
        ea = self._erase_attr()
        rowc[x0:x1] = [' '] * (x1 - x0)
        rowa[x0:x1] = [ea] * (x1 - x0)
        self.dirty.add(y)

    def erase_display(self, mode):
        if mode == 0:
            self._erase(self.cy, self.cx, self.cols)
            for y in range(self.cy + 1, self.rows):
                self._erase(y, 0, self.cols)
        elif mode == 1:
            for y in range(0, self.cy):
                self._erase(y, 0, self.cols)
            self._erase(self.cy, 0, self.cx + 1)
        elif mode in (2, 3):
            for y in range(self.rows):
                self._erase(y, 0, self.cols)
            self.clear_images(visible_only=mode == 2)
            if not self.using_alt and self.marks:
                top = self.total_scrolled
                self.marks = [m for m in self.marks if m['prompt'] < top] if mode == 2 else []
            if mode == 3:
                self.scrollback.clear()

    def erase_line(self, mode):
        if mode == 0:
            self._erase(self.cy, self.cx, self.cols)
        elif mode == 1:
            self._erase(self.cy, 0, self.cx + 1)
        else:
            self._erase(self.cy, 0, self.cols)

    def _insert_blanks(self, n):
        y, x = self.cy, self.cx
        rowc, rowa = self.chars[y], self.attrs[y]
        n = min(n, self.cols - x)
        ea = self._erase_attr()
        rowc[x:x] = [' '] * n
        rowa[x:x] = [ea] * n
        del rowc[self.cols:]
        del rowa[self.cols:]
        self.dirty.add(y)

    def delete_chars(self, n):
        y, x = self.cy, self.cx
        rowc, rowa = self.chars[y], self.attrs[y]
        n = min(n, self.cols - x)
        self._record_row_shift(y)
        del rowc[x:x + n]
        del rowa[x:x + n]
        ea = self._erase_attr()
        rowc.extend([' '] * n)
        rowa.extend([ea] * n)
        self.dirty.add(y)

    def _record_row_shift(self, y):
        # horizontal shifts invalidate per-cell effects on this row
        self.events.append((EV_SCROLL, y, y, 0))

    # ------------------------------------------------------------ cursor
    def _clamp(self):
        self.cx = min(max(self.cx, 0), self.cols - 1)
        lo, hi = (self.top, self.bottom) if self.origin else (0, self.rows - 1)
        self.cy = min(max(self.cy, lo), hi)
        self.wrap_pending = False

    def goto(self, x, y):
        if self.origin:
            y += self.top
        self.cx, self.cy = x, y
        self._clamp()

    def save_cursor(self):
        self.saved = (self.cx, self.cy, self.attr, list(self.charsets), self.gl,
                      self.origin, self.wrap_pending)

    def restore_cursor(self):
        if self.saved:
            (self.cx, self.cy, self.attr, cs, self.gl, self.origin,
             self.wrap_pending) = self.saved
            self.charsets = list(cs)
            self.cx = min(self.cx, self.cols - 1)
            self.cy = min(self.cy, self.rows - 1)
        else:
            self.cx = self.cy = 0

    # ------------------------------------------------------------ alt screen
    def set_alt(self, on, save=False, clear=True):
        if on == self.using_alt:
            return
        if on:
            if save:
                self.save_cursor()
            self.alt_saved = (self.chars, self.attrs)
            self.chars = [[' '] * self.cols for _ in range(self.rows)]
            self.attrs = [[DEFAULT_ATTR] * self.cols for _ in range(self.rows)]
            self.using_alt = True
        else:
            if self.alt_saved:
                self.chars, self.attrs = self.alt_saved
            self.alt_saved = None
            self.using_alt = False
            if save:
                self.restore_cursor()
        self.images = [im for im in self.images if not im['alt']]
        self.events.append((EV_RESET,))
        self._mark_full()

    # ------------------------------------------------------------ resize
    def resize(self, cols, rows):
        cols, rows = max(2, cols), max(2, rows)
        if cols == self.cols and rows == self.rows:
            return

        def fix(chars, attrs, is_main):
            if rows < len(chars):
                cut = max(0, min(len(chars) - rows, self.cy - rows + 1)) if is_main else 0
                for i in range(cut):
                    if is_main and not self.using_alt:
                        self.scrollback.append((chars[i], attrs[i]))
                del chars[:cut]
                del attrs[:cut]
                del chars[rows:]
                del attrs[rows:]
                return cut
            while len(chars) < rows:
                chars.append([' '] * self.cols)
                attrs.append([DEFAULT_ATTR] * self.cols)
            return 0

        cut = fix(self.chars, self.attrs, True)
        if self.alt_saved:
            fix(self.alt_saved[0], self.alt_saved[1], False)
        for buf in [(self.chars, self.attrs)] + ([self.alt_saved] if self.alt_saved else []):
            for rc, ra in zip(*buf):
                if cols < len(rc):
                    del rc[cols:]
                    del ra[cols:]
                    if rc and rc[-1] == '':
                        rc[-1] = ' '
                else:
                    rc.extend([' '] * (cols - len(rc)))
                    ra.extend([DEFAULT_ATTR] * (cols - len(ra)))
        self.cy -= cut
        if not self.using_alt:
            self.total_scrolled += cut   # keeps images / command marks anchored
        self.cols, self.rows = cols, rows
        self.top, self.bottom = 0, rows - 1
        self.tabs = set(range(0, cols, 8))
        self.cx = min(self.cx, cols - 1)
        self.cy = min(max(self.cy, 0), rows - 1)
        self.wrap_pending = False
        self.events.append((EV_RESET,))
        self._mark_full()

    # ------------------------------------------------------------ controls
    def control(self, c):
        if c == '\r':
            self.cx = 0
            self.wrap_pending = False
        elif c in '\n\x0b\x0c':
            self.wrap_pending = False
            self._linefeed()
            self.events.append((EV_NL,))
        elif c == '\x08':
            if self.cx > 0:
                self.cx -= 1
            self.wrap_pending = False
        elif c == '\t':
            x = self.cx + 1
            while x < self.cols - 1 and x not in self.tabs:
                x += 1
            self.cx = min(x, self.cols - 1)
        elif c == '\x07':
            self.events.append((EV_BELL,))
        elif c == '\x0e':
            self.gl = 1
        elif c == '\x0f':
            self.gl = 0

    def esc(self, c):
        if c == '7':
            self.save_cursor()
        elif c == '8':
            self.restore_cursor()
        elif c == 'D':
            self._linefeed()
        elif c == 'E':
            self.cx = 0
            self._linefeed()
        elif c == 'M':
            if self.cy == self.top:
                self.scroll_down(1)
            elif self.cy > 0:
                self.cy -= 1
        elif c == 'H':
            self.tabs.add(self.cx)
        elif c == 'c':
            self.reset()
            self.erase_display(2)
        elif c == '=':
            self.app_keypad = True
        elif c == '>':
            self.app_keypad = False

    def designate(self, which, c):
        idx = 0 if which == '(' else 1
        if which in '()':
            self.charsets[idx] = c

    def decaln(self):
        for y in range(self.rows):
            self.chars[y] = ['E'] * self.cols
            self.attrs[y] = [DEFAULT_ATTR] * self.cols
        self._mark_full()

    def abs_line(self, y=None):
        return self.total_scrolled + (self.cy if y is None else y)

    def osc(self, s):
        code, _, arg = s.partition(';')
        if code in ('0', '2'):
            self.title = arg
            self.title_changed = True
        elif code == '133':
            self._osc133(arg)
        elif code == '7':
            # file://host/path
            path = arg
            if path.startswith('file://'):
                path = path[7:]
                path = path[path.find('/'):] if '/' in path else path
            path = _unquote(path)
            if len(path) > 2 and path[0] == '/' and path[2] == ':':
                path = path[1:]  # /C:/Users -> C:/Users
            self.cwd = path
        elif code == '9' and arg.startswith('9;'):
            self.cwd = arg[2:].strip('"')
        elif code == '52':
            # OSC 52 clipboard (vim/nvim, tmux, mc, ssh sessions, TUI frameworks): 52;c;<base64> or 52;c;?
            sel, _, data = arg.partition(';')
            if data == '?':
                self.clip_ops.append(('get', sel or 'c'))
            else:
                import base64
                try:
                    text = base64.b64decode(data + '=' * (-len(data) % 4)).decode('utf-8', 'replace') if data else ''
                except Exception:
                    text = None
                if text is not None and len(self.clip_ops) < 16:
                    self.clip_ops.append(('set', text))
        elif code == '1337' and arg.startswith('File='):
            from . import images
            img = images.decode_iterm(arg[5:])
            if img is not None:
                self.place_image(img[0], img[1], img[2])

    # ------------------------------------------------------------ shell integration
    def _osc133(self, arg):
        kind, _, rest = arg.partition(';')
        if self.using_alt:
            return
        line = self.abs_line()
        m = self.marks[-1] if self.marks else None
        if kind == 'A':
            if m and m.get('end') is None and m.get('out') is not None:
                m['end'] = line
            self.marks.append({'prompt': line, 'cmd': None, 'out': None, 'end': None, 'exit': None,
                               't0': None, 't1': None, 'cmdline': '', 'bcol': 0})
            del self.marks[:-3000]
        elif kind == 'B' and m:
            m['cmd'] = line
            m['bcol'] = self.cx
        elif kind == 'C' and m:
            m['out'] = line
            m['t0'] = _time.time()
            if m['cmd'] is not None:
                y = m['cmd'] - self.total_scrolled
                if 0 <= y < self.rows:
                    m['cmdline'] = ''.join(self.chars[y][m['bcol']:]).strip()
        elif kind == 'D' and m and m['exit'] is None:
            try:
                m['exit'] = int(rest.split(';')[0]) if rest else 0
            except ValueError:
                m['exit'] = 0
            m['t1'] = _time.time()
            if m['end'] is None:
                m['end'] = line
            if m['t0'] is not None:
                self.events.append((EV_CMD, m))

    # ------------------------------------------------------------ images
    def place_image(self, surf, cols=None, rows=None, move_cursor=True):
        """anchor an image at the cursor; cols/rows = cell size (None: native pixel size)"""
        cwp, chp = self.cell_px
        w, h = surf.get_size()
        fit = bool(cols or rows)
        if not cols and not rows:
            cols = max(1, -(-w // cwp))
            rows = max(1, -(-h // chp))
        elif cols and not rows:
            rows = max(1, round(h * cols * cwp / max(1, w) / chp))
        elif rows and not cols:
            cols = max(1, round(w * rows * chp / max(1, h) / cwp))
        img = {'surf': surf, 'col': self.cx, 'line': self.abs_line(), 'cols': cols, 'rows': rows,
               'alt': self.using_alt, 'tex': None, 'fit': fit}
        self.images.append(img)
        del self.images[:-64]
        self.events.append((EV_IMAGE, img))
        if move_cursor:
            for _ in range(rows - 1):
                self._linefeed()
            self.cx = 0
            self._linefeed()
        self.full_dirty = True

    def clear_images(self, visible_only=True):
        if not self.images:
            return
        top = self.total_scrolled
        self.images = [im for im in self.images if visible_only and im['line'] + im['rows'] <= top and not self.using_alt]

    def dcs(self, payload):
        # sixel: params 'q' data
        i = 0
        while i < len(payload) and payload[i] in '0123456789;':
            i += 1
        if i < len(payload) and payload[i] == 'q':
            if self.using_alt and _time.monotonic() < self.sixel_hold:
                return          # drawn for the previous cell grid - the program repaints for the new one
            from . import images
            surf = images.decode_sixel(payload[i + 1:])
            if surf is not None:
                if self.using_alt:
                    self.paint_sixel(surf)
                else:
                    self.place_image(surf)

    def paint_sixel(self, surf):
        """full-screen sixel programs (alternate screen): every sixel paints into one screen-sized layer,
        like on a real terminal, instead of piling up as separate images"""
        import pygame
        cwp, chp = self.cell_px
        size = (self.cols * cwp, self.rows * chp)
        im = self.sixel_layer
        if im is None or size != im['surf'].get_size() or not any(i is im for i in self.images):
            im = {'surf': pygame.Surface(size, pygame.SRCALPHA), 'col': 0, 'line': self.total_scrolled,
                  'cols': self.cols, 'rows': self.rows, 'alt': True, 'tex': None, 'fit': False}
            im['surf'].fill((0, 0, 0, 0))
            self.sixel_layer = im
            self.images.append(im)
            del self.images[:-64]
        im['surf'].blit(surf, (self.cx * cwp, self.cy * chp))
        im['_tex'] = None           # both presenters rebuild from the surface
        im['_sw_key'] = None
        for _ in range(-(-surf.get_height() // chp) - 1):
            self._linefeed()
        self.cx = 0
        self._linefeed()
        self.full_dirty = True

    def grid_changed(self, hold=0.15):
        """the cell grid (font, scale or size) changed: the sixel layer no longer fits - drop it and ignore
        sixels for a moment, they were still drawn for the old grid"""
        if self.sixel_layer is not None:
            self.images = [im for im in self.images if im is not self.sixel_layer]
            self.sixel_layer = None
        self.sixel_hold = _time.monotonic() + hold
        self.full_dirty = True

    def apc(self, payload):
        if not payload.startswith('G'):
            return
        from . import images
        images.kitty_command(self, payload[1:])

    # ------------------------------------------------------------ CSI
    def csi(self, params, inter, final):
        priv = ''
        if params and params[0] in '?><=':
            priv, params = params[0], params[1:]
        if final == 'm' and not priv and not inter:
            self.sgr(params)
            return
        try:
            ps = [int(p) if p else 0 for p in params.split(';')] if params else []
        except ValueError:
            ps = []
        p0 = ps[0] if ps else 0
        p1 = max(1, p0)
        f = final
        if f == 't' and not inter and not priv and p0 in (14, 16, 18):
            # XTWINOPS size reports: text area in pixels, cell in pixels, text area in cells
            cwp, chp = self.cell_px
            self.replies.append({14: '\x1b[4;%d;%dt' % (self.rows * chp, self.cols * cwp),
                                 16: '\x1b[6;%d;%dt' % (chp, cwp),
                                 18: '\x1b[8;%d;%dt' % (self.rows, self.cols)}[p0])
            return
        if inter:
            if inter == ' ' and f == 'q':
                self.cursor_shape = p0
            elif inter == '!' and f == 'p':
                self.reset()
            return
        if f == 'A':
            self.cy = max(self.top if self.cy >= self.top else 0, self.cy - p1); self.wrap_pending = False
        elif f == 'B' or f == 'e':
            self.cy = min(self.bottom if self.cy <= self.bottom else self.rows - 1, self.cy + p1); self.wrap_pending = False
        elif f == 'C' or f == 'a':
            self.cx = min(self.cols - 1, self.cx + p1); self.wrap_pending = False
        elif f == 'D':
            self.cx = max(0, self.cx - p1); self.wrap_pending = False
        elif f == 'E':
            self.cx = 0; self.cy = min(self.rows - 1, self.cy + p1); self.wrap_pending = False
        elif f == 'F':
            self.cx = 0; self.cy = max(0, self.cy - p1); self.wrap_pending = False
        elif f == 'G' or f == '`':
            self.cx = min(self.cols - 1, p1 - 1); self.wrap_pending = False
        elif f == 'H' or f == 'f':
            y = (ps[0] if ps and ps[0] else 1) - 1
            x = (ps[1] if len(ps) > 1 and ps[1] else 1) - 1
            self.goto(x, y)
        elif f == 'd':
            self.goto(self.cx, p1 - 1)
        elif f == 'J':
            self.erase_display(p0)
        elif f == 'K':
            self.erase_line(p0)
        elif f == 'L':
            if self.top <= self.cy <= self.bottom:
                self.scroll_down(p1, self.cy, self.bottom); self.cx = 0
        elif f == 'M':
            if self.top <= self.cy <= self.bottom:
                self.scroll_up(p1, self.cy, self.bottom); self.cx = 0
        elif f == 'P':
            self.delete_chars(p1)
        elif f == '@':
            self._record_row_shift(self.cy)
            self._insert_blanks(p1)
        elif f == 'X':
            self._erase(self.cy, self.cx, self.cx + p1)
        elif f == 'S' and not priv:
            self.scroll_up(p1)
        elif f == 'T' and not priv:
            self.scroll_down(p1)
        elif f == 'r' and not priv:
            top = (ps[0] if ps and ps[0] else 1) - 1
            bot = (ps[1] if len(ps) > 1 and ps[1] else self.rows) - 1
            if 0 <= top < bot < self.rows:
                self.top, self.bottom = top, bot
                self.goto(0, 0)
        elif f == 's' and not priv:
            self.save_cursor()
        elif f == 'u' and not priv:
            self.restore_cursor()
        elif f == 'b':
            if self.last_char:
                self.draw(self.last_char * min(p1, 4096))
        elif f == 'g':
            if p0 == 0:
                self.tabs.discard(self.cx)
            elif p0 == 3:
                self.tabs.clear()
        elif f == 'n':
            if p0 == 6:
                y = self.cy - (self.top if self.origin else 0)
                self.replies.append('\x1b[%d;%dR' % (y + 1, self.cx + 1))
            elif p0 == 5:
                self.replies.append('\x1b[0n')
        elif f == 'c':
            if priv == '>':
                self.replies.append('\x1b[>0;276;0c')
            elif not priv:
                self.replies.append('\x1b[?62;4;22c')  # 4 = sixel
        elif f in 'hl':
            on = f == 'h'
            for p in ps:
                self._mode(priv, p, on)

    def _mode(self, priv, p, on):
        if priv == '?':
            if p == 1:
                self.app_cursor = on
            elif p == 6:
                self.origin = on; self.goto(0, 0)
            elif p == 7:
                self.autowrap = on
            elif p == 25:
                self.cursor_visible = on
            elif p in (47, 1047):
                self.set_alt(on)
            elif p == 1048:
                self.save_cursor() if on else self.restore_cursor()
            elif p == 1049:
                self.set_alt(on, save=True)
                if on:
                    self.cx = self.cy = 0
            elif p == 2004:
                self.bracketed_paste = on
            elif p in (9, 1000, 1002, 1003):
                self.mouse_mode = p if on else 0
            elif p == 1006:
                self.mouse_sgr = on
        elif not priv:
            if p == 4:
                self.insert = on

    def sgr(self, params):
        fg, bg, fl = self.attr
        if not params:
            self.attr = DEFAULT_ATTR
            return
        ps = []
        for grp in params.split(';'):
            if ':' in grp:
                sub = [int(x) if x else 0 for x in grp.split(':')]
                if sub[0] in (38, 48, 58) and len(sub) >= 2:
                    if sub[1] == 2:
                        rgb = sub[-3:] if len(sub) >= 5 else [0, 0, 0]
                        ps.append(('rgb', sub[0], rgb))
                    elif sub[1] == 5 and len(sub) >= 3:
                        ps.append(('idx', sub[0], sub[2]))
                elif sub[0] == 4:
                    ps.append(4 if (len(sub) < 2 or sub[1]) else 24)
                else:
                    ps.append(sub[0])
            else:
                ps.append(int(grp) if grp.isdigit() else 0)
        i, n = 0, len(ps)
        while i < n:
            p = ps[i]
            if isinstance(p, tuple):
                kind, which, v = p
                c = (TRUECOLOR | (v[0] & 255) << 16 | (v[1] & 255) << 8 | (v[2] & 255)) if kind == 'rgb' else v & 255
                if which == 38:
                    fg = c
                elif which == 48:
                    bg = c
            elif p == 0:
                fg, bg, fl = DEFAULT, DEFAULT, 0
            elif p == 1:
                fl |= BOLD
            elif p == 2:
                fl |= DIM
            elif p == 3:
                fl |= ITALIC
            elif p == 4:
                fl |= UNDERLINE
            elif p in (5, 6):
                fl |= BLINK
            elif p == 7:
                fl |= REVERSE
            elif p == 8:
                fl |= HIDDEN
            elif p == 9:
                fl |= STRIKE
            elif p == 21 or p == 24:
                fl &= ~UNDERLINE
            elif p == 22:
                fl &= ~(BOLD | DIM)
            elif p == 23:
                fl &= ~ITALIC
            elif p == 25:
                fl &= ~BLINK
            elif p == 27:
                fl &= ~REVERSE
            elif p == 28:
                fl &= ~HIDDEN
            elif p == 29:
                fl &= ~STRIKE
            elif 30 <= p <= 37:
                fg = p - 30
            elif p == 38 or p == 48:
                c = None
                if i + 2 < n and ps[i + 1] == 5:
                    c = ps[i + 2] & 255
                    i += 2
                elif i + 4 < n and ps[i + 1] == 2:
                    r, g, b = ps[i + 2], ps[i + 3], ps[i + 4]
                    c = TRUECOLOR | (r & 255) << 16 | (g & 255) << 8 | (b & 255)
                    i += 4
                if c is not None:
                    if p == 38:
                        fg = c
                    else:
                        bg = c
            elif p == 39:
                fg = DEFAULT
            elif 40 <= p <= 47:
                bg = p - 40
            elif p == 49:
                bg = DEFAULT
            elif 90 <= p <= 97:
                fg = p - 82
            elif 100 <= p <= 107:
                bg = p - 92
            i += 1
        self.attr = mkattr(fg, bg, fl)

    # ------------------------------------------------------------ view
    def get_view_row(self, y, offset):
        """row y of the visible window when scrolled back by `offset` lines"""
        if offset <= 0 and 0 <= y < self.rows:
            return self.chars[y], self.attrs[y]
        idx = len(self.scrollback) - offset + y
        if idx < 0 or idx >= len(self.scrollback) + self.rows:
            return None
        if idx < len(self.scrollback):
            rc, ra = self.scrollback[idx]
            return rc, ra
        return self.chars[idx - len(self.scrollback)], self.attrs[idx - len(self.scrollback)]

    def text_of_row(self, y, offset=0):
        r = self.get_view_row(y, offset)
        return ''.join(r[0]) if r else ''


# ============================================================================
_TEXT = re.compile(r'[^\x00-\x1f\x7f-\x9f]+')
_CSI = re.compile(r'\x1b\[([0-?]*)([ -/]*)([@-~])')
_CSI_PART = re.compile(r'\x1b\[[0-?]*[ -/]*\Z')
_OSC = re.compile(r'\x1b\]([^\x07\x1b]*)(?:\x07|\x1b\\)')


class Parser:
    def __init__(self, screen: Screen):
        self.s = screen
        self.pending = ''

    def feed(self, data: str):
        if self.pending:
            data = self.pending + data
            self.pending = ''
        s = self.s
        i, n = 0, len(data)
        text_match = _TEXT.match
        csi_match = _CSI.match
        while i < n:
            m = text_match(data, i)
            if m:
                s.draw(m.group())
                i = m.end()
                continue
            c = data[i]
            if c != '\x1b':
                s.control(c)
                i += 1
                continue
            if i + 1 >= n:
                self.pending = data[i:]
                return
            c2 = data[i + 1]
            if c2 == '[':
                m = csi_match(data, i)
                if m:
                    s.csi(m.group(1), m.group(2), m.group(3))
                    i = m.end()
                elif _CSI_PART.match(data, i):
                    if n - i < 512:
                        self.pending = data[i:]
                    return
                else:
                    i += 2
            elif c2 == ']':
                m = _OSC.match(data, i)
                if m:
                    s.osc(m.group(1))
                    i = m.end()
                else:
                    j = data.find('\x07', i)
                    k = data.find('\x1b', i + 2)
                    if j < 0 and k < 0:
                        if n - i < (64 << 20):
                            self.pending = data[i:]
                        return
                    # malformed OSC: skip to whatever terminator we found
                    cands = [x for x in (j, k) if x >= 0]
                    i = min(cands) + (1 if min(cands) == j else 0)
            elif c2 in 'PX^_':
                j = data.find('\x1b\\', i + 2)
                if j < 0:
                    if n - i < (64 << 20):
                        self.pending = data[i:]
                    return
                if c2 == 'P':
                    s.dcs(data[i + 2:j])
                elif c2 == '_':
                    s.apc(data[i + 2:j])
                i = j + 2
            elif c2 in '()*+-./#% ':
                if i + 2 >= n:
                    self.pending = data[i:]
                    return
                c3 = data[i + 2]
                if c2 in '()*+':
                    s.designate(c2, c3)
                elif c2 == '#' and c3 == '8':
                    s.decaln()
                i += 3
            else:
                s.esc(c2)
                i += 2
