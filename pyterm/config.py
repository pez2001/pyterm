"""Configuration: defaults <- config.yaml (project dir, then user dir) <- command line."""
from __future__ import annotations

import argparse
import os
import sys

from . import yamlio

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')   # bundled assets (themes, fonts, sounds, plugins, shell, config.yaml)

DEFAULTS = {
    'theme': 'neon',
    'font': None,            # None -> theme font -> builtin
    'font_size': None,
    'antialias': None,
    'scale': None,           # pixel scale; None -> theme / auto (2 for pixel fonts, 1 for TTF)
    'width': 1280,
    'height': 800,
    'fullscreen': False,
    'fps': 60,
    'shell': None,
    'backend': 'auto',       # auto | pty | pipes
    'encoding': 'utf-8',     # utf-8 | cp437 | ascii | latin-1 | any python codec
    'scrollback': 5000,
    'max_effects': 900,      # simultaneous letter effects (governor)
    'max_particles': 120000,
    'letter_effect': None,   # override theme
    'delete_effect': None,
    'background': None,
    'splash': 'auto',        # boot splash: auto (theme's choice) | demo | c64 | none | random (+plugins)
    'mqtt': {},              # MQTT / Home Assistant (see docs/HOMEASSISTANT.md), off unless enabled
    'cursor_style': None,    # override theme
    'cursor_effects': None,
    'writer': None,          # instant | smart | baud | human
    'baud': None,
    'sound': True,
    'volume': None,
    'miner': None,
    'plugins': True,
    'plugin_dirs': [],
    'demo': False,
    'cat': None,
    'cwd': None,
    'studio': False,
    'gpu': 'auto',            # auto | true | false  - SDL2 GPU presenter
    'vsync': True,
    'idle_fps': 30,           # fps after 3 s without output/input (animated themes)
    'unfocused_fps': 15,
    'bg_fps': 30,             # background effects are rendered at this rate and cached
    'smooth_scroll_lines': 3, # pixel-smooth scroll for up to N lines per frame (0 = off)
    'shell_integration': True,
    'alt_effects': None,     # full-screen apps: off | typed | all  (None = theme, default typed)
    'right_click': 'copy-paste',  # right mouse button: copy-paste (copy selection / paste) | off
    'cell_bg_alpha': None,   # 0..255 alpha of cells with a background color (None = theme / auto)
    'osc52': 'write',        # programs may set the clipboard (vim, mc, tmux, ssh...): off | write | read-write
    'command_blocks': True,
    'notify_after': 8,        # seconds - notify when longer commands finish
    'tabbar': 'auto',         # auto | always | never
    'dim_inactive': True,
    'record_fps': 30,
    'banner': True,
}


def _user_base():
    if sys.platform.startswith('win'):
        return os.environ.get('APPDATA') or os.path.expanduser('~')
    return os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')


_migrated = set()


def _migrate_legacy(new_dir):
    """pyterm 1.0.0 was called pyvterm and kept its settings in a 'pyvterm' folder. On first start,
    copy that folder to the new location (copy, not move - the old folder stays untouched)."""
    if new_dir in _migrated:
        return
    _migrated.add(new_dir)
    old_dir = os.path.join(os.path.dirname(new_dir), 'pyvterm')
    if os.path.isdir(new_dir) or not os.path.isdir(old_dir):
        return
    try:
        import shutil
        shutil.copytree(old_dir, new_dir)
        print('[pyterm] copied your settings from %s to %s (the old folder was left in place)' % (old_dir, new_dir))
    except Exception as e:
        print('[pyterm] could not copy settings from %s: %s' % (old_dir, e))


def user_dir():
    d = os.path.join(_user_base(), 'pyterm')
    _migrate_legacy(d)
    return d


def load_config_file():
    cfg = {}
    for base in (os.path.join(ROOT, 'config'), os.path.join(user_dir(), 'config')):
        p = yamlio.find(base)
        if p:
            try:
                cfg.update(yamlio.load(p) or {})
            except Exception as e:
                print('[pyterm] bad config %s: %s' % (p, e))
    return cfg


def parse_args(argv=None):
    ap = argparse.ArgumentParser(prog='pyterm', description='pixel-art overkill terminal emulator',
                                 epilog=RANDOM_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('-t', '--theme', help='theme name | random | random:a,b,c')
    ap.add_argument('-f', '--font', help='builtin | sys:Consolas | path/to/font.(ttf|bdf|psf|png) | random')
    ap.add_argument('--random', action='store_true', help='random theme and random font')
    ap.add_argument('-s', '--font-size', type=int)
    ap.add_argument('--no-aa', dest='antialias', action='store_false', default=None, help='crisp TTF rendering')
    ap.add_argument('-x', '--scale', type=int, help='pixel scale factor')
    ap.add_argument('--size', type=parse_size, metavar='WxH', help='window size in pixels, e.g. 1280x720')
    ap.add_argument('--fullscreen', action='store_true', default=None)
    ap.add_argument('-e', '--shell', help='command to run')
    ap.add_argument('--backend', choices=['auto', 'pty', 'pipes'])
    ap.add_argument('--encoding', help='utf-8 | cp437 | ascii | latin-1 ...')
    ap.add_argument('--effect', dest='letter_effect', help='letter effect | random (per letter) | pick | random:a,b')
    ap.add_argument('--delete-effect', help='delete effect | random (per letter) | pick | random:a,b')
    ap.add_argument('--cursor', dest='cursor_style', help='cursor style: block underline beam outline miner hero settler train ... | random')
    ap.add_argument('--cursor-fx', dest='cursor_effects', help='comma separated cursor effects: glow,trail,ripple,sparkle,orbit,smoke,reticle | random | random2')
    ap.add_argument('--bg', dest='background', help='comma separated background layers | random | random2 | random:a,b')
    ap.add_argument('--writer', choices=['instant', 'smart', 'baud', 'human'])
    ap.add_argument('--baud', type=int)
    ap.add_argument('--no-sound', dest='sound', action='store_false', default=None)
    ap.add_argument('--miner', action='store_true', default=None, help='EMERALD MINE mode')
    ap.add_argument('--no-plugins', dest='plugins', action='store_false', default=None)
    ap.add_argument('--fps', type=int)
    ap.add_argument('--demo', action='store_true', default=None, help='built-in demo show, no shell')
    ap.add_argument('--cat', help='play a file (ANSI art) instead of a shell')
    ap.add_argument('--list', action='store_true', help='list themes, effects, backgrounds, fonts')
    ap.add_argument('--export-font', metavar='PNG', help='export current font as editable PNG sheet')
    ap.add_argument('--studio', action='store_true', default=None, help='open the Studio (theme/font/plugin editor) with live preview')
    ap.add_argument('--record', metavar='FILE', help='record video (.mp4 or .gif); with --frames renders offline')
    ap.add_argument('--gpu', choices=['auto', 'true', 'false'])
    ap.add_argument('--alt-effects', dest='alt_effects', choices=['off', 'typed', 'all'],
                    help='letter effects in full-screen apps (vim, mc, ...): off, typed letters only (default), all')
    ap.add_argument('--cell-bg-alpha', dest='cell_bg_alpha', type=int, metavar='0-255',
                    help='see-through colored cell backgrounds (mc, htop ...) over the background scene')
    ap.add_argument('--splash', help='boot splash: demo | c64 | none | random (+plugins); default: the theme\'s')
    ap.add_argument('--mqtt', dest='mqtt_url', nargs='?', const=True, metavar='URL',
                    help='enable MQTT / Home Assistant, optionally mqtt://user:pass@host:1883 (mqtts:// for TLS)')
    ap.add_argument('--no-mqtt', action='store_true', help='disable MQTT even if config.yaml enables it')
    ap.add_argument('--mqtt-debug', action='store_true', help='print every MQTT message sent / received')
    ap.add_argument('--benchmark', action='store_true', help='headless performance benchmark')
    ap.add_argument('--screenshot', metavar='PNG', help=argparse.SUPPRESS)
    ap.add_argument('--frames', type=int, default=0, help=argparse.SUPPRESS)
    return ap.parse_args(argv)


RANDOM_HELP = """random selection - every option that takes a name from a list also accepts
  random            pick one of all available at startup
  random:a,b,c      pick one of your own shortlist
  random3           (backgrounds, cursor effects) stack 3 random ones
examples:
  pyterm -t random
  pyterm -t random:c64,amiga,gameboy,nes_famicom
  pyterm -t random -f random --cursor random --cursor-fx random2 --bg random2
  pyterm --effect pick --delete-effect pick      (effects: 'random' = a different effect for every
                                                   letter, 'pick' = one random effect for the session)
  pyterm --random                                 shorthand: random theme + random font
"""


def _choices():
    """lists to choose from; imported lazily (no display needed)"""
    from . import backgrounds, cursors, effects, fonts, themes
    return {
        'theme': [t for t in themes.list_themes()],
        'font': [f for f in fonts.list_fonts() if not f.startswith(('sys:', 'builtin:scroller'))],
        'letter_effect': [e for e in effects.APPEAR if e not in ('none', 'random')],
        'delete_effect': [e for e in effects.VANISH if e not in ('none', 'random')],
        'background': [b for b in backgrounds.BACKGROUNDS if b not in ('weather', 'seasonal')],
        # layers that stay see-through, so they can go on top of another one
        'overlay': [b for b, c in backgrounds.BACKGROUNDS.items() if not getattr(c, 'opaque', False) and b != 'weather'],
        'cursor_style': list(cursors.CURSORS),
        'cursor_effects': list(cursors.CURSOR_EFFECTS),
    }


def resolve_random(cfg, rng=None):
    """replace 'random' / 'random:a,b' / 'randomN' / 'pick' selectors with concrete names.
    Returns a list of (option, chosen) for the startup message."""
    import random as _r
    rng = rng or _r.Random()
    picked = []
    lists = None
    multi = ('background', 'cursor_effects')
    for key in ('theme', 'font', 'letter_effect', 'delete_effect', 'background', 'cursor_style', 'cursor_effects'):
        v = cfg.get(key)
        if isinstance(v, (list, tuple)):
            v = ','.join(v) if len(v) != 1 else v[0]
        if not isinstance(v, str):
            continue
        sel = v.strip()
        low = sel.lower()
        effect_pick = key in ('letter_effect', 'delete_effect') and low == 'pick'
        if not (low.startswith('random') or effect_pick):
            continue
        if key in ('letter_effect', 'delete_effect') and low == 'random':
            continue                   # 'random' already means: a different effect for every letter
        if lists is None:
            lists = _choices()
        pool = lists[key]
        count = 1
        if ':' in sel:
            pool = [x.strip() for x in sel.split(':', 1)[1].split(',') if x.strip()] or pool
        elif low[6:].isdigit() and key in multi:
            count = max(1, min(6, int(low[6:])))
        if not pool:
            continue
        if key == 'background' and count > 1 and ':' not in sel:
            first = rng.choice(pool)
            over = [b for b in lists['overlay'] if b != first]
            choice = [first] + rng.sample(over, min(count - 1, len(over)))
            cfg[key] = choice
            picked.append((key, '+'.join(choice)))
        elif key in multi:
            choice = rng.sample(pool, min(count, len(pool)))
            cfg[key] = choice
            picked.append((key, '+'.join(choice)))
        else:
            choice = rng.choice(pool)
            cfg[key] = choice
            picked.append((key, choice))
    return picked


def parse_size(text):
    """'1280x720' -> (1280, 720); raises argparse.ArgumentTypeError with a readable message"""
    w, sep, h = str(text).lower().replace(' ', '').partition('x')
    try:
        if not sep:
            raise ValueError
        w, h = int(w), int(h)
    except ValueError:
        raise argparse.ArgumentTypeError('%r is not a size - use WIDTHxHEIGHT, e.g. 1280x720' % text) from None
    if w < 1 or h < 1:
        raise argparse.ArgumentTypeError('size must be positive, got %r' % text)
    return w, h


def build_config(argv=None):
    a = parse_args(argv)
    cfg = dict(DEFAULTS)
    cfg.update(load_config_file())
    for k, v in vars(a).items():
        if v is not None and k in cfg:
            cfg[k] = v
    if a.size:
        cfg['width'], cfg['height'] = a.size
    if not (cfg.get('demo') or cfg.get('cat') or getattr(a, 'benchmark', False) or getattr(a, 'list', False)
            or getattr(a, 'export_font', None)):
        from .backend import shell_problem
        problem = shell_problem(cfg.get('shell'))
        if problem:
            print('pyterm: error: %s' % problem, file=sys.stderr)
            sys.exit(2)
    if isinstance(cfg.get('background'), str):
        cfg['background'] = [b for b in cfg['background'].split(',') if b] or ['none']
    if getattr(a, 'random', False):
        if not a.theme:
            cfg['theme'] = 'random'
        if not a.font:
            cfg['font'] = 'random'
    from .mqtt import DEFAULTS as MQTT_DEFAULTS, parse_url
    m = dict(MQTT_DEFAULTS, **(cfg.get('mqtt') or {}))
    if a.mqtt_url:
        m = parse_url(a.mqtt_url, m)
        m['enabled'] = True
    if a.no_mqtt:
        m['enabled'] = False
    if a.mqtt_debug:
        m['debug'] = True
    cfg['mqtt'] = m
    cfg['_random'] = resolve_random(cfg)
    for key, val in cfg['_random']:
        print('[pyterm] random %s: %s' % (key.replace('_', ' '), val))
    if isinstance(cfg.get('cursor_effects'), str):
        cfg['cursor_effects'] = [f for f in cfg['cursor_effects'].split(',') if f and f != 'none']
    if a.cat:
        cfg['encoding'] = a.encoding or 'cp437'
    return cfg, a
