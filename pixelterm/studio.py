"""pixelterm Studio - theme, pixel-font and plugin editor docked next to the
running terminal. Every change is applied live; the terminal *is* the preview.

Tabs:  THEME   - every theme key: colors, effects, backgrounds, CRT, sound ... -> YAML
       FONT    - pixel glyph editor (paint / erase / shift / invert / copy) -> PNG sheet + YAML
       PLUGINS - enable/disable, scaffold new plugin, open in editor, errors, hot reload
       CONSOLE - plugin + app log
"""
from __future__ import annotations

import os
import subprocess
import sys

import numpy as np
import pygame

from . import backgrounds, effects, fonts, themes
from .themes import hex2rgb


def rgb2hex(c):
    return '#%02x%02x%02x' % tuple(int(v) for v in c[:3])


def open_in_editor(path):
    try:
        if sys.platform.startswith('win'):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        else:
            ed = os.environ.get('VISUAL') or os.environ.get('EDITOR')
            if ed and os.environ.get('DISPLAY') is None:
                subprocess.Popen([ed, path])
            else:
                subprocess.Popen(['xdg-open', path])
    except Exception as e:
        print('[studio] cannot open %s: %s' % (path, e))


# ============================================================================ tiny immediate-mode UI
class UI:
    BG = (16, 18, 26)
    FG = (215, 220, 235)
    DIM = (120, 128, 150)
    ACC = (90, 200, 255)
    HOT = (255, 200, 60)
    ERR = (255, 90, 90)
    WIDGET = (34, 38, 52)
    WIDGET_HI = (52, 58, 80)

    def __init__(self):
        path = fonts.fallback().path
        self.font = pygame.font.Font(path, 13)
        self.big = pygame.font.Font(path, 16)
        self.lh = 20
        self.mouse = (0, 0)
        self.click = None
        self.rclick = None
        self.down = False
        self.rdown = False
        self.wheel = 0
        self.focus = None
        self.typed = []
        self.drag = None
        self._tcache = {}

    def text(self, s, c=None, big=False):
        key = (s, c, big)
        t = self._tcache.get(key)
        if t is None:
            if len(self._tcache) > 3000:
                self._tcache.clear()
            t = (self.big if big else self.font).render(s, True, c or self.FG)
            self._tcache[key] = t
        return t

    def begin(self, surf, rect, scroll):
        self.surf = surf
        self.rect = rect
        self.x0 = rect.x + 10
        self.x = self.x0
        self.y = rect.y + 8 - scroll
        self.w = rect.width - 20
        self.max_y = self.y

    def end(self):
        self.click = None
        self.rclick = None
        self.wheel = 0
        self.typed = []
        return self.y

    def hit(self, r):
        return r.collidepoint(self.mouse) and self.rect.collidepoint(self.mouse)

    def clicked(self, r):
        return self.click is not None and r.collidepoint(self.click) and self.rect.collidepoint(self.click)

    def newline(self, h=None):
        self.y += h or self.lh
        self.x = self.x0

    def label(self, s, c=None, big=False, w=None):
        t = self.text(s, c, big)
        self.surf.blit(t, (self.x, self.y + 2))
        self.x += (w if w is not None else t.get_width() + 8)

    def header(self, s):
        self.newline(6)
        self.surf.fill((40, 46, 70), (self.rect.x + 4, self.y, self.rect.width - 8, self.lh))
        self.surf.blit(self.text(s, self.HOT), (self.x0, self.y + 2))
        self.newline()

    def button(self, s, w=None, color=None):
        t = self.text(s, color)
        w = w or t.get_width() + 14
        r = pygame.Rect(self.x, self.y + 1, w, self.lh - 2)
        hot = self.hit(r)
        pygame.draw.rect(self.surf, self.WIDGET_HI if hot else self.WIDGET, r, border_radius=3)
        pygame.draw.rect(self.surf, self.ACC if hot else (60, 66, 90), r, 1, border_radius=3)
        self.surf.blit(t, (r.x + (w - t.get_width()) // 2, r.y + 2))
        self.x += w + 6
        return self.clicked(r)

    def toggle(self, s, v, w=None):
        r = pygame.Rect(self.x, self.y + 3, 14, 14)
        pygame.draw.rect(self.surf, self.WIDGET, r)
        pygame.draw.rect(self.surf, self.ACC, r, 1)
        if v:
            self.surf.fill(self.ACC, r.inflate(-6, -6))
        t = self.text(s)
        self.surf.blit(t, (r.right + 6, self.y + 2))
        full = pygame.Rect(self.x, self.y, (w or t.get_width() + 30), self.lh)
        self.x += w or t.get_width() + 30
        return (not v) if self.clicked(full) else v

    def cycle(self, s, v, opts, lw=110):
        self.label(s, self.DIM, w=lw)
        opts = list(opts)
        if self.button('◄', 22):
            v = opts[(opts.index(v) - 1) % len(opts)] if v in opts else opts[0]
        t = self.text(str(v), self.FG)
        r = pygame.Rect(self.x, self.y, max(120, t.get_width() + 10), self.lh)
        self.surf.blit(t, (r.x + 4, r.y + 2))
        self.x = r.right + 4
        if self.button('►', 22) or self.clicked(r):
            v = opts[(opts.index(v) + 1) % len(opts)] if v in opts else opts[0]
        return v

    def slider(self, sid, s, v, lo, hi, lw=110, fmt='%.2f', integer=False):
        self.label(s, self.DIM, w=lw)
        w = self.w - lw - 60
        r = pygame.Rect(self.x, self.y + 6, w, 8)
        pygame.draw.rect(self.surf, self.WIDGET, r, border_radius=4)
        k = 0 if hi == lo else (float(v) - lo) / (hi - lo)
        k = max(0.0, min(1.0, k))
        pygame.draw.rect(self.surf, self.ACC, (r.x, r.y, int(w * k), 8), border_radius=4)
        pygame.draw.circle(self.surf, self.HOT, (r.x + int(w * k), r.centery), 6)
        grab = r.inflate(10, 12)
        if self.click and grab.collidepoint(self.click) and self.rect.collidepoint(self.click):
            self.drag = sid
        if self.drag == sid:
            if self.down:
                k = max(0.0, min(1.0, (self.mouse[0] - r.x) / max(1, w)))
                v = lo + (hi - lo) * k
                if integer:
                    v = int(round(v))
                else:
                    v = round(v, 3)
            else:
                self.drag = None
        self.surf.blit(self.text(fmt % v), (r.right + 8, self.y + 2))
        self.newline()
        return v

    def swatch(self, rgb, size=18, sel=False):
        r = pygame.Rect(self.x, self.y + 1, size, size)
        self.surf.fill(rgb, r)
        pygame.draw.rect(self.surf, self.HOT if sel else (80, 80, 100), r, 2 if sel else 1)
        self.x += size + 4
        return self.clicked(r)

    def textfield(self, fid, v, w=160):
        r = pygame.Rect(self.x, self.y + 1, w, self.lh - 2)
        foc = self.focus == fid
        pygame.draw.rect(self.surf, (10, 10, 16), r)
        pygame.draw.rect(self.surf, self.HOT if foc else (70, 76, 100), r, 1)
        if self.clicked(r):
            self.focus = fid
            foc = True
        elif self.click and self.focus == fid and not r.collidepoint(self.click):
            self.focus = None
        if foc:
            for k in self.typed:
                if k == '\b':
                    v = v[:-1]
                elif k in ('\r', '\x1b'):
                    self.focus = None
                else:
                    v += k
        t = self.text(v + ('_' if foc else ''))
        self.surf.set_clip(r.inflate(-4, 0))
        self.surf.blit(t, (r.x + 4, r.y + 2))
        self.surf.set_clip(None)
        self.x += w + 6
        return v


# ============================================================================ studio
class Studio:
    width = 470
    TABS = ['THEME', 'FONT', 'PLUGINS', 'CONSOLE']

    def __init__(self, app):
        self.app = app
        self.ui = UI()
        self.tab = 'THEME'
        self.scroll = {t: 0 for t in self.TABS}
        self.color_target = 'fg'
        self.saveas = ''
        self.newplug = ''
        self.glyph = 'A'
        self.clip = None
        self.newcell = [8, 16]
        self.fontname = ''
        self.sample = 'The quick brown fox 0123 ÄÖÜß ╔═╗░▒▓█ <>{}'
        self.msg = ''
        self.dirty = False
        self.paint = None
        self.hexbuf = ''

    # ------------------------------------------------------------ events
    def handle(self, ev):
        W, H = self.app.presenter.size()
        rect = pygame.Rect(W - self.width, 0, self.width, H)
        ui = self.ui
        if ev.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL):
            pos = pygame.mouse.get_pos() if ev.type == pygame.MOUSEWHEEL else ev.pos
            ui.mouse = pos
            inside = rect.collidepoint(pos)
            if ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 1:
                    ui.down = inside
                    if inside:
                        ui.click = pos
                elif ev.button == 3:
                    ui.rdown = inside
                    if inside:
                        ui.rclick = pos
                if not inside:
                    ui.focus = None
            elif ev.type == pygame.MOUSEBUTTONUP:
                if ev.button == 1:
                    was = ui.down
                    ui.down = False
                    self.paint = None
                    if was:
                        return True
                if ev.button == 3:
                    ui.rdown = False
                    self.paint = None
            elif ev.type == pygame.MOUSEWHEEL and inside:
                self.scroll[self.tab] = max(0, self.scroll[self.tab] - ev.y * 40)
            return inside or ui.down or ui.drag is not None
        if ev.type == pygame.KEYDOWN and ui.focus:
            if ev.key == pygame.K_BACKSPACE:
                ui.typed.append('\b')
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                ui.typed.append('\r')
            return True
        if ev.type == pygame.TEXTINPUT and ui.focus:
            ui.typed.append(ev.text)
            return True
        if ev.type == pygame.TEXTINPUT and self.tab == 'FONT' and rect.collidepoint(pygame.mouse.get_pos()):
            self.glyph = ev.text[:1]
            return True
        return False

    def update(self, dt):
        pass

    # ------------------------------------------------------------ draw
    def draw(self, win, rect, offset=(0, 0)):
        ui = self.ui
        ox, oy = offset
        real = (ui.mouse, ui.click, ui.rclick)
        ui.mouse = (ui.mouse[0] - ox, ui.mouse[1] - oy)
        ui.click = (ui.click[0] - ox, ui.click[1] - oy) if ui.click else None
        ui.rclick = (ui.rclick[0] - ox, ui.rclick[1] - oy) if ui.rclick else None
        try:
            self._draw(win, rect)
        finally:
            ui.mouse = real[0]

    def _draw(self, win, rect):
        ui = self.ui
        win.fill(UI.BG, rect)
        pygame.draw.line(win, UI.ACC, rect.topleft, rect.bottomleft, 2)
        # title + tabs
        win.blit(ui.text('PIXELTERM STUDIO', UI.HOT, True), (rect.x + 10, rect.y + 8))
        win.blit(ui.text('live preview ->  terminal on the left', UI.DIM), (rect.x + 170, rect.y + 11))
        tx = rect.x + 10
        for t in self.TABS:
            tt = ui.text(t, UI.BG if t == self.tab else UI.FG)
            r = pygame.Rect(tx, rect.y + 34, tt.get_width() + 20, 22)
            pygame.draw.rect(win, UI.ACC if t == self.tab else UI.WIDGET, r, border_radius=4)
            win.blit(tt, (r.x + 10, r.y + 3))
            if ui.click and r.collidepoint(ui.click):
                self.tab = t
                ui.click = None
            tx = r.right + 6
        body = pygame.Rect(rect.x, rect.y + 62, rect.width, rect.height - 62 - 22)
        win.set_clip(body)
        ui.begin(win, body, self.scroll[self.tab])
        try:
            getattr(self, 'tab_' + self.tab.lower())()
        except Exception as e:  # never kill the terminal
            import traceback
            self.msg = 'studio error: %s' % e
            traceback.print_exc()
        end = ui.end()
        win.set_clip(None)
        content_h = end + self.scroll[self.tab] - body.y
        self.scroll[self.tab] = min(self.scroll[self.tab], max(0, content_h - body.height + 20))
        # status line
        win.fill((10, 10, 16), (rect.x, rect.bottom - 22, rect.width, 22))
        win.blit(ui.text(self.msg[:70], UI.HOT if self.msg else UI.DIM), (rect.x + 10, rect.bottom - 19))

    # ------------------------------------------------------------ THEME
    def _apply(self):
        app = self.app
        for k in ('background', 'letter_effect', 'delete_effect', 'writer', 'baud', 'miner'):
            app.cfg[k] = None
        app.apply_theme(app.theme)
        self.dirty = True

    def tab_theme(self):
        ui, app = self.ui, self.app
        th = app.theme
        names = list(themes.list_themes())
        ui.label('theme', UI.DIM, w=60)
        if ui.button('◄', 22) and names:
            self._load(names[(names.index(th['name']) - 1) % len(names)] if th['name'] in names else names[0])
            th = app.theme
        ui.label(th['name'] + (' *' if self.dirty else ''), UI.HOT, w=150)
        if ui.button('►', 22) and names:
            self._load(names[(names.index(th['name']) + 1) % len(names)] if th['name'] in names else names[0])
            th = app.theme
        if ui.button('Save'):
            p = themes.save_theme(th)
            app._watch_file('theme', p)
            self.dirty = False
            self.msg = 'saved %s' % p
        ui.newline()
        ui.label('save as', UI.DIM, w=60)
        self.saveas = ui.textfield('saveas', self.saveas, 170)
        if ui.button('Save as') and self.saveas.strip():
            th['name'] = self.saveas.strip()
            p = themes.save_theme(th, os.path.join(themes.THEME_DIR, th['name'] + '.yaml'))
            app._watch_file('theme', p)
            self.dirty = False
            self.msg = 'created %s' % p
        if ui.button('Revert'):
            self._load(th['name'])
        ui.newline()
        if ui.button('Preview: demo content'):
            from . import demo
            app.inject('\r\n' + demo.boxes() + demo.color_table() + demo.ansi_art(48, 6))
        if ui.button('Open YAML') and th.get('_path'):
            open_in_editor(th['_path'])
        ui.newline()
        th['description'] = self._text_row('description', 'desc', th.get('description', ''))

        ui.header('COLORS  (click a swatch, then edit)')
        for key in ('fg', 'bg', 'cursor', 'border_color'):
            ui.label(key, UI.DIM, w=90)
            if ui.swatch(hex2rgb(th.get(key, '#000000')), sel=self.color_target == key):
                self.color_target = key
            ui.x += 4
            if key in ('bg', 'border_color'):
                ui.newline()
        ui.newline()
        ui.label('palette', UI.DIM, w=90)
        pal = th['palette']
        for i in range(16):
            if i == 8:
                ui.newline()
                ui.x += 90
            if ui.swatch(hex2rgb(pal[i]), sel=self.color_target == i):
                self.color_target = i
        ui.newline()
        self._color_editor(th)

        ui.header('LETTER EFFECTS')
        v = ui.cycle('appear', th.get('letter_effect', 'none'), list(effects.APPEAR))
        if v != th.get('letter_effect'):
            th['letter_effect'] = v
            self._apply()
        ui.newline()
        v = ui.cycle('delete', th.get('delete_effect', 'none'), list(effects.VANISH))
        if v != th.get('delete_effect'):
            th['delete_effect'] = v
            self._apply()
        ui.newline()
        cur = th.get('alt_effects', 'typed') in (True, 'all', 'true', 'on')
        v = ui.toggle('all effects in full-screen apps (vim, mc...; off = typed letters only)', cur)
        if v != cur:
            th['alt_effects'] = 'all' if v else 'typed'
            self._apply()
        ui.newline()
        v = ui.toggle('drama (shake/flash on errors)', th.get('drama', True))
        if v != th.get('drama', True):
            th['drama'] = v
            self._apply()
        ui.newline()

        ui.header('BACKGROUND LAYERS  (stacked in click order)')
        cur = list(th.get('background') or [])
        names = list(backgrounds.BACKGROUNDS)
        for i, n in enumerate(names):
            on = n in cur
            nv = ui.toggle(('%d ' % (cur.index(n) + 1) if on else '') + n, on, w=140)
            if nv != on:
                cur = cur + [n] if nv else [x for x in cur if x != n]
                th['background'] = cur
                self._apply()
            if i % 3 == 2:
                ui.newline()
        ui.newline()
        v = ui.slider('bgdim', 'bg brightness', float(th.get('bg_dim', 0.4)), 0, 1)
        if v != th.get('bg_dim'):
            th['bg_dim'] = v
            self._apply()
        v = ui.slider('bga', 'text bg alpha', int(th.get('bg_alpha', 255)), 0, 255, fmt='%d', integer=True)
        if v != th.get('bg_alpha'):
            th['bg_alpha'] = v
            self._apply()
        cur = th.get('cell_bg_alpha')
        cur = int(cur) if cur is not None else (255 if int(th.get('bg_alpha', 255)) >= 255 else 170)
        v = ui.slider('cba', 'colored cell alpha (mc, htop)', cur, 0, 255, fmt='%d', integer=True)
        if v != cur:
            th['cell_bg_alpha'] = v
            self._apply()
        v = ui.toggle('EMERALD MINE mode', th.get('miner', False))
        if v != th.get('miner', False):
            th['miner'] = v
            self._apply()
        ui.newline()

        ui.header('TEXT & CURSOR')
        for key, lab in (('text_shadow', 'text shadow'), ('bold_bright', 'bold = bright')):
            v = ui.toggle(lab, th.get(key, False), w=140)
            if v != th.get(key):
                th[key] = v
                self._apply()
        ui.newline()
        from . import cursors
        v = ui.cycle('cursor', th.get('cursor_style', 'block'), list(cursors.CURSORS))
        if v != th.get('cursor_style'):
            th['cursor_style'] = v
            self._apply()
        ui.newline()
        fx = list(th.get('cursor_effects') or [])
        ui.label('cursor effects')
        ui.newline()
        for i, name in enumerate(cursors.CURSOR_EFFECTS):
            if i and i % 3 == 0:
                ui.newline()
            v = ui.toggle(name, name in fx, w=140)
            if v != (name in fx):
                fx = [f for f in fx if f != name] + ([name] if v else [])
                th['cursor_effects'] = fx
                self._apply()
        ui.newline()
        v = ui.slider('border', 'border px', int(th.get('border', 6)), 0, 60, fmt='%d', integer=True)
        if v != th.get('border'):
            th['border'] = v
            self._apply()
        v = ui.cycle('border fx', th.get('border_fx', 'none'), ['none', 'c64', 'rainbow'])
        if v != th.get('border_fx'):
            th['border_fx'] = v
            self._apply()
        ui.newline()

        ui.header('FONT')
        fl = fonts.list_fonts()
        curf = th.get('font') or 'builtin'
        if curf not in fl:
            fl.append(curf)
        v = ui.cycle('font', curf, fl)
        if v != curf:
            th['font'] = v
            app.font_override = None
            self._apply()
        ui.newline()
        v = ui.slider('fsize', 'size (ttf)', int(th.get('font_size', 18)), 6, 48, fmt='%d', integer=True)
        if v != th.get('font_size'):
            th['font_size'] = v
            self._apply()
        v = ui.toggle('antialias (ttf)', th.get('antialias', True))
        if v != th.get('antialias'):
            th['antialias'] = v
            app._font_size = None
            app.font = app._load_font_for(th)
            app.set_font(app.font)
            self.dirty = True
        ui.newline()
        sc = th.get('scale') or 'auto'
        v = ui.cycle('pixel scale', sc, ['auto', 1, 2, 3, 4, 5])
        if v != sc:
            th['scale'] = None if v == 'auto' else v
            app.cfg['scale'] = None
            self._apply()
        ui.newline()

        ui.header('WRITER (output pacing)')
        w = th.setdefault('writer', {})
        v = ui.cycle('mode', w.get('mode', 'smart'), ['smart', 'instant', 'baud', 'human'])
        if v != w.get('mode'):
            w['mode'] = v
            self._apply()
        ui.newline()
        v = ui.cycle('baud', w.get('baud', 9600), [300, 1200, 2400, 9600, 19200, 57600, 115200])
        if v != w.get('baud'):
            w['baud'] = v
            self._apply()
        ui.newline()

        ui.header('PALETTE LOCK (retro console colors)')
        lock = th.get('palette_lock') or {}
        on = ui.toggle('lock to %d colors' % len(lock.get('colors', [])) if lock.get('colors') else 'lock (define colors in YAML)',
                       bool(lock.get('colors')) and not lock.get('off'), w=260)
        if lock.get('colors') and on == bool(lock.get('off')):
            lock['off'] = not on
            th['palette_lock'] = lock
            app.post.configure(th['crt'], None if lock.get('off') else lock)
            self.dirty = True
        ui.newline()
        if lock.get('colors'):
            v = ui.slider('lockd', 'dither', float(lock.get('dither', 0) or 0), 0, 1)
            if v != float(lock.get('dither', 0) or 0):
                lock['dither'] = v
                app.post.configure(th['crt'], None if lock.get('off') else lock)
                self.dirty = True

        ui.header('CRT / POST FX')
        crt = th['crt']
        for key, hi in (('scanlines', 1), ('vignette', 1.5), ('bloom', 1.5), ('phosphor', 0.97), ('flicker', 0.3),
                        ('noise', 1), ('glitch', 3), ('curvature', 1), ('lcd', 1), ('interlace', 1)):
            v = ui.slider('crt' + key, key, float(crt.get(key) or 0), 0, hi)
            if v != float(crt.get(key) or 0):
                crt[key] = v
                app.post.configure(crt, None if (th.get('palette_lock') or {}).get('off') else th.get('palette_lock'))
                self.dirty = True
        v = ui.slider('crtab', 'aberration', int(crt.get('aberration') or 0), 0, 6, fmt='%d', integer=True)
        if v != int(crt.get('aberration') or 0):
            crt['aberration'] = v
            app.post.configure(crt, None if (th.get('palette_lock') or {}).get('off') else th.get('palette_lock'))
            self.dirty = True

        ui.header('SOUND')
        snd = th.setdefault('sound', {})
        v = ui.cycle('pack', snd.get('pack', 'chime'), ['chime', 'typewriter', '8bit', 'glass', 'off'])
        if v != snd.get('pack'):
            snd['pack'] = v
            app.sound.enabled = v != 'off'
            self._apply()
        ui.newline()
        v = ui.slider('vol', 'volume', float(snd.get('volume', 0.4)), 0, 1)
        if v != snd.get('volume'):
            snd['volume'] = v
            app.sound.volume = v
            self.dirty = True
        ui.newline(30)

    def _text_row(self, fid, label, val):
        ui = self.ui
        ui.label(label, UI.DIM, w=90)
        nv = ui.textfield(fid, val or '', ui.w - 100)
        ui.newline()
        if nv != val:
            self.dirty = True
        return nv

    def _load(self, name):
        app = self.app
        for k in ('background', 'letter_effect', 'delete_effect'):
            app.cfg[k] = None
        app.apply_theme(themes.load_theme(name))
        self.dirty = False
        self.msg = 'loaded %s' % name

    def _get_color(self, th):
        t = self.color_target
        return hex2rgb(th['palette'][t]) if isinstance(t, int) else hex2rgb(th.get(t, '#000000'))

    def _set_color(self, th, rgb):
        t = self.color_target
        h = rgb2hex(rgb)
        if isinstance(t, int):
            th['palette'] = list(th['palette'])
            th['palette'][t] = h
        else:
            th[t] = h
        for p in self.app.all_panes():
            p.set_theme(th)
        self.dirty = True

    def _color_editor(self, th):
        ui = self.ui
        c = list(self._get_color(th))
        name = ('palette %d' % self.color_target) if isinstance(self.color_target, int) else self.color_target
        ui.label('editing: %s' % name, UI.HOT, w=170)
        if ui.focus != 'hex':
            self.hexbuf = rgb2hex(c)
        self.hexbuf = ui.textfield('hex', self.hexbuf, 90)
        if ui.focus != 'hex' and self.hexbuf != rgb2hex(c):
            try:
                c = list(hex2rgb(self.hexbuf))
                self._set_color(th, c)
            except ValueError:
                pass
        ui.newline()
        new = list(c)
        for i, ch in enumerate('RGB'):
            new[i] = ui.slider('col' + ch, ch, c[i], 0, 255, lw=30, fmt='%d', integer=True)
        # hue strip
        r = pygame.Rect(ui.x, ui.y + 2, ui.w, 12)
        for i in range(r.width):
            col = pygame.Color(0)
            col.hsva = (i / r.width * 360, 90, 100, 100)
            ui.surf.fill(col, (r.x + i, r.y, 1, r.height))
        if ui.down and ui.hit(r):
            col = pygame.Color(0)
            col.hsva = ((ui.mouse[0] - r.x) / r.width * 360, 85, 100, 100)
            new = [col.r, col.g, col.b]
        ui.newline()
        if new != c:
            self._set_color(th, new)

    # ------------------------------------------------------------ FONT
    def tab_font(self):
        ui, app = self.ui, self.app
        f = app.font
        ui.label('font: %s   cell %dx%d   (%s)' % (f.name, f.cw, f.ch, type(f).__name__), UI.HOT)
        ui.newline()
        anim = isinstance(f, fonts.AnimatedFont)
        if anim:
            n = len(f.frames)
            self.fidx = getattr(self, 'fidx', 0) % n
            ui.label('animated font', UI.ACC, w=110)
            if ui.button('◄', 22):
                self.fidx = (self.fidx - 1) % n
            ui.label('frame %d/%d' % (self.fidx + 1, n), w=80)
            if ui.button('►', 22):
                self.fidx = (self.fidx + 1) % n
            held = getattr(f, 'hold', None) is not None
            if ui.button('Play' if held else 'Hold'):
                f.hold = None if held else self.fidx
            if held:
                f.hold = self.fidx
            ui.newline()
            v = ui.slider('ffps', 'fps', float(f.fps), 1, 30, fmt='%.0f')
            if v != f.fps:
                f.fps = max(1.0, v)
            editable = all(isinstance(fr, fonts.PixelFont) for fr in f.frames)
            if editable:
                if ui.button('Duplicate frame'):
                    src = f.frames[self.fidx]
                    f.frames.insert(self.fidx + 1, fonts.PixelFont(src.name, src.cw, src.ch,
                                                                   {c: b.copy() for c, b in src.bits.items()}))
                    self.fidx += 1
                    self._all_changed()
                if len(f.frames) > 1 and ui.button('Delete frame'):
                    f.frames.pop(self.fidx)
                    self.fidx = max(0, self.fidx - 1)
                    self._all_changed()
                ui.newline()
            else:
                ui.label('generated frames - convert to edit them', UI.DIM)
                ui.newline()
                if ui.button('Convert frames to editable pixel frames'):
                    fr = [fonts.PixelFont.from_font(x) for x in f.frames]
                    nf = fonts.AnimatedFont(f.name.replace('builtin:', '') + '_anim', fr, f.fps)
                    nf.spec = getattr(f, 'spec', 'builtin')
                    app.font_override = None
                    app.set_font(nf)
                    self.fontname = nf.name
                ui.newline()
            ef = f.frames[self.fidx] if editable else None
        else:
            editable = isinstance(f, fonts.PixelFont)
            ef = f
            if editable and ui.button('Make animated (4 frames)'):
                fr = [fonts.PixelFont(f.name, f.cw, f.ch, {c: b.copy() for c, b in f.bits.items()}) for _ in range(4)]
                nf = fonts.AnimatedFont(f.name + '_anim', fr, 6)
                app.font_override = None
                app.set_font(nf)
                self.fontname = nf.name
                return
            ui.newline()
        if not editable:
            ui.label('This font is not pixel-editable.', UI.DIM)
            ui.newline()
            if ui.button('Convert to editable pixel font'):
                pf = fonts.PixelFont.from_font(f)
                pf.spec = getattr(f, 'spec', 'builtin')
                app.font_override = None
                app.set_font(pf)
                self.fontname = pf.name
                self.msg = 'converted - edit & save as a new font'
            ui.newline()
        ui.label('new font, cell', UI.DIM, w=110)
        for i in (0, 1):
            if ui.button('-', 22):
                self.newcell[i] = max(3, self.newcell[i] - 1)
            ui.label(str(self.newcell[i]), w=24)
            if ui.button('+', 22):
                self.newcell[i] = min(64, self.newcell[i] + 1)
            if i == 0:
                ui.label('x', UI.DIM, w=14)
        if ui.button('Create (resample current)'):
            pf = fonts.PixelFont.from_font(f, self.newcell[0], self.newcell[1], name='font%dx%d' % tuple(self.newcell))
            app.font_override = None
            app.set_font(pf)
            self.fontname = pf.name
        ui.newline()
        if not editable:
            return
        if not self.fontname:
            self.fontname = f.name
        ui.label('name', UI.DIM, w=50)
        self.fontname = ui.textfield('fontname', self.fontname, 160)
        if ui.button('Save font'):
            p = f.save(self.fontname.strip() or f.name)
            f.spec = 'fonts/' + os.path.basename(p)
            app.theme['font'] = f.spec
            app._watch_file('font', None)
            self.msg = 'saved %s (+ .png sheet). theme font set.' % os.path.basename(p)
        if ui.button('Use in theme'):
            app.theme['font'] = getattr(f, 'spec', None) or 'builtin'
            self.dirty = True
        ui.newline()

        ui.header('GLYPHS  (click, or hover + type a key)')
        cell = 17
        gx0, gy0 = ui.x, ui.y
        for i, c in enumerate(fonts.CP437):
            r = pygame.Rect(gx0 + (i % 16) * cell, gy0 + (i // 16) * cell, cell - 1, cell - 1)
            sel = c == self.glyph
            ui.surf.fill((60, 60, 90) if sel else (26, 28, 40), r)
            if i:
                g = f.glyph(c)
                k = min((cell - 3) / f.cw, (cell - 3) / f.ch)
                gs = pygame.transform.scale(g, (max(1, int(f.cw * k)), max(1, int(f.ch * k))))
                ui.surf.blit(gs, (r.x + (r.w - gs.get_width()) // 2, r.y + (r.h - gs.get_height()) // 2))
            if ui.clicked(r):
                self.glyph = c
        ui.y = gy0 + cell * 16 + 6
        ui.x = ui.x0
        ui.label('glyph %r  U+%04X  cp437 %s' % (self.glyph, ord(self.glyph), fonts.UNI_TO_CP437.get(self.glyph, '-')), UI.HOT)
        ui.newline()

        # editor canvas
        z = int(max(4, min(22, (ui.w - 10) / f.cw, 300 / f.ch)))
        cx0, cy0 = ui.x, ui.y
        bits = ef.get_bits(self.glyph)
        canvas = pygame.Rect(cx0, cy0, f.cw * z, f.ch * z)
        ui.surf.fill((8, 8, 12), canvas)
        for x in range(f.cw):
            for y in range(f.ch):
                if bits[x, y]:
                    ui.surf.fill((240, 240, 255), (cx0 + x * z, cy0 + y * z, z - 1, z - 1))
                else:
                    ui.surf.fill((26, 28, 38), (cx0 + x * z, cy0 + y * z, z - 1, z - 1))
        # baseline helpers
        pygame.draw.rect(ui.surf, UI.ACC, canvas, 1)
        if ui.hit(canvas) and (ui.down or ui.rdown):
            px = (ui.mouse[0] - cx0) // z
            py = (ui.mouse[1] - cy0) // z
            if self.paint is None:
                self.paint = bool(ui.down)
            if ef.set_pixel(self.glyph, px, py, self.paint):
                self._font_changed(self.glyph)
        ui.y = canvas.bottom + 6
        ui.x = ui.x0
        ui.label('LMB paint  RMB erase', UI.DIM)
        ui.newline()
        b = bits
        ops = [('Clear', lambda: b.__setitem__(slice(None), False)),
               ('Invert', lambda: np.logical_not(b, out=b)),
               ('◄', lambda: b.__setitem__(slice(None), np.roll(b, -1, 0))),
               ('►', lambda: b.__setitem__(slice(None), np.roll(b, 1, 0))),
               ('▲', lambda: b.__setitem__(slice(None), np.roll(b, -1, 1))),
               ('▼', lambda: b.__setitem__(slice(None), np.roll(b, 1, 1))),
               ('Mirror', lambda: b.__setitem__(slice(None), b[::-1, :].copy())),
               ('Bold', lambda: b.__setitem__(slice(None), b | np.roll(b, 1, 0)))]
        for name, fn in ops:
            if ui.button(name):
                fn()
                ef.touch(self.glyph)
                self._font_changed(self.glyph)
        ui.newline()
        if ui.button('Copy'):
            self.clip = bits.copy()
        if ui.button('Paste') and self.clip is not None and self.clip.shape == bits.shape:
            bits[:] = self.clip
            ef.touch(self.glyph)
            self._font_changed(self.glyph)
        if ui.button('Type glyph in terminal'):
            app.inject(self.glyph)
        ui.newline()

        ui.header('PREVIEW')
        self.sample = self._text_row('sample', 'text', self.sample)
        for k in (1, 2, 3):
            x = ui.x
            for c in self.sample:
                if c != ' ':
                    g = f.glyph(c)
                    if k > 1:
                        g = pygame.transform.scale(g, (f.cw * k, f.ch * k))
                    ui.surf.blit(g, (x, ui.y))
                x += f.cw * k
                if x > ui.rect.right - 10:
                    break
            ui.newline(f.ch * k + 6)
        ui.newline(20)

    def _all_changed(self):
        self.app.gcache.clear()
        for p in self.app.all_panes():
            p.renderer.full = True

    def _font_changed(self, c):
        self.app.refresh_glyph(c)

    # ------------------------------------------------------------ PLUGINS
    def tab_plugins(self):
        ui, app = self.ui, self.app
        pm = app.plugins
        ui.label('Plugins hot-reload on save. Hooks: frame draw draw_under post key', UI.DIM)
        ui.newline()
        ui.label('output put del bell theme command + effects/backgrounds.', UI.DIM)
        ui.newline()
        ui.label('new', UI.DIM, w=40)
        self.newplug = ui.textfield('newplug', self.newplug, 170)
        if ui.button('Create & open') and self.newplug.strip():
            p = pm.new_plugin(self.newplug.strip())
            open_in_editor(p)
            self.msg = 'created %s' % p
            self.newplug = ''
        if ui.button('Folder'):
            open_in_editor(pm.dirs[0])
        ui.newline()
        if ui.button('Docs (PLUGINS.md)'):
            open_in_editor(os.path.join(themes.ROOT, 'docs', 'PLUGINS.md'))
        ui.newline()
        ui.header('INSTALLED')
        for path, p in sorted(pm.plugins.items(), key=lambda kv: kv[1].name):
            on = ui.toggle(p.name, p.enabled, w=150)
            if on != p.enabled:
                pm.set_enabled(p, on)
            st = 'ERROR' if p.error else ('ok' if p.module else 'off')
            ui.label(st, UI.ERR if p.error else (UI.ACC if p.module else UI.DIM), w=50)
            if ui.button('Open'):
                open_in_editor(p.path)
            if ui.button('Reload'):
                pm.load(p)
            ui.newline()
            desc = p.meta.get('description', '')
            if desc:
                ui.x += 22
                ui.label(desc[:60], UI.DIM)
                ui.newline()
            if p.error:
                for ln in p.error.strip().splitlines()[-4:]:
                    ui.x += 22
                    ui.label(ln.strip()[:62], UI.ERR)
                    ui.newline(16)
        hk = pm.hotkeys
        if hk:
            ui.header('PLUGIN HOTKEYS (Ctrl+Shift+...)')
            for k, (p, fn, d) in hk.items():
                ui.label('%-6s %s  (%s)' % (k, d, p.name))
                ui.newline()

    def tab_console(self):
        ui, app = self.ui, self.app
        if ui.button('Clear'):
            app.plugins.console.clear()
        ui.label('fps %.0f   fx %d   particles %d   energy %.2f' % (app.clock.get_fps(), len(app.fx.active),
                                                                    app.fx.particles.n, app.energy), UI.DIM)
        ui.newline()
        for line in app.plugins.console[-120:]:
            for ln in line.splitlines():
                ui.label(ln[:66], UI.ERR if 'ERROR' in line or 'Error' in ln else UI.FG)
                ui.newline(16)
