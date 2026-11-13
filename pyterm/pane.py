"""A Pane is one terminal session: process + screen + effects + view state.
Tabs hold split trees of panes."""
from __future__ import annotations

import itertools
import json
import math
import random
import re
import time
import webbrowser

import pygame

from . import cursors, signals, vt
from .effects import EffectsManager
from .renderer import Renderer

URL_RE = re.compile(r'(https?://|www\.)[^\s<>"\'`]+[^\s<>"\'`.,;:!?)\]]')
DRAMA_RE = re.compile(r'(?i)\b(error|traceback|fatal|failed|exception|panic)\b')
DRAMA_WORDS = ('error', 'traceback', 'fatal', 'failed', 'exception', 'panic')


def has_drama(data):
    """error-looking output? (substring test first: the regex alone costs milliseconds on big chunks)"""
    low = data.lower()
    return any(w in low for w in DRAMA_WORDS) and DRAMA_RE.search(data) is not None
_ids = itertools.count(1)


class Pane:
    def __init__(self, app, cwd=None, backend=None):
        self.app = app
        self.id = next(_ids)
        cfg = app.cfg
        self.screen = vt.Screen(80, 24, cfg['scrollback'])
        self.parser = vt.Parser(self.screen)
        self.renderer = Renderer(app.font, app.theme, app.gcache)
        self.fx = EffectsManager(self.renderer, app.font, cfg['max_effects'], cfg['max_particles'])
        self.fx.listeners.append(app._on_cell_event)
        self.fx.listeners.append(self._letter_signal)
        self._letters_frame = 0
        self._echo = 0
        self.mine = None
        self.cursor = None          # cursors.CursorStyle (built lazily from the theme)
        self.cursor_fx = []         # cursors.CursorEffect list
        self.cstate = cursors.CursorState()
        self.rect = pygame.Rect(0, 0, 80, 24)
        self.view_offset = 0
        self.view_pos = 0.0
        self.scroll_anim = 0.0
        self.yoff = 0.0
        self._last_total = 0
        self.sel = None
        self.selecting = False
        self.search = None
        self.search_hit = None
        self.cast = None
        self.pending = ''
        self.acc = 0.0
        self.rate = 0.0
        self.energy = 0.0
        self.last_activity = time.time()
        self.dead = False
        self.cwd = cwd
        self.backend = backend if backend is not None else app.make_backend(self, cwd)
        banner = app.theme.get('banner')
        if banner and app.cfg.get('banner', True):
            self.pending += banner.replace('\r\n', '\n').replace('\n', '\r\n')

    # ------------------------------------------------------------ props
    @property
    def title(self):
        t = self.screen.title
        if not t or t == 'pyterm':
            t = getattr(self.backend, 'name', 'term')
            if self.screen.cwd:
                t = self.screen.cwd.rstrip('/\\').replace('\\', '/').split('/')[-1] or self.screen.cwd
        return t

    @property
    def cell(self):
        return self.renderer.cw, self.renderer.ch

    # ------------------------------------------------------------ config
    def set_font(self, font):
        self.renderer.set_font(font)
        self.fx.set_font(font)
        self.reset_cursor()
        if self.mine:
            self.set_miner(False)
            self.set_miner(True)

    def set_theme(self, theme):
        self.renderer.set_theme(theme, self.app.cfg.get('cell_bg_alpha'))
        self.reset_cursor()

    def _letter_signal(self, e):
        """publish printed letters of the focused pane for the scenes (signals.letters)"""
        if e[0] != vt.EV_PUT or self.app.pane is not self or self._letters_frame > 24:
            return
        c = e[3]
        if not c or c == ' ' or self.screen.using_alt:
            return
        self._letters_frame += 1
        cw, ch = self.renderer.cw, self.renderer.ch
        signals.letter_seq += 1
        typed = self._echo > 0 and time.time() - self.last_activity < 0.6   # echo of a key the user pressed
        if typed:
            self._echo -= 1
        signals.letters.append((signals.letter_seq, c, self.rect.x + e[1] * cw + cw / 2, self.rect.y + e[2] * ch + ch / 2, typed))

    # ------------------------------------------------------------ cursor
    def reset_cursor(self):
        self.cursor = None
        self.cursor_fx = []

    def build_cursor(self):
        th = self.app.theme
        params = th.get('cursor_params') or {}
        name = 'miner' if self.mine else (self.app.cfg.get('cursor_style') or th.get('cursor_style', 'block'))
        self.cursor = cursors.make_style(name, self, params)
        fx = self.app.cfg.get('cursor_effects')
        if fx is None:
            fx = th.get('cursor_effects') or []
        if isinstance(fx, str):
            fx = [f for f in fx.split(',') if f]
        self.cursor_fx = cursors.make_effects(fx, self, params)

    @property
    def mcursor(self):
        """the animated character (MinerCursor) of a character style, or None"""
        return getattr(self.cursor, 'mc', None)

    def set_miner(self, on):
        if on and not self.mine:
            from .mine import Mine
            self.mine = Mine(self.fx, self.screen, self.app.sound)
            self.fx.miner = self.mine
        elif not on and self.mine:
            self.mine = None
            self.fx.miner = None
        self.reset_cursor()

    def layout(self, rect, scale):
        cw, ch = self.cell
        cols = max(2, rect.width // cw)
        rows = max(2, rect.height // ch)
        self.rect = pygame.Rect(rect.x, rect.y, cols * cw, rows * ch)
        grid = ((cw * scale, ch * scale), cols, rows)
        if grid != (self.screen.cell_px, self.screen.cols, self.screen.rows):
            self.screen.grid_changed()       # a full-screen sixel picture no longer fits the new grid
        self.screen.cell_px = (cw * scale, ch * scale)
        if (cols, rows) != (self.screen.cols, self.screen.rows):
            self.screen.resize(cols, rows)
            self.backend.resize(cols, rows)
        self.fx.resize(cols, rows)
        if self.mine:
            self.mine.resize(cols, rows)
        self.renderer.full = True

    # ------------------------------------------------------------ io
    def send(self, s):
        if self.view_offset:
            self.view_offset = 0
        self.sel = None
        self.last_activity = time.time()
        self.last_key = self.last_activity
        self.key_cell = (self.screen.cx, self.screen.cy)     # where the echo of this key will appear
        if len(s) == 1 and s.isprintable():
            self._echo = min(8, self._echo + 1)
            signals.key_times.append(time.time())
            signals.keys_total += 1
        elif s:
            self._echo = 0
        if self.cursor:
            self.cursor.wake()
            for e in self.cursor_fx:
                e.wake()
        self.backend.write(s)

    def inject(self, text):
        self.pending += text

    def pump(self, dt):
        app = self.app
        data = self.backend.read()
        if data:
            self.last_activity = time.time()
            data = app.plugins.filter_output(data)
            if self.cast:
                fh, t0, _ = self.cast
                fh.write(json.dumps([round(time.time() - t0, 4), 'o', data]) + '\n')
            if not self.screen.using_alt and has_drama(data):
                if app.theme.get('drama', True):
                    app.drama(0.5)
                if getattr(app, 'mqtt', None):          # error events don't depend on the screen-shake setting
                    app.mqtt.error_output(data)
            self.pending += data
        if not self.pending:
            self.acc = 0
            return 0
        mode = app.writer
        backlog = len(self.pending)
        if mode == 'instant' or self.screen.using_alt or app.zen is not None:
            n = backlog
        elif mode == 'baud':
            self.acc += dt * app.baud / 10.0
            n = int(self.acc)
            self.acc -= n
        elif mode == 'human':
            if backlog > 4000:
                n = backlog // 8
            else:
                self.acc += dt * random.uniform(14, 45) * (1 + backlog / 300)
                n = int(self.acc)
                self.acc -= n
        else:
            cps = max(1800.0, backlog * 6.0)
            self.acc += dt * cps
            n = int(self.acc)
            self.acc -= n
        n = min(n, 1 << 19)
        if n <= 0:
            return 0
        chunk, self.pending = self.pending[:n], self.pending[n:]
        self.parser.feed(chunk)
        return len(chunk)

    # ------------------------------------------------------------ frame
    def update(self, dt, focused):
        app = self.app
        sc = self.screen
        if sc.replies:
            for r in sc.replies:
                self.backend.write(r)
            sc.replies.clear()
        if sc.clip_ops:
            self._clipboard_ops(sc)
        if sc.title_changed and focused:
            sc.title_changed = False
            app.presenter.set_caption(sc.title or 'pyterm')
        evs = sc.take_events()
        alt = sc.using_alt
        theme = app.theme
        appear = app.cfg.get('letter_effect') or theme.get('letter_effect', 'none')
        vanish = app.cfg.get('delete_effect') or theme.get('delete_effect', 'none')
        self.fx.near = None
        if alt:
            # full-screen apps (vim, mc, pytermwm ...): 'typed' animates only what you type - letters at the
            # cursor right after a key press - and never the app's own redraws; true = everything; false = nothing
            mode = app.cfg.get('alt_effects')
            if mode is None:
                mode = theme.get('alt_effects', 'typed')
            mode = {True: 'all', False: 'off', 'true': 'all', 'false': 'off', 'on': 'all'}.get(mode, mode)
            if mode == 'all':
                pass
            elif mode == 'typed' and time.time() - getattr(self, 'last_key', 0) < 0.5:
                kx, ky = getattr(self, 'key_cell', (sc.cx, sc.cy))
                self.fx.near = (kx, ky, 2)
            else:
                appear, vanish = 'none', 'none'
        self.fx.appear_name, self.fx.vanish_name = appear, vanish
        if self.mine is not None:
            self.fx.miner = None if alt else self.mine
        self._letters_frame = 0
        self.fx.process(evs)
        for e in evs:
            if e[0] == vt.EV_CMD:
                app.command_done(self, e[1])
        st = self.fx.stats
        if focused:
            if st['puts']:
                signals.typing = time.time()
                signals.puts += st['puts']
            if st['nl']:
                signals.enter = time.time()
            if st['bell']:
                signals.bell = time.time()
        app.sound.on_frame(st) if focused or st['bell'] else None
        if st['bell']:
            app.post.flash = max(app.post.flash, 0.4)
            app.post.flash_rgb = (255, 255, 255)
            app.plugins.emit('bell')
            app.show_event('bell')
        r = (st['puts'] + st['dels']) / max(dt, 1e-3)
        self.rate += (r - self.rate) * min(1.0, dt * 3)
        self.energy = min(2.0, self.rate / 2500.0)
        # smooth scrolling
        d = sc.total_scrolled - self._last_total
        self._last_total = sc.total_scrolled
        maxl = int(app.cfg.get('smooth_scroll_lines', 3) or 0)
        ch = self.renderer.ch
        if d > 0 and maxl and not alt and self.view_offset == 0 and app.zen is None:
            if d <= maxl:
                self.scroll_anim = min(self.scroll_anim + d * ch, maxl * ch)
            else:
                self.scroll_anim = 0.0
        if self.scroll_anim > 0:
            self.scroll_anim *= math.exp(-dt * 16)
            if self.scroll_anim < 0.4:
                self.scroll_anim = 0.0
        tgt = float(self.view_offset)
        if self.view_pos != tgt:
            if not app.cfg.get('smooth_scroll_lines', 3):
                self.view_pos = tgt
            else:
                self.view_pos += (tgt - self.view_pos) * (1 - math.exp(-dt * 18))
                if abs(self.view_pos - tgt) < 0.03:
                    self.view_pos = tgt
        # cursor style + effects
        if self.cursor is None:
            self.build_cursor()
        cs = self.cstate
        cw = self.renderer.cw
        cs.cx, cs.cy = sc.cx, sc.cy
        x, y = sc.cx * cw, sc.cy * ch
        cs.moved = (x, y) != (cs.x, cs.y)
        cs.x, cs.y, cs.cw, cs.ch = x, y, cw, ch
        cs.voff = self.fx.voff
        cs.typed, cs.newline, cs.bell = st['puts'], bool(st['nl']), bool(st['bell'])
        cs.focused, cs.alt, cs.eco = focused, alt, bool(app.eco)
        cs.visible = sc.cursor_visible and self.view_offset == 0
        cs.t, cs.dt = app.t, dt
        cs.rgb = self.renderer.cursor_rgb
        cs.screen, cs.mine = sc, self.mine
        if focused:
            signals.cursor_x = self.rect.x + x + cw / 2
            signals.cursor_y = self.rect.y + y
        cvis = self.cursor.visible(cs)
        if cvis or self.mine:
            self.cursor.update(dt, cs)
        if app.zen is None:
            for e in self.cursor_fx:
                if not alt or e.active_in_alt:
                    e.update(dt, cs)
        self.fx.update(dt)
        if self.mine:
            self.mine.update(dt, self.mcursor if cvis else None)
            if self.mine.flash > 0.05:
                app.post.flash = max(app.post.flash, self.mine.flash * 0.8)
                app.post.flash_rgb = (255, 140, 30)
            app.shake = max(app.shake, self.mine.shake)
        self.renderer.set_blink(int(app.t * 2) % 2 == 0)
        self.renderer.set_anim(app.t)
        if not self.backend.alive and not self.backend.q.qsize() and not self.pending:
            self.dead = True

    def animating(self):
        return bool(self.pending or self.fx.active or self.fx.particles.n or self.scroll_anim
                    or (self.mine and self.mine.pending) or (self.cursor and self.cursor.busy())
                    or any(e.busy() for e in self.cursor_fx)
                    or self.view_pos != self.view_offset)

    def slow_anim(self):
        """animated emoji / animated font on screen: needs frames, but only ~8-10 per second"""
        return bool(self.renderer.anim_rows or self.renderer.font.animated)

    def needs_render(self):
        s = self.screen
        return bool(s.dirty or s.full_dirty or s.scroll_ops or self.renderer.full or self.renderer.extra_dirty)

    # ------------------------------------------------------------ render
    def render(self, vs, focused, t):
        app = self.app
        sc = self.screen
        r = self.rect
        cw, ch = self.cell
        k = int(math.floor(self.view_pos + 1e-6))
        frac = self.view_pos - k
        self.yoff = yoff = self.scroll_anim + frac * ch
        iy = int(round(yoff))
        alt = sc.using_alt
        clip = vs.get_clip()
        vs.set_clip(r)
        if self.mine and not alt:
            self.mine.draw_world(vs, r.x, r.y + iy)
        hidden = self.fx.hidden_rows(self.renderer)
        self.renderer.render(sc, hidden, k)
        vs.blit(self.renderer.tsurf, (r.x, r.y + iy))
        if iy > 0:
            n = -(-iy // ch)
            extra = self.renderer.render_extra(sc, k, n)
            vs.blit(extra, (r.x, r.y + iy - n * ch))
        if not self.view_offset and k == 0:
            vs.set_clip(r.inflate(cw * 4, ch * 4).clip(clip) if clip else r.inflate(cw * 4, ch * 4))
            self.fx.draw(vs, r.x, r.y + iy)
            vs.set_clip(r)
            self._draw_cursor(vs, r, iy, clip)
        if self.sel:
            self.renderer.draw_selection(vs, r.x, r.y + iy, self.sel, sc.cols)
        vs.set_clip(clip)
        self._draw_marks(vs, k, iy)
        self._overlays(vs)
        if not focused and len(app.tab.panes()) > 1 and app.cfg.get('dim_inactive', True):
            dim = pygame.Surface(r.size)
            dim.fill((205, 205, 205))
            vs.blit(dim, r.topleft, special_flags=pygame.BLEND_RGB_MULT)

    def _draw_cursor(self, vs, r, iy, clip):
        app = self.app
        cs = self.cstate
        if app.intro or self.cursor is None:
            return
        cw, ch = self.cell
        vs.set_clip(r.inflate(cw * 4, ch * 3).clip(clip) if clip else r.inflate(cw * 4, ch * 3))
        ox, oy = r.x, r.y + iy
        fx = [e for e in self.cursor_fx if app.zen is None and (not cs.alt or e.active_in_alt)]
        vis = self.cursor.visible(cs)
        if vis:
            for e in fx:
                if e.layer == 'under':
                    e.draw(vs, ox, oy, cs)
            self.cursor.draw(vs, ox, oy, cs)
        for e in fx:
            if e.layer != 'under':
                e.draw(vs, ox, oy, cs)
        vs.set_clip(r)

    def _draw_marks(self, vs, k, iy):
        sc = self.screen
        if not sc.marks or sc.using_alt or not self.app.cfg.get('command_blocks', True) \
                or self.app.theme.get('command_blocks') is False:
            return
        r = self.rect
        ch = self.renderer.ch
        base = sc.total_scrolled - k
        cur_line = sc.abs_line()
        gx = r.x - 4
        mouse = self.app.mouse_v
        tip = None
        for m in reversed(sc.marks):
            start = m['prompt'] - base
            if start >= sc.rows:
                continue
            end_line = m['end'] if m['end'] is not None else cur_line
            end = end_line - base
            if end < 0:
                break
            if m['exit'] is None:
                col = (70, 150, 255) if m['out'] is not None else (90, 90, 110)
            else:
                col = (70, 220, 110) if m['exit'] == 0 else (255, 70, 70)
            y0 = r.y + iy + max(0, start) * ch
            y1 = r.y + iy + min(sc.rows, max(end, start) + 1) * ch
            if y1 > y0:
                vs.fill(col, (gx, y0 + 1, 2, y1 - y0 - 2))
            if 0 <= start < sc.rows and start > 0:
                vs.fill((40, 44, 60), (r.x, r.y + iy + start * ch, r.width, 1), special_flags=pygame.BLEND_RGB_ADD)
            if mouse and gx - 3 <= mouse[0] <= gx + 4 and y0 <= mouse[1] < y1:
                tip = m
        if tip:
            dur = (tip['t1'] or time.time()) - tip['t0'] if tip['t0'] else 0
            st = 'running' if tip['exit'] is None else ('ok' if tip['exit'] == 0 else 'exit %d' % tip['exit'])
            text = '%s  %.1fs  %s' % (st, dur, tip['cmdline'][:40])
            self.app.tooltip = (text, mouse)

    def _overlays(self, vs):
        app = self.app
        cw, ch = self.cell
        r = self.rect
        if self.view_offset:
            t = ' SCROLLBACK -%d ' % self.view_offset
            app.draw_text(vs, r.right - len(t) * cw, r.bottom - ch, t, (255, 220, 80))
        if self.cast and int(app.t * 2) % 2:
            app.draw_text(vs, r.x + cw, r.y, '● REC', (255, 60, 60))
        if self.mine and not self.screen.using_alt:
            t = self.mine.hud()
            rr = pygame.Rect(r.right - (len(t) + 2) * cw, r.top, (len(t) + 2) * cw, ch + 4)
            app.panel(vs, rr, 150)
            app.draw_text(vs, rr.x + cw, rr.y + 2, t, (120, 255, 150))
        if self.search is not None:
            t = 'search: ' + self.search + '_   (Enter = previous match, Esc = close)'
            rr = pygame.Rect(r.x, r.bottom - ch - 4, r.width, ch + 4)
            app.panel(vs, rr, 220)
            app.draw_text(vs, rr.x + cw, rr.y + 2, t, (255, 255, 255))

    def image_rects(self, dst, s):
        """yield (image, window_rect, window_clip) for crisp inline images"""
        sc = self.screen
        if not sc.images:
            return
        cw, ch = self.cell
        k = int(math.floor(self.view_pos + 1e-6))
        base = sc.total_scrolled - k
        clip = pygame.Rect(dst.x + self.rect.x * s, dst.y + self.rect.y * s, self.rect.w * s, self.rect.h * s)
        for im in sc.images:
            if im['alt'] != sc.using_alt:
                continue
            row = im['line'] - base
            if row + im['rows'] < 0 or row >= sc.rows:
                continue
            x = dst.x + (self.rect.x + im['col'] * cw) * s
            y = dst.y + int((self.rect.y + row * ch + self.yoff) * s)
            w, h = im['surf'].get_size()
            cwp, chp = cw * s, ch * s
            if w > im['cols'] * cwp + 1 or h > im['rows'] * chp + 1 or im.get('fit'):
                kk = min(im['cols'] * cwp / w, im['rows'] * chp / h)
                w, h = max(1, int(w * kk)), max(1, int(h * kk))
            yield im, pygame.Rect(x, y, w, h), clip

    # ------------------------------------------------------------ interaction
    def cell_at(self, vpos):
        cw, ch = self.cell
        x = (vpos[0] - self.rect.x) // cw
        y = (vpos[1] - self.rect.y - int(self.yoff)) // ch
        return (min(self.screen.cols - 1, max(0, x)), min(self.screen.rows - 1, max(0, y)))

    def scroll_view(self, n):
        sb = len(self.screen.scrollback)
        nv = min(sb, max(0, self.view_offset + n))
        if nv != self.view_offset:
            self.view_offset = nv

    def selection_text(self):
        if not self.sel:
            return ''
        (x0, y0), (x1, y1) = self.sel
        if (y1, x1) < (y0, x0):
            (x0, y0), (x1, y1) = (x1, y1), (x0, y0)
        lines = []
        for y in range(y0, y1 + 1):
            t = self.screen.text_of_row(y, self.view_offset)
            a = x0 if y == y0 else 0
            b = x1 + 1 if y == y1 else len(t)
            lines.append(t[a:b].rstrip())
        return '\n'.join(lines)

    def paste_text(self, t):
        if not t:
            return
        t = t.replace('\r\n', '\r').replace('\n', '\r').replace('\x00', '')
        if self.screen.bracketed_paste:
            t = '\x1b[200~' + t.replace('\x1b[201~', '') + '\x1b[201~'
        if len(t) <= 1024:
            self.send(t)
            return
        self.send(t[:1024])                 # big pastes in pieces: ConPTY / small pty buffers drop input otherwise
        for i in range(1024, len(t), 1024):
            self.backend.write(t[i:i + 1024])

    def _clipboard_ops(self, sc):
        """OSC 52: programs inside the terminal set (and, if allowed, read) the system clipboard"""
        from .app import clip_get, clip_put
        import base64
        mode = str(self.app.cfg.get('osc52', 'write')).lower()
        for op, v in sc.clip_ops:
            if op == 'set' and mode in ('write', 'read-write', 'true'):
                clip_put(v)
                if v:
                    self.app.notify('clipboard: %d chars from %s' % (len(v), (sc.title or 'program')[:30]), 1.2)
            elif op == 'get':
                # reading is opt-in (osc52: read-write): any output, e.g. a cat-ed file, could ask. Otherwise answer
                # with an empty clipboard, so asking programs (pytermwm, nvim) don't wait for a reply that never comes.
                text = clip_get() or '' if mode == 'read-write' else ''
                data = base64.b64encode(text.encode('utf-8')).decode('ascii')
                self.backend.write('\x1b]52;%s;%s\x1b\\' % (v, data))
        sc.clip_ops.clear()

    def open_url(self, cell):
        x, y = cell
        t = self.screen.text_of_row(y, self.view_offset)
        for m in URL_RE.finditer(t):
            if m.start() <= x < m.end():
                url = m.group()
                if url.startswith('www.'):
                    url = 'http://' + url
                webbrowser.open(url)
                self.app.notify('opening %s' % url[:60])
                return True
        return False

    def do_search(self):
        q = (self.search or '').lower()
        if not q:
            return
        sc = self.screen
        sb = len(sc.scrollback)
        total = sb + sc.rows
        start = self.search_hit[0] - 1 if self.search_hit else total - 1
        for i in range(start, -1, -1):
            t = ''.join(sc.scrollback[i][0]) if i < sb else ''.join(sc.chars[i - sb])
            j = t.lower().find(q)
            if j >= 0:
                self.search_hit = (i, j)
                self.view_offset = min(sb, max(0, total - i - sc.rows // 2 - 1)) if i < sb else 0
                return
        self.app.notify('not found: %s' % self.search, 1.5)
        self.search_hit = None

    def _line_text(self, abs_line):
        sc = self.screen
        y = abs_line - sc.total_scrolled
        if 0 <= y < sc.rows:
            return ''.join(sc.chars[y])
        idx = len(sc.scrollback) + y
        if 0 <= idx < len(sc.scrollback):
            return ''.join(sc.scrollback[idx][0])
        return None

    def jump_prompt(self, direction):
        sc = self.screen
        if not sc.marks:
            self.app.notify('no command marks - enable shell integration (docs/SHELL.md)', 2)
            return
        top_line = sc.total_scrolled - self.view_offset
        prompts = [m['prompt'] for m in sc.marks]
        if direction < 0:
            cands = [p for p in prompts if p < top_line]
            target = cands[-1] if cands else None
        else:
            cands = [p for p in prompts if p > top_line]
            target = cands[0] if cands else None
        if target is None:
            if direction > 0:
                self.view_offset = 0
            return
        off = sc.total_scrolled - target
        self.view_offset = min(len(sc.scrollback), max(0, off))

    def last_output(self):
        sc = self.screen
        for m in reversed(sc.marks):
            if m['out'] is not None and m['end'] is not None:
                lines = [self._line_text(l) for l in range(m['out'], m['end'])]
                return '\n'.join(l.rstrip() for l in lines if l is not None).rstrip('\n'), m
        return None, None

    def toggle_cast(self, directory):
        import os
        if self.cast:
            self.cast[0].close()
            p = self.cast[2]
            self.cast = None
            return False, p
        os.makedirs(directory, exist_ok=True)
        p = os.path.join(directory, time.strftime('pyterm-%Y%m%d-%H%M%S.cast'))
        fh = open(p, 'w', encoding='utf-8')
        fh.write(json.dumps({'version': 2, 'width': self.screen.cols, 'height': self.screen.rows,
                             'timestamp': int(time.time()), 'title': 'pyterm',
                             'env': {'TERM': 'xterm-256color'}}) + '\n')
        self.cast = (fh, time.time(), p)
        return True, p

    def close(self):
        if self.cast:
            self.cast[0].close()
            self.cast = None
        try:
            self.backend.close()
        except Exception:
            pass
