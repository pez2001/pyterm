"""Themes: YAML files in ./themes (and the user config dir). Any key missing
from a theme falls back to DEFAULT_THEME."""
from __future__ import annotations

import copy
import os

from . import yamlio

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')   # bundled assets (themes, fonts, sounds, plugins, shell, config.yaml)
THEME_DIR = os.path.join(ROOT, 'themes')


def save_dir():
    """Where new themes are written: the bundled dir when writable (source checkout), else the user dir."""
    if os.access(THEME_DIR, os.W_OK):
        return THEME_DIR
    from .config import user_dir
    return os.path.join(user_dir(), 'themes')

XTERM16 = ['#000000', '#cd0000', '#00cd00', '#cdcd00', '#0000ee', '#cd00cd', '#00cdcd', '#e5e5e5',
           '#7f7f7f', '#ff0000', '#00ff00', '#ffff00', '#5c5cff', '#ff00ff', '#00ffff', '#ffffff']

DEFAULT_THEME = {
    'name': 'default',
    'events': {},            # event -> show(s): startup theme success fail command_ok command_failed bell alarm alarm_end
    'description': '',
    'palette': XTERM16,
    'fg': '#d0d0d0',
    'bg': '#000000',
    'bg_alpha': 255,
    'cursor': '#ffcc00',
    'cursor_style': 'block',
    'cursor_effects': ['glow'],
    'cursor_params': {},
    'bold_bright': True,
    'text_shadow': False,
    'border': 6,
    'border_color': '#000000',
    'border_fx': 'none',
    'font': None,
    'font_size': 18,
    'antialias': True,
    'scale': None,
    'background': [],
    'bg_dim': 0.4,
    'bg_params': {},
    'letter_effect': 'none',
    'delete_effect': 'none',
    'writer': {'mode': 'smart', 'baud': 9600},
    'crt': {'scanlines': 0.0, 'vignette': 0.0, 'bloom': 0.0, 'phosphor': 0.0,
            'flicker': 0.0, 'noise': 0.0, 'glitch': 0.0, 'aberration': 0},
    'sound': {'pack': 'chime', 'volume': 0.4},
    'miner': False,
    'banner': None,
    'palette_lock': None,
    'plugins': {},
}


def hex2rgb(h):
    if isinstance(h, (list, tuple)):
        return tuple(int(v) for v in h[:3])
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Theme(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def build_palette(self):
        pal16 = [hex2rgb(c) for c in self['palette']][:16]
        while len(pal16) < 16:
            pal16.append(hex2rgb(XTERM16[len(pal16)]))
        pal = list(pal16)
        lv = [0, 95, 135, 175, 215, 255]
        for r in range(6):
            for g in range(6):
                for b in range(6):
                    pal.append((lv[r], lv[g], lv[b]))
        for i in range(24):
            v = 8 + i * 10
            pal.append((v, v, v))
        return pal


def theme_dirs(extra=None):
    d = [THEME_DIR]
    from .config import user_dir
    d.append(os.path.join(user_dir(), 'themes'))
    if extra:
        d.append(extra)
    return [x for x in d if os.path.isdir(x)]


def list_themes():
    names = {}
    for d in theme_dirs():
        for fn in sorted(os.listdir(d)):
            base, ext = os.path.splitext(fn)
            if ext in yamlio.EXTS:
                names[base] = os.path.join(d, fn)
    return names


def normalize_cursor(t, data=None):
    """old themes used  cursor_glow: bool / cursor_trail: bool  - map them to cursor_effects"""
    data = t if data is None else data
    fx = data.get('cursor_effects')
    if fx is None:
        fx = list(DEFAULT_THEME['cursor_effects'])
        if data.get('cursor_glow') is False and 'glow' in fx:
            fx.remove('glow')
        if data.get('cursor_trail') and 'trail' not in fx:
            fx.append('trail')
    elif isinstance(fx, str):
        fx = [f for f in fx.replace(',', ' ').split() if f != 'none']
    t['cursor_effects'] = list(fx or [])
    t.pop('cursor_glow', None)
    t.pop('cursor_trail', None)
    return t


def load_theme(name_or_path) -> Theme:
    data = {}
    path = None
    if name_or_path:
        if os.path.exists(name_or_path):
            path = name_or_path
        else:
            path = list_themes().get(name_or_path)
    if path:
        try:
            data = yamlio.load(path) or {}
        except Exception as e:
            print('[pyterm] theme %s broken: %s' % (path, e))
        data.setdefault('name', os.path.splitext(os.path.basename(path))[0])
    elif name_or_path:
        print('[pyterm] theme not found: %s' % name_or_path)
    t = Theme(_merge(DEFAULT_THEME, data))
    normalize_cursor(t, data)
    t['_path'] = path
    if t['sound'].get('pack') is False:
        t['sound']['pack'] = 'off'
    if isinstance(t['background'], str):
        t['background'] = [t['background']] if t['background'] else []
    return t


def save_theme(theme, path=None):
    """write only the keys that differ from the defaults"""
    path = path or theme.get('_path') or os.path.join(save_dir(), theme['name'] + '.yaml')
    if path.endswith('.json'):
        path = path[:-5] + '.yaml'
    out = {}
    for k, v in theme.items():
        if k.startswith('_'):
            continue
        d = DEFAULT_THEME.get(k, None)
        if isinstance(v, dict) and isinstance(d, dict):
            sub = {kk: vv for kk, vv in v.items() if d.get(kk) != vv}
            if sub:
                out[k] = sub
        elif v != d or k in ('name',):
            out[k] = v
    yamlio.dump(out, path, header='pyterm theme - edit freely, changes are hot-reloaded')
    theme['_path'] = path
    return path
