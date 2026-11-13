"""The main application: window, tabs & split panes, frame loop and glue."""
from __future__ import annotations

import json
import math
import os
import random
import time

import pygame

from . import backgrounds, effects, fonts, signals, themes, vt
from .backend import FileSource, ScriptSource, create_backend, default_shell
from .keys import key_to_seq, mouse_seq
from .pane import Pane
from .plugins import PluginManager
from .post import Post
from .present import create_presenter
from .sound import Sound

WRITER_MODES = ['smart', 'instant', 'baud', 'human']
BAUDS = [300, 1200, 2400, 9600, 19200, 57600, 115200]
SOUND_PACKS = ['chime', 'typewriter', '8bit', 'glass', 'cyber', 'off']

HELP = [
    ('Ctrl+Shift+H', 'this help'), ('Ctrl+Shift+F12', 'Studio (theme/font/plugin editor)'),
    ('Ctrl+Shift+Space', 'ZEN mode <-> OVERKILL mode'),
    ('Ctrl+Shift+T / W', 'new tab / close pane'), ('Ctrl+Shift+E / O', 'split side by side / stacked'),
    ('Alt+Arrows', 'focus pane'), ('Ctrl+Tab, Ctrl+PgUp/Dn', 'next / prev tab'), ('Ctrl+Shift+1..9', 'go to tab'),
    ('Ctrl+Shift+Up/Down', 'previous / next command'), ('Ctrl+Shift+A', 'copy last command output'),
    ('Ctrl+Shift+F1 / F2 / F3', 'theme / letter fx / delete fx'), ('Ctrl+Shift+U (Alt+)', 'cursor style (effects)'), ('Ctrl+Shift+F4', 'writer mode / baud'),
    ('Ctrl+Shift+F5 / F6 / F7', 'CRT / bloom / phosphor'), ('Ctrl+Shift+F8', 'sound pack'),
    ('Ctrl+Shift+B / M / F', 'background / EMERALD MINE / font'), ('Ctrl+Shift+ +/-', 'pixel scale'),
    ('Ctrl+Shift+C / V', 'copy / paste'), ('Ctrl+Shift+L', 'search scrollback'),
    ('Ctrl+Shift+X', 'screenshot'), ('Ctrl+Shift+G / J', 'record MP4 / GIF'), ('Ctrl+Shift+R', 'record asciinema cast'),
    ('Shift+PgUp/PgDn, wheel', 'scrollback'), ('Ctrl+Click', 'open URL'), ('F11 / Alt+Enter', 'fullscreen'),
]


def clip_get():
    try:
        t = pygame.scrap.get_text()
        if t:
            return t
    except Exception:
        pass
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        d = pygame.scrap.get(pygame.SCRAP_TEXT)
        if d:
            return d.decode('utf-8', 'ignore').rstrip('\x00')
    except Exception:
        pass
    try:
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        t = r.clipboard_get()
        r.destroy()
        return t
    except Exception:
        return ''


def clip_put(text):
    try:
        pygame.scrap.put_text(text)
        return
    except Exception:
        pass
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        pygame.scrap.put(pygame.SCRAP_TEXT, text.encode('utf-8'))
    except Exception:
        pass


def _fast_surface(size):
    s = pygame.Surface(size, 0, 32)
    try:
        return s.convert()
    except pygame.error:  # GPU presenter: no display surface, plain 32 bit is fine
        return s


# ============================================================================ tabs / splits
class Split:
    def __init__(self, direction, a, b, ratio=0.5):
        self.dir = direction    # 'v' = side by side, 'h' = stacked
        self.a, self.b = a, b
        self.ratio = ratio


class Tab:
    def __init__(self, pane):
        self.root = pane
        self.focus = pane

    def panes(self, node=None):
        node = self.root if node is None else node
        if isinstance(node, Split):
            return self.panes(node.a) + self.panes(node.b)
        return [node]

    def _parent(self, node, target):
        if isinstance(node, Split):
            if node.a is target or node.b is target:
                return node
            return self._parent(node.a, target) or self._parent(node.b, target)
        return None

    def split(self, pane, new, direction):
        sp = Split(direction, pane, new)
        par = self._parent(self.root, pane)
        if par is None:
            self.root = sp
        elif par.a is pane:
            par.a = sp
        else:
            par.b = sp
        self.focus = new

    def remove(self, pane):
        par = self._parent(self.root, pane)
        if par is None:
            self.root = None
            return
        sib = par.b if par.a is pane else par.a
        gp = self._parent(self.root, par)
        if gp is None:
            self.root = sib
        elif gp.a is par:
            gp.a = sib
        else:
            gp.b = sib
        if self.focus is pane:
            self.focus = self.panes(sib)[0]

    def layout(self, rect, cw, ch, gap, node=None, out=None):
        out = {} if out is None else out
        node = self.root if node is None else node
        if not isinstance(node, Split):
            out[node] = rect
            return out
        if node.dir == 'v':
            wa = max(cw * 4, int((rect.width - gap) * node.ratio) // cw * cw)
            ra = pygame.Rect(rect.x, rect.y, wa, rect.height)
            rb = pygame.Rect(rect.x + wa + gap, rect.y, rect.width - wa - gap, rect.height)
        else:
            ha = max(ch * 2, int((rect.height - gap) * node.ratio) // ch * ch)
            ra = pygame.Rect(rect.x, rect.y, rect.width, ha)
            rb = pygame.Rect(rect.x, rect.y + ha + gap, rect.width, rect.height - ha - gap)
        self.layout(ra, cw, ch, gap, node.a, out)
        self.layout(rb, cw, ch, gap, node.b, out)
        return out


# ============================================================================ app
_warned_screens = set()


class App:
    def __init__(self, cfg, args):
        self.cfg = cfg
        self.args = args
        self.headless = bool(args.screenshot or args.benchmark or os.environ.get('SDL_VIDEODRIVER') == 'dummy')
        pygame.init()
        pygame.key.set_repeat(400, 30)
        self.presenter = create_presenter(cfg, self.headless)
        self.presenter.set_caption('pyterm')
        try:
            from .mine import LEGS, TOP, _sprite
            icon = pygame.Surface((32, 32), pygame.SRCALPHA)
            icon.fill((0, 0, 0, 0))
            icon.blit(_sprite(TOP + LEGS[0], 2), (8, 5))
            self.presenter.set_icon(icon)
        except Exception:
            pass
        try:
            pygame.key.start_text_input()
        except Exception:
            pass
        self.clock = pygame.time.Clock()
        self.t = 0.0
        self.notes = []
        self.show_help = False
        self.zen = None
        self.energy = 0.0
        self.drama_t = 0.0
        self.shake = 0.0
        self.studio = None
        self.studio_w = 0
        self._watch = {}
        self.font_override = cfg.get('font')
        self.gcache = {}
        self.tooltip = None
        self.mouse_v = None
        self.focused_window = True
        self.minimized = False
        self.video = None
        self.eco = False
        self.anim_until = 0.0
        self._bg_t = 0.0
        self.bgsurf = None
        self.tab_rects = []

        self.theme = themes.load_theme(cfg['theme'])
        self.font = self._load_font_for(self.theme)
        self.post = Post()
        vol = cfg['volume'] if cfg.get('volume') is not None else self.theme['sound'].get('volume', 0.4)
        self.sound = Sound(self.theme['sound'].get('pack', 'chime'), vol, enabled=bool(cfg['sound']) and not args.benchmark)
        self.bg = None
        self.vsurf = None
        self.plugins = PluginManager(self, cfg.get('plugin_dirs'), enabled=bool(cfg['plugins']))
        self.tabs = [Tab(Pane(self, cfg.get('cwd')))]
        self.tab_i = 0
        self.apply_theme(self.theme, first=True)
        self.plugins.scan()
        self._applied = None
        self.apply_theme(self.theme, first=True)
        self.intro = None
        if cfg.get('intro', True) and not args.benchmark and not args.screenshot and not cfg.get('studio') \
                and not getattr(args, 'record', None):
            from .splash import make_splash
            self.intro = make_splash(self)
        if cfg.get('studio'):
            self.toggle_studio()
        self.alarm = None
        self.shows = []
        self._startup_shows = True
        self._swallow_text = 0.0
        self.mqtt = None
        if (cfg.get('mqtt') or {}).get('enabled') and not args.benchmark:
            from .mqtt import MqttBridge
            self.mqtt = MqttBridge(self, cfg['mqtt'])
            if not self.mqtt.start():
                self.notify('MQTT: %s' % self.mqtt.error, 6)
                self.mqtt = None
        if cfg.get('_random'):
            self.notify('random  ' + '   '.join('%s: %s' % (k.replace('_effect', '').replace('_', ' '), v)
                                                 for k, v in cfg['_random']), 6)
        if getattr(args, 'record', None):
            self.start_video(args.record, fixed=self.headless)

    # ------------------------------------------------------------ focus shortcuts (plugin / studio API)
    @property
    def tab(self):
        return self.tabs[self.tab_i]

    @property
    def pane(self):
        return self.tab.focus

    @property
    def screen(self):
        return self.pane.screen

    @property
    def fx(self):
        return self.pane.fx

    @property
    def backend(self):
        return self.pane.backend

    @property
    def renderer(self):
        return self.pane.renderer

    @property
    def mine(self):
        return self.pane.mine

    @property
    def term_rect(self):
        return self.pane.rect

    def all_panes(self):
        out = []
        for t in self.tabs:
            out += t.panes()
        return out

    # ------------------------------------------------------------ setup helpers
    def _load_font_for(self, theme):
        spec = self.font_override or theme.get('font') or 'builtin'
        size = self.cfg.get('font_size') or theme.get('font_size') or 18
        aa = self.cfg.get('antialias')
        if aa is None:
            aa = theme.get('antialias', True)
        try:
            f = fonts.load_font(spec, size, aa)
        except Exception as e:
            print('[pyterm] font error %s: %s' % (spec, e))
            f = fonts.load_font('builtin')
        f.spec = spec
        self._watch_file('font', getattr(f, 'path', None) or (spec if os.path.exists(str(spec)) else None))
        return f

    def make_backend(self, pane, cwd=None):
        cfg = self.cfg
        if cfg.get('cat') and not getattr(self, '_cat_used', False):
            self._cat_used = True
            return FileSource(cfg['cat'], encoding=cfg['encoding'], echo=True)
        if cfg.get('demo') or self.args.benchmark:
            from . import demo
            first = not getattr(self, '_demo_used', False)
            self._demo_used = True
            script = demo.demo_script(demo.PROMPT) if first and not self.args.benchmark else \
                [(0.1, demo.MARK_A + demo.PROMPT + demo.MARK_B if not self.args.benchmark else '')]
            b = ScriptSource(script, cfg['encoding'], prompt=demo.PROMPT, marks=True)
            b.on_command = self.demo_command
            return b
        cmd = cfg['shell']
        if cfg.get('shell_integration', True):
            from .shell import integrate
            cmd = integrate(cmd or default_shell())
        return create_backend(cfg['backend'], cmd, 80, 24, cfg['encoding'], cwd or cfg.get('cwd'))

    def scale(self):
        s = self.cfg.get('scale') or self.theme.get('scale')
        if not s:
            s = 2 if self.font.pixel else 1
        return max(1, int(s))

    def tabbar_visible(self):
        mode = self.cfg.get('tabbar', 'auto')
        return mode == 'always' or (mode == 'auto' and len(self.tabs) > 1)

    def screen_grid(self):
        """theme 'screen: {cols: 40, rows: 25, border: [32, 36]}' -> fixed text area like the original
        machine (C64: 320x200 pixels inside a 384x272 frame); None for the normal resizable terminal"""
        sg = self.theme.get('screen')
        if not isinstance(sg, dict) or not sg.get('cols') or not sg.get('rows'):
            return None
        bx, by = (sg.get('border') or [32, 36]) if isinstance(sg.get('border'), (list, tuple)) else (sg.get('border') or 32,) * 2
        try:
            cols, rows, bx, by = int(sg['cols']), int(sg['rows']), int(bx), int(by)
            if cols < 1 or rows < 1:
                raise ValueError('cols and rows must be positive')
            return cols, rows, bx, by
        except (TypeError, ValueError) as e:
            name = self.theme.get('name', '?')
            if name not in _warned_screens:
                _warned_screens.add(name)
                print("[pyterm] theme '%s': invalid screen settings %r (%s) - using a resizable terminal"
                      % (name, sg, e))
            return None

    def layout(self):
        W, H = self.presenter.size()
        W = max(64, W - self.studio_w)
        cw, ch = self.font.cw, self.font.ch
        grid = self.screen_grid()
        if grid:
            gc, gr, bx, by = grid
            fw, fh = gc * cw + bx, gr * ch + by                 # text area + at least half of the original border
            s = int(self.cfg.get('scale') or 0) or max(1, min(W // fw, H // fh))
        else:
            s = self.scale()
        self.s = s
        if grid:      # cover the whole window (round up) so the border reaches every edge
            self.vw, self.vh = max(16, -(-W // s)), max(16, -(-H // s))
        else:
            self.vw, self.vh = max(16, W // s), max(16, H // s)
        if self.vsurf is None or self.vsurf.get_size() != (self.vw, self.vh):
            self.vsurf = _fast_surface((self.vw, self.vh))
            self.bgsurf = None
        b = int(self.theme.get('border', 6))
        top = (ch + 6) if self.tabbar_visible() else 0
        if grid:
            gw, gh = min(gc * cw, self.vw - 4), min(gr * ch, self.vh - 4 - top)
            area = pygame.Rect((self.vw - gw) // 2, top + (self.vh - top - gh) // 2, gw, gh)
        else:
            area = pygame.Rect(b, b + top, self.vw - 2 * b, self.vh - 2 * b - top)
        self.content = area
        for ti, tab in enumerate(self.tabs):
            panes = tab.panes()
            if len(panes) == 1:
                p = panes[0]
                cols = max(10, area.width // cw)
                rows = max(4, area.height // ch)
                x = area.x + (area.width - cols * cw) // 2
                y = area.y + (area.height - rows * ch) // 2
                p.layout(pygame.Rect(x, y, cols * cw, rows * ch), s)
            else:
                rects = tab.layout(area, cw, ch, gap=5)
                for p, r in rects.items():
                    p.layout(pygame.Rect(r.x + 4, r.y, r.width - 4, r.height), s)
        if self.bg:
            self.bg.resize(self.vw, self.vh)

    def set_font(self, font):
        self.font = font
        self.gcache.clear()
        for p in self.all_panes():
            p.set_font(font)
        self.layout()

    def apply_theme(self, theme, first=False):
        old = getattr(self, '_applied', None)
        self.theme = theme
        self._watch_file('theme', theme.get('_path'))
        if not first and not self.font_override:
            spec = theme.get('font') or 'builtin'
            ofs = (getattr(self.font, 'spec', None), getattr(self, '_font_size', None))
            if ofs != (spec, theme.get('font_size')):
                self.font = self._load_font_for(theme)
                self.gcache.clear()
                for p in self.all_panes():
                    p.set_font(self.font)
        self._font_size = theme.get('font_size')
        for p in self.all_panes():
            p.set_theme(theme)
        self.post.configure(theme.get('crt'), theme.get('palette_lock'))
        self.post.overlay = theme.get('color_overlay')
        cfg = self.cfg
        bgs = cfg['background'] if cfg.get('background') else theme.get('background', [])
        key = (tuple(bgs), json.dumps(theme.get('bg_params', {}), sort_keys=True))
        if not old or old[0] != key:
            self.bg = backgrounds.BackgroundStack(bgs, getattr(self, 'vw', 320), getattr(self, 'vh', 200),
                                                  theme.get('bg_params'), theme)
            self.bgsurf = None
        from . import weather
        weather.SOUND = lambda n: self.sound.play(n, min_gap=1.0, vol=0.6)
        snd = theme.get('sound', {})
        if self.sound.ok and snd.get('pack') and snd.get('pack') != self.sound.pack:
            self.sound.build(snd['pack'])
        if self.cfg.get('volume') is None and 'volume' in snd:
            self.sound.volume = float(snd['volume'])
        miner = cfg['miner'] if cfg.get('miner') is not None else theme.get('miner', False)
        for p in self.all_panes():
            p.set_miner(bool(miner))
        w = theme.get('writer', {})
        self.writer = cfg.get('writer') or w.get('mode', 'smart')
        self.baud = cfg.get('baud') or w.get('baud', 9600)
        self._applied = (key,)
        self.layout()
        if not first:
            self.plugins.emit('theme', theme)
            self.show_event('theme')
            if getattr(self, 'mqtt', None):
                self.mqtt.publish_state()

    def _watch_file(self, kind, path):
        if path and os.path.exists(path):
            self._watch[kind] = (path, os.path.getmtime(path))
        else:
            self._watch.pop(kind, None)

    def _poll_watch(self):
        for kind, (path, mt) in list(self._watch.items()):
            try:
                m2 = os.path.getmtime(path)
            except OSError:
                continue
            if m2 != mt:
                self._watch[kind] = (path, m2)
                if kind == 'theme':
                    self.apply_theme(themes.load_theme(path))
                    self.notify('theme reloaded: %s' % os.path.basename(path))
                elif kind == 'font':
                    self.set_font(self._load_font_for(self.theme))
                    self.notify('font reloaded')

    def refresh_glyph(self, c):
        for k in [k for k in self.gcache if isinstance(k, tuple) and k[0] == c]:
            del self.gcache[k]
        for p in self.all_panes():
            p.renderer.full = True

    # ------------------------------------------------------------ public helpers
    def notify(self, text, secs=2.5):
        self.notes.append([text, secs, secs])
        del self.notes[:-4]

    def inject(self, text):
        self.pane.inject(text)

    def animating(self, secs=0.1):
        """plugins call this while they animate (keeps the frame rate up)"""
        self.anim_until = max(self.anim_until, self.t + secs)

    def draw_text(self, surf, x, y, text, rgb=(255, 255, 255), style=0):
        cw = self.font.cw
        r = self.renderer
        for c in text:
            if c != ' ':
                surf.blit(r.colored(c, style, False, rgb), (x, y))
            x += cw
        return x

    def panel(self, vs, rect, alpha=200):
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        s.fill((0, 0, 0, alpha))
        vs.blit(s, rect.topleft)
        pygame.draw.rect(vs, (90, 200, 255), rect, 1)

    def command_done(self, pane, m):
        dur = (m['t1'] or 0) - (m['t0'] or 0)
        signals.cmd = (m['exit'], dur, time.time())
        self.plugins.emit('command_done', m['exit'], dur, m.get('cmdline', ''))
        self.show_event('command_ok' if m['exit'] == 0 else 'command_failed')
        if dur >= float(self.cfg.get('notify_after', 8) or 8):
            self.show_event('success' if m['exit'] == 0 else 'fail')
        if self.mqtt:
            self.mqtt.command_done(m['exit'], dur, m.get('cmdline', ''), pane.screen.cwd)
        if pane.cursor:
            pane.cursor.command_done(m['exit'], dur)
            for e in pane.cursor_fx:
                e.command_done(m['exit'], dur)
        long_cmd = float(self.cfg.get('notify_after', 8) or 8)
        if dur >= long_cmd:
            ok = m['exit'] == 0
            self.notify('%s %s  (%.1fs)' % ('✓ done:' if ok else '✗ exit %d:' % m['exit'], m['cmdline'][:40], dur), 5)
            self.sound.play('gem' if ok else 'bell', min_gap=0.5)
            if not self.focused_window or pane is not self.pane:
                self.post.flash = 0.5
                self.post.flash_rgb = (60, 255, 120) if ok else (255, 60, 60)

    # ------------------------------------------------------------ tabs / panes
    def new_tab(self):
        p = Pane(self, self.screen.cwd)
        self.tabs.insert(self.tab_i + 1, Tab(p))
        self.tab_i += 1
        self._apply_to_new(p)
        self.notify('tab %d' % (self.tab_i + 1), 1)

    def split(self, direction):
        p = Pane(self, self.screen.cwd)
        self.tab.split(self.pane, p, direction)
        self._apply_to_new(p)

    def _apply_to_new(self, p):
        miner = self.cfg['miner'] if self.cfg.get('miner') is not None else self.theme.get('miner', False)
        p.set_miner(bool(miner))
        self.layout()

    def close_pane(self, pane=None):
        pane = pane or self.pane
        for ti, tab in enumerate(self.tabs):
            if pane in tab.panes():
                pane.close()
                tab.remove(pane)
                if tab.root is None:
                    self.tabs.pop(ti)
                    if not self.tabs:
                        self.running = False
                        return
                    self.tab_i = min(self.tab_i, len(self.tabs) - 1)
                self.layout()
                return

    def goto_tab(self, i):
        if 0 <= i < len(self.tabs):
            self.tab_i = i
            for p in self.tab.panes():
                p.renderer.full = True

    def focus_dir(self, dx, dy):
        cur = self.pane.rect
        best, bd = None, 1e9
        for p in self.tab.panes():
            if p is self.pane:
                continue
            r = p.rect
            vx, vy = r.centerx - cur.centerx, r.centery - cur.centery
            if (dx and vx * dx <= 0) or (dy and vy * dy <= 0):
                continue
            d = abs(vx) + abs(vy) * (2 if dx else 1) + abs(vx) * (2 if dy else 0)
            if d < bd:
                best, bd = p, d
        if best:
            self.tab.focus = best

    # ------------------------------------------------------------ demo shell
    def demo_command(self, cmd):
        from . import demo
        parts = cmd.strip().split()
        if not parts:
            return ''
        c, args = parts[0], parts[1:]
        if c in ('theme', 'font', 'bg', 'effect', 'delete', 'cursor') and args and args[0].lower().startswith(('random', 'pick')):
            from .config import resolve_random
            key = {'theme': 'theme', 'font': 'font', 'bg': 'background', 'effect': 'letter_effect',
                   'delete': 'delete_effect', 'cursor': 'cursor_style'}[c]
            tmp = {key: args[0]}
            got = resolve_random(tmp)
            if got:
                val = tmp[key]
                args = [','.join(val) if isinstance(val, list) else val] + list(args[1:])
        simple = {'help': demo.HELP, 'colors': demo.color_table, 'boxes': demo.boxes, 'art': demo.ansi_art,
                  'braille': demo.braille_wave, 'logo': demo.logo, 'info': demo.sysinfo, 'hack': demo.hack,
                  'lorem': demo.LOREM + '\r\n', 'clear': '\x1b[2J\x1b[3J\x1b[H', 'image': demo.image_demo,
                  'sixel': lambda: demo.image_demo('sixel'), 'kitty': lambda: demo.image_demo('kitty')}
        if c in simple:
            v = simple[c]
            return v() if callable(v) else v
        if c == 'weather':
            from . import weather
            lay = [l for l in (self.bg.layers if self.bg else []) if isinstance(l, weather.Weather)]
            if not lay:
                return 'no weather background - try: theme weather   or   bg weather\r\n'
            L = lay[0]
            if args and args[0] in weather.SIM:
                L.sim = args[0]
                return 'simulating %s (weather live to go back)\r\n' % args[0]
            if args and args[0] == 'live':
                L.sim = None
                L.timelapse = 0
                L.feed = weather.WeatherFeed.get(L.prm.get('location', 'auto'))
            if args and args[0] == 'timelapse':
                L.timelapse = 0 if L.timelapse else float(args[1]) if len(args) > 1 else 60.0
                return 'timelapse %s\r\n' % ('off' if not L.timelapse else '%.0f s per day' % L.timelapse)
            f = L.feed
            st = ('error: %s' % f.error) if f and f.error and not f.data else ('updated %ds ago' % (time.time() - f.updated) if f and f.data else 'fetching...')
            return '%s\r\n%s\r\nforce a condition: weather clear|cloudy|rain|snow|fog|storm|live   day cycle: weather timelapse [secs]\r\n' % (L.label, st)
        if c == 'emoji':
            return demo.emoji_table()
        if c == 'fonts':
            return '  '.join(fonts.list_fonts()) + '\r\n'
        if c in ('font', 'animfont'):
            spec = args[0] if args else ('builtin:wave' if c == 'animfont' else 'builtin')
            if c == 'animfont' and not args:
                cur = getattr(self.font, 'spec', '')
                opts = ['builtin:wave', 'builtin:shimmer', 'builtin:jelly', 'builtin:bounce', 'fonts/sparkle.yaml',
                        'builtin:amiga', 'builtin:amigachrome', 'builtin:amigafire', 'builtin:cute', 'builtin:scroller']
                spec = opts[(opts.index(cur) + 1) % len(opts)] if cur in opts else opts[0]
            self.font_override = spec
            self.set_font(self._load_font_for(self.theme))
            return 'font: %s (%dx%d)%s\r\n%s\r\n' % (spec, self.font.cw, self.font.ch,
                                                     '  - animated, %d frames' % len(self.font.frames) if self.font.animated else '',
                                                     'The quick brown fox jumps over the lazy dog 0123456789 😀🔥' if self.font.animated else '')
        if c == 'error':
            return ('\x1b[31;1mTraceback (most recent call last):\r\n  File "overkill.py", line 1\r\n'
                    'FatalError: too awesome\x1b[0m\r\n', 1)
        if c == 'sleep' and args:
            time.sleep(min(10.0, float(args[0])))
            return 'zzz... done\r\n'
        if c == 'flood':
            return ''.join(demo.rainbow('%05d ' % i + demo.LOREM[: random.randint(20, 90)], i * 0.3) + '\r\n'
                           for i in range(400))
        if c == 'effects':
            return 'letter: ' + ' '.join(effects.APPEAR) + '\r\ndelete: ' + ' '.join(effects.VANISH) + '\r\n'
        if c == 'bgs':
            return ' '.join(backgrounds.BACKGROUNDS) + ' mine\r\n'
        if c == 'themes':
            return ' '.join(themes.list_themes()) + '\r\n'
        if c == 'effect' and args:
            self.cfg['letter_effect'] = args[0]
            return 'letter effect: %s\r\n' % args[0]
        if c == 'splash':
            from .splash import SPLASHES, make_splash
            if args and args[0] not in SPLASHES and args[0] != 'random':
                return 'splashes: %s\r\n' % ' '.join(SPLASHES)
            old = self.cfg.get('splash')
            self.cfg['splash'] = args[0] if args else 'auto'
            self.intro = make_splash(self)
            self.cfg['splash'] = old
            return ''
        if c == 'alarm':
            from . import alarms
            if not args or args[0] not in alarms.ALARMS:
                return 'alarm NAME [message]   alarms: %s   (alarm stop)\r\n' % ' '.join(alarms.ALARMS) \
                    if not (args and args[0] == 'stop') else (self.stop_alarm() or '')
            self.trigger_alarm(args[0], ' '.join(args[1:]))
            return ''
        if c == 'show':
            from . import shows
            if args and args[0] == 'stop':
                self.stop_shows()
                return ''
            if not args or args[0] not in shows.SHOWS:
                return ('show NAME [duration=8 intensity=1 palette=gold style=willow]   shows: %s   (show stop)\r\n'
                        % ' '.join(shows.SHOWS))
            name, opts = shows.parse(' '.join(args))
            self.trigger_show(name, **opts)
            return ''
        if c == 'cursors':
            from . import cursors
            return 'styles : ' + ' '.join(cursors.CURSORS) + '\r\neffects: ' + ' '.join(cursors.CURSOR_EFFECTS) + '\r\n'
        if c == 'cursor' and args:
            self.cfg['cursor_style'] = args[0]
            self.cfg['cursor_effects'] = [f for f in args[1:] if f != 'none'] if len(args) > 1 else None
            for p in self.all_panes():
                p.reset_cursor()
            return 'cursor: %s %s\r\n' % (args[0], ' '.join(args[1:]))
        if c == 'delete' and args:
            self.cfg['delete_effect'] = args[0]
            return 'delete effect: %s\r\n' % args[0]
        if c == 'bg' and args:
            self.cfg['background'] = args[0].split(',')
            self.apply_theme(self.theme)
            return ''
        if c == 'theme' and args:
            self.cfg['background'] = None
            self.cfg['letter_effect'] = self.cfg['delete_effect'] = None
            self.cfg['cursor_style'] = self.cfg['cursor_effects'] = None
            self.apply_theme(themes.load_theme(args[0]))
            return 'theme: %s\r\n' % self.theme['name']
        if c == 'miner':
            self.cfg['miner'] = not bool(self.mine)
            self.apply_theme(self.theme)
            return 'EMERALD MINE %s\r\n' % ('ON' if self.mine else 'off')
        r = self.plugins.emit('command', cmd)
        if isinstance(r, str):
            return r
        return ('%s: command not found (try help)\r\n' % c, 127)

    # ------------------------------------------------------------ hotkeys
    def cycle(self, lst, cur, step=1):
        lst = list(lst)
        i = lst.index(cur) if cur in lst else -1
        return lst[(i + step) % len(lst)]

    def hotkey(self, key, mods):
        name = pygame.key.name(key)
        k = key
        K = pygame
        if name in self.plugins.hotkeys:
            p, fn, desc = self.plugins.hotkeys[name]
            try:
                fn()
            except Exception as e:
                self.plugins.log('hotkey error %s: %s' % (p.name, e))
            return True
        th = self.theme
        pane = self.pane
        if k == K.K_h:
            self.show_help = not self.show_help
        elif k == K.K_F12:
            self.toggle_studio()
        elif k == K.K_SPACE:
            self.toggle_zen()
        elif k == K.K_t:
            self.new_tab()
        elif k == K.K_w:
            self.close_pane()
        elif k == K.K_e:
            self.split('v')
        elif k == K.K_o:
            self.split('h')
        elif K.K_1 <= k <= K.K_9:
            self.goto_tab(k - K.K_1)
        elif k == K.K_UP:
            pane.jump_prompt(-1)
        elif k == K.K_DOWN:
            pane.jump_prompt(1)
        elif k == K.K_a:
            text, m = pane.last_output()
            if text is not None:
                clip_put(text)
                self.notify('copied output of: %s' % (m.get('cmdline') or 'last command')[:40], 1.5)
            else:
                self.notify('no finished command block (shell integration?)', 2)
        elif k == K.K_F1:
            names = list(themes.list_themes())
            if names:
                n = self.cycle(names, th['name'], -1 if mods & K.KMOD_ALT else 1)
                self.cfg['background'] = None
                self.cfg['letter_effect'] = self.cfg['delete_effect'] = None
                self.cfg['cursor_style'] = self.cfg['cursor_effects'] = None
                self.apply_theme(themes.load_theme(n))
                self.notify('theme: %s  %s' % (n, self.theme.get('description', '')))
        elif k == K.K_F2:
            n = self.cycle(effects.APPEAR, self.fx.appear_name)
            self.cfg['letter_effect'] = n
            self.notify('letter effect: %s' % n)
        elif k == K.K_F3:
            n = self.cycle(effects.VANISH, self.fx.vanish_name)
            self.cfg['delete_effect'] = n
            self.notify('delete effect: %s' % n)
        elif k == K.K_u:
            from . import cursors
            cur = self.pane.cursor.name if self.pane.cursor else th.get('cursor_style', 'block')
            if mods & K.KMOD_ALT:     # Alt: cycle cursor effect sets
                sets = [[], ['glow'], ['glow', 'trail'], ['ripple'], ['orbit', 'glow'], ['sparkle', 'trail'], ['smoke'],
                        ['reticle', 'glow']]
                curfx = self.cfg.get('cursor_effects')
                curfx = list(th.get('cursor_effects') or []) if curfx is None else list(curfx)
                i = sets.index(curfx) if curfx in sets else -1
                self.cfg['cursor_effects'] = sets[(i + 1) % len(sets)]
                msg = 'cursor effects: %s' % (' + '.join(self.cfg['cursor_effects']) or 'none')
            else:
                self.cfg['cursor_style'] = self.cycle(cursors.CURSORS, cur)
                msg = 'cursor: %s' % self.cfg['cursor_style']
            for p in self.all_panes():
                p.reset_cursor()
            self.notify(msg)
        elif k == K.K_b:
            opts = [['none']] + [[b] for b in backgrounds.BACKGROUNDS] + [['starfield', 'copper'], ['plasma', 'starfield'],
                                                                          ['boing', 'copper'], ['parallax', 'starfield']]
            cur = self.cfg.get('background') or th.get('background') or ['none']
            i = opts.index(list(cur)) if list(cur) in opts else -1
            nb = opts[(i + 1) % len(opts)]
            self.cfg['background'] = nb
            self.apply_theme(th)
            self.notify('background: %s' % '+'.join(nb))
        elif k == K.K_m:
            self.cfg['miner'] = not bool(self.mine)
            self.apply_theme(th)
            self.notify('EMERALD MINE %s' % ('ON - dig, miner, dig!' if self.mine else 'off'))
        elif k == K.K_F4:
            if self.writer == 'baud':
                i = BAUDS.index(self.baud) if self.baud in BAUDS else 0
                if i + 1 < len(BAUDS):
                    self.baud = BAUDS[i + 1]
                else:
                    self.writer = 'human'
            else:
                self.writer = self.cycle(WRITER_MODES, self.writer)
                if self.writer == 'baud':
                    self.baud = BAUDS[0]
            self.cfg['writer'] = self.writer
            self.cfg['baud'] = self.baud
            self.notify('writer: %s%s' % (self.writer, (' %d baud' % self.baud) if self.writer == 'baud' else ''))
        elif k == K.K_F5:
            crt = th['crt']
            on = any(float(crt.get(x) or 0) for x in ('scanlines', 'vignette', 'curvature', 'lcd'))
            if on:
                th['_crt_saved'] = dict(crt)
                for x in ('scanlines', 'vignette', 'curvature', 'flicker', 'noise', 'aberration', 'lcd'):
                    crt[x] = 0
            else:
                crt.update(th.get('_crt_saved') or {'scanlines': 0.35, 'vignette': 0.5, 'flicker': 0.03, 'noise': 0.2})
            self.post.configure(crt, th.get('palette_lock'))
            self.notify('CRT %s' % ('off' if on else 'ON'))
        elif k == K.K_F6:
            crt = th['crt']
            crt['bloom'] = 0 if float(crt.get('bloom') or 0) else 0.7
            self.post.configure(crt, th.get('palette_lock'))
            self.notify('bloom %s' % crt['bloom'])
        elif k == K.K_F7:
            crt = th['crt']
            crt['phosphor'] = 0 if float(crt.get('phosphor') or 0) else 0.8
            self.post.configure(crt, th.get('palette_lock'))
            self.notify('phosphor afterglow %s' % crt['phosphor'])
        elif k == K.K_F8:
            n = self.cycle(SOUND_PACKS, self.sound.pack if self.sound.enabled else 'off')
            self.sound.enabled = n != 'off'
            if n != 'off':
                self.sound.build(n)
            self.notify('sound: %s' % n)
        elif k == K.K_f:
            lst = fonts.list_fonts()
            n = self.cycle(lst, getattr(self.font, 'spec', 'builtin'))
            self.font_override = n
            self.set_font(self._load_font_for(th))
            self.notify('font: %s (%dx%d)' % (n, self.font.cw, self.font.ch))
        elif k in (K.K_EQUALS, K.K_PLUS, K.K_KP_PLUS):
            self.cfg['scale'] = min(8, self.s + 1)
            self.layout()
            self.notify('scale %dx' % self.s)
        elif k in (K.K_MINUS, K.K_KP_MINUS):
            self.cfg['scale'] = max(1, self.s - 1)
            self.layout()
            self.notify('scale %dx' % self.s)
        elif k == K.K_c:
            t = pane.selection_text()
            if t:
                clip_put(t)
                self.notify('copied %d lines' % (t.count('\n') + 1), 1.2)
        elif k == K.K_v:
            pane.paste_text(clip_get())
        elif k == K.K_l:
            pane.search = ''
        elif k == K.K_x:
            self.screenshot()
        elif k == K.K_r:
            on, p = pane.toggle_cast(os.path.join(os.getcwd(), 'recordings'))
            self.notify(('REC ● asciinema cast (Ctrl+Shift+R stops)' if on else 'cast saved: %s' % os.path.basename(p)))
        elif k == K.K_g:
            self.toggle_video('mp4')
        elif k == K.K_j:
            self.toggle_video('gif')
        else:
            return False
        return True

    def toggle_zen(self):
        if self.zen is None:
            self.zen = (self.cfg.get('letter_effect'), self.cfg.get('delete_effect'), self.cfg.get('background'),
                        dict(self.theme['crt']), self.sound.enabled, self.cfg.get('miner'), self.theme.get('palette_lock'))
            self.cfg.update(letter_effect='none', delete_effect='none', background=['none'], miner=False)
            for x in self.theme['crt']:
                self.theme['crt'][x] = 0
            self.theme['palette_lock'] = None
            self.sound.enabled = False
            self.apply_theme(self.theme)
            self.notify('ZEN mode - clean & fast')
        else:
            le, de, bg, crt, snd, mi, lock = self.zen
            self.zen = None
            self.cfg.update(letter_effect=le, delete_effect=de, background=bg, miner=mi)
            self.theme['crt'].update(crt)
            self.theme['palette_lock'] = lock
            self.sound.enabled = snd
            self.apply_theme(self.theme)
            self.notify('OVERKILL mode restored')

    def toggle_studio(self):
        if self.studio is None:
            from .studio import Studio
            self.studio = Studio(self)
            self.studio_w = self.studio.width
        else:
            self.studio = None
            self.studio_w = 0
        self.layout()

    # ------------------------------------------------------------ capture
    def screenshot(self):
        d = os.path.join(os.getcwd(), 'screenshots')
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, time.strftime('pyterm-%Y%m%d-%H%M%S.png'))
        pygame.image.save(self.presenter.screenshot(), p)
        self.notify('screenshot saved: %s' % os.path.basename(p))
        return p

    def start_video(self, path, fixed=False):
        from .recorder import VideoRecorder
        self.video = VideoRecorder(path, fps=int(self.cfg.get('record_fps', 30)), fixed_step=fixed)
        self.notify('REC ● %s' % os.path.basename(path), 2)

    def stop_video(self):
        if not self.video:
            return
        v = self.video
        self.video = None
        out = v.stop()
        msg = 'video saved: %s (%d frames%s)' % (os.path.basename(out or '?'), v.count,
                                                ', %d dropped' % v.dropped if v.dropped else '')
        if v.error:
            msg = 'video error: %s' % v.error
        self.notify(msg, 4)
        print('[pyterm] ' + msg)

    def toggle_video(self, fmt):
        if self.video:
            self.stop_video()
            return
        d = os.path.join(os.getcwd(), 'recordings')
        os.makedirs(d, exist_ok=True)
        self.start_video(os.path.join(d, time.strftime('pyterm-%Y%m%d-%H%M%S.') + fmt))

    # ------------------------------------------------------------ events
    def to_virtual(self, pos):
        W, H = self.presenter.size()
        dw, dh = self.vw * self.s, self.vh * self.s
        dx = (W - self.studio_w - dw) // 2
        dy = (H - dh) // 2
        return ((pos[0] - dx) // self.s, (pos[1] - dy) // self.s)

    def pane_at(self, vpos):
        for p in self.tab.panes():
            if p.rect.inflate(6, 4).collidepoint(vpos):
                return p
        return None

    def handle(self, ev):
        if self.studio and self.studio.handle(ev):
            return
        t = ev.type
        if t == pygame.QUIT:
            self.running = False
        elif t == pygame.VIDEORESIZE:
            self.presenter.resized(ev.w, ev.h)
            self.layout()
        elif t == getattr(pygame, 'WINDOWFOCUSLOST', -1):
            self.focused_window = False
        elif t == getattr(pygame, 'WINDOWFOCUSGAINED', -1):
            self.focused_window = True
        elif t == getattr(pygame, 'WINDOWMINIMIZED', -1):
            self.minimized = True
        elif t in (getattr(pygame, 'WINDOWRESTORED', -1), getattr(pygame, 'WINDOWSHOWN', -1),
                   getattr(pygame, 'WINDOWEXPOSED', -1)):
            self.minimized = False
            for p in self.all_panes():
                p.renderer.full = True
        elif t == getattr(pygame, 'WINDOWSIZECHANGED', -1):
            self.layout()
        elif t == pygame.KEYDOWN:
            self.on_key(ev)
        elif t == pygame.TEXTINPUT:
            if self.intro or self.alarm or time.time() < self._swallow_text:
                return
            pane = self.pane
            if pane.search is not None:
                pane.search += ev.text
                return
            mods = pygame.key.get_mods()
            if mods & pygame.KMOD_CTRL and mods & pygame.KMOD_SHIFT:
                return
            if mods & pygame.KMOD_LALT and not mods & pygame.KMOD_CTRL:
                return
            pane.send(ev.text)
        elif t == pygame.MOUSEMOTION:
            self.mouse_v = self.to_virtual(ev.pos)
            pane = self.pane
            if pane.selecting:
                pane.sel = (pane.sel[0], pane.cell_at(self.mouse_v))
            sc = pane.screen
            # mouse modes 1002 (drag) / 1003 (any motion): report movement in new cells
            if sc.mouse_mode in (1002, 1003) and not pane.selecting and not pygame.key.get_mods() & pygame.KMOD_SHIFT:
                held = next((i for i, b in enumerate(ev.buttons) if b), None)
                cell = pane.cell_at(self.mouse_v)
                if (held is not None or sc.mouse_mode == 1003) and cell != getattr(self, 'mouse_cell', None):
                    self.mouse_cell = cell
                    pane.backend.write(mouse_seq(3 if held is None else held, cell[0], cell[1], True, sc.mouse_sgr,
                                                 motion=True))
        elif t == pygame.MOUSEWHEEL:
            vpos = self.to_virtual(pygame.mouse.get_pos())
            pane = self.pane_at(vpos) or self.pane
            sc = pane.screen
            if sc.mouse_mode and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                cx, cy = pane.cell_at(vpos)
                for _ in range(abs(ev.y)):
                    pane.backend.write(mouse_seq(64 if ev.y > 0 else 65, cx, cy, True, sc.mouse_sgr))
            elif sc.using_alt:
                pane.backend.write(('\x1b[A' if ev.y > 0 else '\x1b[B') * abs(ev.y) * 3)
            else:
                pane.scroll_view(ev.y * 3)
        elif t == pygame.MOUSEBUTTONDOWN and ev.button in (1, 2, 3):
            if self.alarm:
                self.stop_alarm(dismissed=True)
                return
            vpos = self.to_virtual(ev.pos)
            for i, r in enumerate(self.tab_rects):
                if r.collidepoint(vpos):
                    self.goto_tab(i)
                    return
            pane = self.pane_at(vpos)
            if pane is None:
                return
            if pane is not self.pane:
                self.tab.focus = pane
            cell = pane.cell_at(vpos)
            mods = pygame.key.get_mods()
            if ev.button == 1 and mods & pygame.KMOD_CTRL and self.cfg.get('ctrl_click_urls', True):
                pane.open_url(cell)
            elif pane.screen.mouse_mode and not mods & pygame.KMOD_SHIFT and not (
                    ev.button == 3 and self.cfg.get('right_click') == 'always'):
                # programs with mouse support get the clicks; Shift+click is always pyterm's own (select / paste)
                pane.backend.write(mouse_seq(ev.button - 1, cell[0], cell[1], True, pane.screen.mouse_sgr))
                self._app_buttons = getattr(self, '_app_buttons', set()) | {ev.button}
            elif ev.button == 1:
                pane.sel = (cell, cell)
                pane.selecting = True
            elif ev.button == 2 and self.cfg.get('middle_click_paste', True):
                pane.paste_text(clip_get())
            elif ev.button == 3 and self.cfg.get('right_click', 'copy-paste') in ('copy-paste', 'always'):
                # like Windows Terminal: right click copies the selection, or pastes when nothing is selected
                if pane.sel and pane.sel[0] != pane.sel[1]:
                    clip_put(pane.selection_text())
                    pane.sel = None
                    self.notify('copied', 0.8)
                else:
                    pane.paste_text(clip_get())
        elif t == pygame.MOUSEBUTTONUP and ev.button in (1, 2, 3):
            pane = self.pane
            if pane.selecting:
                pane.selecting = False
                if pane.sel and pane.sel[0] != pane.sel[1]:
                    if self.cfg.get('copy_on_select', True):
                        clip_put(pane.selection_text())
                        self.notify('copied', 0.8)
                else:
                    pane.sel = None
            elif pane.screen.mouse_mode and ev.button in getattr(self, '_app_buttons', ()):
                self._app_buttons.discard(ev.button)        # only release what the program saw pressed
                cell = pane.cell_at(self.to_virtual(ev.pos))
                pane.backend.write(mouse_seq(ev.button - 1, cell[0], cell[1], False, pane.screen.mouse_sgr))

    def hk_off(self, name):
        """True when the user disabled this built-in hotkey group (config: disabled_hotkeys) - the program gets the keys."""
        v = self.cfg.get('disabled_hotkeys') or ()
        if isinstance(v, str):
            v = v.split(',')
        return name in {str(x).strip().lower() for x in v}

    def on_key(self, ev):
        mods = ev.mod
        K = pygame
        if self.alarm:           # any key acknowledges the alarm and is not passed on
            if ev.key not in (K.K_LSHIFT, K.K_RSHIFT, K.K_LCTRL, K.K_RCTRL, K.K_LALT, K.K_RALT):
                self.stop_alarm(dismissed=True)
                self._swallow_text = time.time() + 0.3
            return
        if self.intro:
            self.intro.skip()
            return
        pane = self.pane
        if pane.search is not None:
            if ev.key == K.K_ESCAPE:
                pane.search = None
                pane.search_hit = None
                pane.view_offset = 0
            elif ev.key == K.K_BACKSPACE:
                pane.search = pane.search[:-1]
            elif ev.key in (K.K_RETURN, K.K_KP_ENTER):
                pane.do_search()
            return
        if (ev.key == K.K_RETURN and mods & K.KMOD_ALT and self.cfg.get('alt_enter_fullscreen', True)) or ev.key == K.K_F11:
            self.presenter.toggle_fullscreen()
            self.layout()
            return
        ctrl, shift, alt = mods & K.KMOD_CTRL, mods & K.KMOD_SHIFT, mods & K.KMOD_LALT
        if ctrl and ev.key == K.K_TAB and not self.hk_off('ctrl_tab'):
            self.goto_tab((self.tab_i + (-1 if shift else 1)) % len(self.tabs))
            return
        if ctrl and not shift and ev.key in (K.K_PAGEUP, K.K_PAGEDOWN) and len(self.tabs) > 1 and not self.hk_off('ctrl_pgup_pgdn'):
            self.goto_tab((self.tab_i + (-1 if ev.key == K.K_PAGEUP else 1)) % len(self.tabs))
            return
        if alt and not ctrl and ev.key in (K.K_LEFT, K.K_RIGHT, K.K_UP, K.K_DOWN) and len(self.tab.panes()) > 1 \
                and not self.hk_off('alt_arrows'):
            self.focus_dir(*{K.K_LEFT: (-1, 0), K.K_RIGHT: (1, 0), K.K_UP: (0, -1), K.K_DOWN: (0, 1)}[ev.key])
            return
        if ctrl and shift and not alt and not self.hk_off('ctrl+shift+' + pygame.key.name(ev.key)):
            if self.plugins.emit('key', ev):
                return
            if self.hotkey(ev.key, mods):
                return
        if self.plugins.emit('key', ev):
            return
        if ev.key == K.K_INSERT and not alt and self.cfg.get('insert_keys', True):
            # classic clipboard keys (xterm, Windows Terminal, PuTTY): Shift+Insert pastes, Ctrl+Insert copies.
            # Without this they reach the program as ESC[2;2~, which most shells print as '2~'.
            if shift and not ctrl:
                pane.paste_text(clip_get())
                return
            if ctrl and not shift:
                t = pane.selection_text()
                if t:
                    clip_put(t)
                    self.notify('copied %d lines' % (t.count('\n') + 1), 1.2)
                return
        if shift and not ctrl and not self.hk_off('shift_pgup'):
            page = pane.screen.rows - 1
            if ev.key == K.K_PAGEUP:
                return pane.scroll_view(page)
            if ev.key == K.K_PAGEDOWN:
                return pane.scroll_view(-page)
            if ev.key == K.K_HOME:
                return pane.scroll_view(10 ** 9)
            if ev.key == K.K_END:
                return pane.scroll_view(-10 ** 9)
        if not (ctrl or alt):
            if ev.key == K.K_LEFT:
                signals.left = time.time()
            elif ev.key == K.K_RIGHT:
                signals.right = time.time()
            elif ev.key in (K.K_RETURN, K.K_KP_ENTER):
                signals.boost = time.time()
        seq = key_to_seq(ev, pane.screen.app_cursor)
        if seq:
            pane.send(seq)

    def _on_cell_event(self, e):
        if e[0] == vt.EV_PUT:
            self.plugins.emit('put', e)
        else:
            self.plugins.emit('del', e)

    def drama(self, k=1.0):
        if self.t - self.drama_t < 1.5:
            return
        self.drama_t = self.t
        self.shake = max(self.shake, 0.25 * k)
        self.post.flash = max(self.post.flash, 0.5 * k)
        self.post.flash_rgb = (255, 30, 30)

    # ------------------------------------------------------------ alarms
    def trigger_alarm(self, name='redalert', message='', duration=None, sound=True):
        """start an alarm (pyterm.alarms); replaces one that is already running"""
        from . import alarms
        cls = alarms.ALARMS.get(name)
        if cls is None:
            raise ValueError('unknown alarm %r (known: %s)' % (name, ', '.join(alarms.ALARMS)))
        if self.alarm:
            self.alarm.stop()
        if self.intro:
            self.intro.skip()
        self.alarm = cls(self, message, duration=duration, sound=sound)
        self.alarm.kind = name
        self.plugins.emit('alarm', name, message)
        self.show_event('alarm')
        if self.mqtt:
            self.mqtt.alarm_changed(self.alarm)
        return self.alarm

    # ------------------------------------------------------------ shows (pyterm.shows)
    def trigger_show(self, name='fireworks', **opts):
        """start a show (fireworks, confetti, lightning, ...); the same show again is retriggered"""
        from . import shows
        cls = shows.SHOWS.get(name)
        if cls is None:
            raise ValueError('unknown show %r (known: %s)' % (name, ', '.join(shows.SHOWS)))
        if self.intro:
            self.intro.skip()
        for s in self.shows:
            if s.name == name and not s.done:
                s.retrigger(opts)
                return s
        s = cls(self, **opts)
        s.name = name
        self.shows.append(s)
        del self.shows[:-6]
        self.plugins.emit('show', name)
        if self.mqtt:
            self.mqtt.show_started(name)
        return s

    def stop_shows(self):
        for s in self.shows:
            s.stop()

    def show_event(self, event):
        """a theme can bind shows to events (theme `events:` - startup, theme, success, fail, command_ok, command_failed,
        bell, alarm, alarm_end); `--no-shows` / `shows: false` turns that off"""
        if not self.cfg.get('shows', True):
            return
        from . import shows
        for name, opts in shows.specs((self.theme.get('events') or {}).get(event)):
            try:
                self.trigger_show(name, **opts)
            except Exception as e:
                self.plugins.log('theme event %s -> %s: %s' % (event, name, e))

    def stop_alarm(self, dismissed=False):
        a = self.alarm
        if not a:
            return
        a.stop(dismissed)
        self.alarm = None
        for p in self.all_panes():
            p.renderer.full = True
        if self.mqtt:
            self.mqtt.alarm_changed(None, a)
        self.plugins.emit('alarm_end', getattr(a, 'kind', a.name), dismissed)
        self.show_event('alarm_end')

    # ------------------------------------------------------------ frame
    def is_animated(self):
        if self.intro or self.alarm or self.shows or self.notes or self.shake > 0.02 or self.post.flash > 0.02 or self.video \
                or self.t < self.anim_until or self.show_help or self.plugins.anim:
            return True
        if self.bg and self.bg.layers:
            return True
        crt = self.post
        if crt.v('flicker') or crt.v('noise') or crt.v('glitch') or crt.v('interlace'):
            return True
        if crt.v('phosphor') and time.time() - max(p.last_activity for p in self.tab.panes()) < 1.5:
            return True
        return any(p.animating() for p in self.tab.panes())

    def frame(self, dt):
        self.t += dt
        self.tooltip = None
        panes_all = self.all_panes()
        for p in panes_all:
            p.pump(dt)
        visible = self.tab.panes()
        focus = self.pane
        for p in panes_all:
            if p in visible or p.pending or p.screen.events:
                p.update(dt, p is focus)
        for p in [p for p in panes_all if p.dead]:
            self.close_pane(p)
            if not self.running:
                return
        self.energy = max(p.energy for p in self.tab.panes())
        signals.energy = self.energy
        if self.mqtt:
            self.mqtt.frame(dt)
        if self.bg:
            pass  # updated in render at bg_fps
        if self.alarm:
            self.alarm.update(dt)
            if self.alarm.done:
                self.stop_alarm(self.alarm.dismissed)
        if self.intro:
            self.intro.update(dt)
            if self.intro.done:
                self.intro = None
                for p in panes_all:
                    p.renderer.full = True
        if self._startup_shows and not self.intro:
            self._startup_shows = False
            self.show_event('startup')
        if self.shows:
            for s in self.shows:
                try:
                    s.update(dt)
                except Exception as e:
                    self.plugins.log('show %s: %s' % (s.name, e))
                    s.done = True
            for s in [s for s in self.shows if s.done]:
                self.shows.remove(s)
                self.plugins.emit('show_end', s.name)
        self.plugins.emit('frame', dt)
        self.plugins.poll()
        if int(self.t * 2) != int((self.t - dt) * 2):
            self._poll_watch()
        for n in self.notes:
            n[1] -= dt
        self.notes = [n for n in self.notes if n[1] > 0]
        if signals.shake:
            self.shake = max(self.shake, signals.shake)
            signals.shake = 0.0
        self.shake *= math.exp(-dt * 6)
        if not self.minimized:
            self.render(dt)

    def _draw_background(self, vs, dt):
        th = self.theme
        bgc = themes.hex2rgb(th['bg'])
        if not self.bg or not self.bg.layers:
            vs.fill(bgc)
            return
        bg_fps = float(self.cfg.get('bg_fps', 30) or 0)
        self._bg_t += dt
        if self.bgsurf is None or self.bgsurf.get_size() != vs.get_size() or not bg_fps or self._bg_t >= 1.0 / bg_fps:
            for layer in self.bg.layers:      # layers that mirror / react to the terminal text
                if getattr(layer, 'wants_text', False):
                    layer.text_layers = [(p.renderer.tsurf, p.rect.topleft) for p in self.tab.panes()
                                         if p.renderer.tsurf is not None and not p.screen.using_alt]
            self.bg.update(self._bg_t, self.energy)
            self._bg_t = 0.0
            if self.bgsurf is None or self.bgsurf.get_size() != vs.get_size():
                self.bgsurf = _fast_surface(vs.get_size())
            self.bg.draw(self.bgsurf, bgc, float(th.get('bg_dim', 0.4)))
        vs.blit(self.bgsurf, (0, 0))

    def render(self, dt):
        vs = self.vsurf
        th = self.theme
        self._draw_background(vs, dt)
        self._border(vs)
        if self.tabbar_visible():
            self._tabbar(vs)
        else:
            self.tab_rects = []
        focus = self.pane
        self.plugins.emit('draw_under', vs, focus.rect)
        panes = self.tab.panes()
        for p in panes:
            p.render(vs, p is focus, self.t)
        if len(panes) > 1:
            r = focus.rect.inflate(6, 4)
            pygame.draw.rect(vs, themes.hex2rgb(th.get('cursor', '#ffcc00')), r, 1)
        self.plugins.emit('draw', vs, focus.rect)
        self._overlays(vs)
        for s in self.shows:
            try:
                s.draw(vs, self)
            except Exception as e:
                self.plugins.log('show %s draw: %s' % (s.name, e))
                s.done = True
        if self.alarm:
            self.alarm.draw(vs, self)
        if self.intro:
            self.intro.draw(vs, self.renderer.colored)
        self.post.virtual(vs, dt)
        # ---- present
        pr = self.presenter
        W, H = pr.size()
        dw, dh = self.vw * self.s, self.vh * self.s
        area = pygame.Rect(0, 0, W - self.studio_w, H)
        dx = (area.width - dw) // 2
        dy = (area.height - dh) // 2
        if self.shake > 0.02:
            m = int(self.shake * 14 * self.s)
            dx += random.randint(-m, m)
            dy += random.randint(-m, m)
        dst = pygame.Rect(dx, dy, dw, dh)
        pr.begin(area, dst)
        pr.draw_main(vs, dst, self.s, area)
        if not self.intro:
            for p in panes:
                for im, rect, clip in p.image_rects(dst, self.s):
                    pr.draw_image(im, rect, clip)
        pr.post_window(self.post, dst, self.s, dt)
        if self.studio:
            rect = pygame.Rect(W - self.studio_w, 0, self.studio_w, H)
            surf = pr.panel_surface(rect)
            self.studio.draw(surf, pygame.Rect(0, 0, rect.width, rect.height), offset=rect.topleft)
            if pr.gpu:
                pr.draw_panel(surf, rect.topleft)
        if self.plugins.hooks['post']:
            ov = pr.overlay()
            self.plugins.emit('post', ov)
            if pr.gpu:
                pr.flush_overlay()

    def _tabbar(self, vs):
        cw, ch = self.font.cw, self.font.ch
        x = self.content.x
        y = self.content.y - ch - 6
        self.tab_rects = []
        for i, tab in enumerate(self.tabs):
            label = ' %d %s ' % (i + 1, tab.focus.title[:18])
            w = len(label) * cw + 4
            r = pygame.Rect(x, y, w, ch + 4)
            act = i == self.tab_i
            col = themes.hex2rgb(self.theme.get('cursor', '#ffcc00'))
            if act:
                vs.fill(col, r)
                self.draw_text(vs, r.x + 2, r.y + 2, label, (0, 0, 0))
            else:
                self.panel(vs, r, 170)
                self.draw_text(vs, r.x + 2, r.y + 2, label, (200, 200, 210))
            self.tab_rects.append(r)
            x += w + 3

    def _border(self, vs):
        th = self.theme
        fx = th.get('border_fx', 'none')
        if fx == 'none' and not th.get('border_solid'):
            return
        tr = self.content
        bc = themes.hex2rgb(th.get('border_color', '#000000'))
        W, H = vs.get_size()
        rects = [(0, 0, W, tr.top), (0, tr.bottom, W, H - tr.bottom), (0, tr.top, tr.left, tr.height),
                 (tr.right, tr.top, W - tr.right, tr.height)]
        loading = fx == 'c64' and (any(p.pending for p in self.tab.panes()) or self.energy > 0.05)
        for r in rects:
            vs.fill(bc, r)
        if loading:
            pal = self.renderer.pal
            y = 0
            rng = random.Random(int(self.t * 50))
            while y < H:
                h = rng.randint(1, 6)
                c = pal[rng.randint(0, 15)]
                for r in rects:
                    rr = pygame.Rect(r).clip((0, y, W, h))
                    if rr.width:
                        vs.fill(c, rr)
                y += h
        elif fx == 'rainbow':
            for i, r in enumerate(rects):
                a = self.t * 2 + i
                vs.fill((int(127 + 127 * math.sin(a)), int(127 + 127 * math.sin(a + 2)), int(127 + 127 * math.sin(a + 4))), r)

    def _overlays(self, vs):
        cw, ch = self.font.cw, self.font.ch
        tr = self.content
        if self.video and int(self.t * 2) % 2:
            self.draw_text(vs, tr.right - 8 * cw, tr.y, '● VIDEO', (255, 60, 60))
        y = tr.bottom - ch * 2
        for text, left, total in reversed(self.notes):
            a = min(1.0, left * 2)
            w = (len(text) + 2) * cw
            r = pygame.Rect(tr.right - w - cw, y - 2, w, ch + 4)
            self.panel(vs, r, int(170 * a))
            self.draw_text(vs, r.x + cw, r.y + 2, text, (int(255 * a), int(230 * a), int(120 * a)))
            y -= ch + 8
        if self.tooltip:
            text, (mx, my) = self.tooltip
            r = pygame.Rect(mx + 6, my - ch - 6, (len(text) + 2) * cw, ch + 4)
            r.clamp_ip(pygame.Rect(0, 0, self.vw, self.vh))
            self.panel(vs, r, 220)
            self.draw_text(vs, r.x + cw, r.y + 2, text, (255, 255, 255))
        if self.show_help:
            w = 62 * cw
            h = (len(HELP) + 4) * ch
            r = pygame.Rect(tr.centerx - w // 2, tr.centery - h // 2, w, h)
            self.panel(vs, r, 225)
            self.draw_text(vs, r.x + cw * 2, r.y + ch // 2, 'PYTERM HOTKEYS', (255, 200, 60), 1)
            for i, (k, d) in enumerate(HELP):
                if k == 'F11 / Alt+Enter' and not self.cfg.get('alt_enter_fullscreen', True):
                    k = 'F11'
                yy = r.y + ch * (i + 2)
                self.draw_text(vs, r.x + cw * 2, yy, k, (90, 220, 255))
                self.draw_text(vs, r.x + cw * 27, yy, d, (230, 230, 230))
            info = '%s | %s/%s | %d fx %d p | %.0f fps%s%s' % (
                self.theme['name'], self.fx.appear_name, self.fx.vanish_name, len(self.fx.active),
                self.fx.particles.n, self.clock.get_fps(), ' | GPU' if self.presenter.gpu else '',
                ' | eco' if self.eco else '')
            self.draw_text(vs, r.x + cw * 2, r.bottom - ch - 2, info[:60], (150, 150, 150))

    # ------------------------------------------------------------ loop
    def run(self):
        self.running = True
        fps = int(self.cfg.get('fps', 60) or 0)
        idle_fps = int(self.cfg.get('idle_fps', 30) or fps)
        bg_off_fps = int(self.cfg.get('unfocused_fps', 15) or fps)
        frames = 0
        last = time.perf_counter()
        fixed = bool(self.video and self.video.fixed_step)
        blink_phase = None
        while self.running:
            evs = pygame.event.get()
            for ev in evs:
                self.handle(ev)
            now = time.perf_counter()
            dt = (1.0 / (fps or 60)) if fixed else min(0.1, now - last)
            # ---- eco: nothing moving -> don't render at all, sleep until something happens
            animated = self.is_animated()
            backlog = any(p.backend.q.qsize() or p.needs_render() for p in self.tab.panes())
            slow = any(p.slow_anim() for p in self.tab.panes())
            ph = int(time.time() * (min(20, max(10, getattr(self.font, 'fps', 10) if self.font.animated else 10)) if slow else 2))
            self.eco = not animated and not backlog and not evs and not fixed
            if self.eco and ph == blink_phase and not self.minimized:
                if self.mqtt:
                    self.mqtt.frame(0.0)
                pygame.time.wait(15)
                if not any(p.backend.q.qsize() for p in self.all_panes()):
                    continue
            blink_phase = ph
            last = now
            self.frame(dt)
            if not self.running:
                break
            if not self.minimized:
                if self.video:
                    self.video.add(self.presenter.frame_surface())
                self.presenter.finish()
            frames += 1
            if self.args.frames and frames >= self.args.frames:
                break
            if fixed:
                continue
            idle = time.time() - max(p.last_activity for p in self.tab.panes()) > 3
            if self.minimized:
                self.clock.tick(4)
            elif not self.focused_window:
                self.clock.tick(min(bg_off_fps, fps) if fps else bg_off_fps)
            elif idle and not self.intro and not self.studio:
                self.clock.tick(min(idle_fps, fps) if fps else idle_fps)
            else:
                self.clock.tick(fps)
        if self.args.screenshot:
            pygame.image.save(self.presenter.screenshot(), self.args.screenshot)
        self.stop_video()
        if self.mqtt:
            self.mqtt.stop()
        for p in self.all_panes():
            p.close()
        pygame.quit()
