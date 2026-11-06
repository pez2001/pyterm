"""Plugin system with hot reload.

A plugin is a single .py file in ./plugins (or <user config>/plugins):

    PLUGIN = {'name': 'clock', 'description': 'pixel clock overlay'}

    def register(api):
        api.on('draw', lambda surf, rect: ...)

    def unregister(api):     # optional
        ...

Save the file -> it is reloaded instantly (all its hooks are removed first).
Errors never crash the terminal; they show up in the Studio console.
See docs/PLUGINS.md and plugins/_template.py.
"""
from __future__ import annotations

import importlib.util
import os
import time
import traceback


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = ('frame', 'draw', 'draw_under', 'post', 'key', 'output', 'put', 'del', 'bell', 'theme', 'command',
          'command_done', 'alarm', 'alarm_end')


class PluginAPI:
    def __init__(self, mgr, plugin):
        self._mgr = mgr
        self._p = plugin
        self.app = mgr.app

    # -------- state
    @property
    def screen(self):
        return self.app.screen

    @property
    def theme(self):
        return self.app.theme

    @property
    def particles(self):
        return self.app.fx.particles

    @property
    def cell(self):
        return self.app.font.cw, self.app.font.ch

    @property
    def settings(self):
        """per-plugin settings: theme['plugins'][name] merged over config['plugin_settings'][name]"""
        name = self._p.name
        out = dict((self.app.cfg.get('plugin_settings') or {}).get(name, {}))
        out.update((self.app.theme.get('plugins') or {}).get(name, {}) or {})
        return out

    # -------- hooks
    def on(self, event, fn):
        if event not in EVENTS:
            raise ValueError('unknown event %s (known: %s)' % (event, ', '.join(EVENTS)))
        self._mgr.hooks[event].append((self._p, fn))

    def register_letter_effect(self, name, cls):
        from . import effects
        cls.name = name
        effects.APPEAR[name] = cls
        if name not in effects.RANDOM_POOL:
            effects.RANDOM_POOL.append(name)
        self._p.owned.append(('appear', name))

    def register_delete_effect(self, name, fn):
        from . import effects
        effects.VANISH[name] = fn
        self._p.owned.append(('vanish', name))

    def register_background(self, name, cls):
        from . import backgrounds
        cls.name = name
        backgrounds.BACKGROUNDS[name] = cls
        self._p.owned.append(('bg', name))

    def register_cursor(self, name, cls):
        """cursor style: subclass pyvterm.cursors.CursorStyle (update(dt, st), draw(surf, ox, oy, st))"""
        from . import cursors
        cls.name = name
        cursors.CURSORS[name] = cls
        self._p.owned.append(('cursor', name))
        self._reset_cursors()

    def register_cursor_effect(self, name, cls):
        """cursor effect: subclass pyvterm.cursors.CursorEffect (layer 'under' | 'over')"""
        from . import cursors
        cls.name = name
        cursors.CURSOR_EFFECTS[name] = cls
        self._p.owned.append(('cursor_fx', name))
        self._reset_cursors()

    def register_splash(self, name, cls):
        """boot splash: subclass pyvterm.splash.Splash (update(dt), draw(surf, colored), skip())"""
        from . import splash
        cls.name = name
        splash.SPLASHES[name] = cls
        self._p.owned.append(('splash', name))

    def register_alarm(self, name, cls):
        """alarm: subclass pyvterm.alarms.Alarm (sound(snd) -> (Sound, repeat), draw(surf, app)); triggerable from
        Home Assistant, the demo shell and app.trigger_alarm(name, message)"""
        from . import alarms
        cls.name = name
        alarms.ALARMS[name] = cls
        self._p.owned.append(('alarm', name))
        mq = getattr(self.app, 'mqtt', None)
        if mq:
            mq.rediscover()

    def _reset_cursors(self):
        for p in getattr(self.app, 'all_panes', lambda: [])():
            p.reset_cursor()

    def add_hotkey(self, key, fn, desc=''):
        """key: pygame key name for Ctrl+Shift+<key>, e.g. 'k' or 'f5'"""
        self._mgr.hotkeys[key.lower()] = (self._p, fn, desc)

    # -------- actions
    def notify(self, text, secs=2.5):
        self.app.notify(text, secs)

    def write(self, text):
        """send input to the running program"""
        self.app.backend.write(text)

    def feed(self, text):
        """display text as if the program printed it"""
        self.app.inject(text)

    def draw_text(self, surf, x, y, text, rgb=(255, 255, 255), style=0):
        return self.app.draw_text(surf, x, y, text, rgb, style)

    def log(self, msg):
        self._mgr.log('[%s] %s' % (self._p.name, msg))

    def animating(self, on=True):
        """tell pyvterm your plugin is animating (True) or idle (False). While any plugin
        animates, pyvterm never drops into its zero-CPU eco mode."""
        if on:
            self._mgr.anim.add(self._p)
        else:
            self._mgr.anim.discard(self._p)


class Plugin:
    def __init__(self, path):
        self.path = path
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.module = None
        self.mtime = 0
        self.error = None
        self.enabled = True
        self.owned = []
        self.meta = {}


class PluginManager:
    def __init__(self, app, dirs=None, enabled=True):
        self.app = app
        self.enabled = enabled
        self.dirs = [os.path.join(ROOT, 'plugins')]
        from .config import user_dir
        self.dirs.append(os.path.join(user_dir(), 'plugins'))
        self.dirs += list(dirs or [])
        self.plugins = {}
        self.hooks = {e: [] for e in EVENTS}
        self.hotkeys = {}
        self.anim = set()
        self.console = []
        self.disabled = set(app.cfg.get('disabled_plugins') or [])
        self._last_scan = 0

    def log(self, msg):
        self.console.append(msg)
        del self.console[:-200]
        print('[plugin] ' + msg)

    # ------------------------------------------------------------ loading
    def scan(self):
        if not self.enabled:
            return
        seen = set()
        for d in self.dirs:
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if not fn.endswith('.py') or fn.startswith('_'):
                    continue
                path = os.path.join(d, fn)
                seen.add(path)
                p = self.plugins.get(path)
                try:
                    mt = os.path.getmtime(path)
                except OSError:
                    continue
                if p is None:
                    p = Plugin(path)
                    p.enabled = p.name not in self.disabled
                    self.plugins[path] = p
                if mt != p.mtime:
                    p.mtime = mt
                    if p.enabled:
                        self.load(p)
        for path in list(self.plugins):
            if path not in seen:
                self.unload(self.plugins.pop(path))

    def load(self, p):
        if p.module is not None:
            self.unload(p)
        try:
            spec = importlib.util.spec_from_file_location('pyvterm_plugin_%s_%d' % (p.name, int(time.time() * 1000)), p.path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            p.meta = dict(getattr(mod, 'PLUGIN', {}) or {})
            p.module = mod
            if hasattr(mod, 'register'):
                mod.register(PluginAPI(self, p))
            p.error = None
            self.log('loaded %s' % p.name)
        except Exception:
            p.error = traceback.format_exc()
            p.module = None
            self.log('ERROR loading %s:\n%s' % (p.name, p.error))
            self._remove_hooks(p)

    def _remove_hooks(self, p):
        for e in self.hooks:
            self.hooks[e] = [(o, f) for (o, f) in self.hooks[e] if o is not p]
        for k in [k for k, v in self.hotkeys.items() if v[0] is p]:
            del self.hotkeys[k]
        from . import alarms, backgrounds, cursors, effects, splash
        had_cursor = False
        for kind, name in p.owned:
            reg = {'appear': effects.APPEAR, 'vanish': effects.VANISH, 'bg': backgrounds.BACKGROUNDS,
                   'cursor': cursors.CURSORS, 'cursor_fx': cursors.CURSOR_EFFECTS, 'splash': splash.SPLASHES,
                   'alarm': alarms.ALARMS}[kind]
            had_cursor = had_cursor or kind.startswith('cursor')
            reg.pop(name, None)
            if kind == 'appear' and name in effects.RANDOM_POOL:
                effects.RANDOM_POOL.remove(name)
        p.owned.clear()
        self.anim.discard(p)
        if had_cursor and hasattr(self.app, 'all_panes'):
            for pane in self.app.all_panes():
                pane.reset_cursor()

    def unload(self, p):
        if p.module is not None and hasattr(p.module, 'unregister'):
            try:
                p.module.unregister(PluginAPI(self, p))
            except Exception:
                self.log('error in %s.unregister: %s' % (p.name, traceback.format_exc()))
        self._remove_hooks(p)
        p.module = None

    def set_enabled(self, p, on):
        p.enabled = on
        if on:
            self.disabled.discard(p.name)
            self.load(p)
        else:
            self.disabled.add(p.name)
            self.unload(p)

    def poll(self):
        now = time.time()
        if now - self._last_scan > 0.7:
            self._last_scan = now
            self.scan()

    # ------------------------------------------------------------ dispatch
    def emit(self, event, *args):
        res = None
        for p, fn in list(self.hooks[event]):
            try:
                r = fn(*args)
                if r is not None:
                    res = r
                    if event == 'key' and r:
                        return True
            except Exception:
                p.error = traceback.format_exc()
                self.log('ERROR in %s (%s):\n%s' % (p.name, event, p.error))
                self._remove_hooks(p)
        return res

    def filter_output(self, text):
        for p, fn in list(self.hooks['output']):
            try:
                r = fn(text)
                if isinstance(r, str):
                    text = r
            except Exception:
                p.error = traceback.format_exc()
                self.log('ERROR in %s (output):\n%s' % (p.name, p.error))
                self._remove_hooks(p)
        return text

    def new_plugin(self, name):
        """scaffold a plugin from the template and load it"""
        safe = ''.join(c for c in name.lower() if c.isalnum() or c == '_') or 'my_plugin'
        path = os.path.join(self.dirs[0], safe + '.py')
        if not os.path.exists(path):
            with open(os.path.join(self.dirs[0], '_template.py'), 'r', encoding='utf-8') as fh:
                src = fh.read().replace('my_plugin', safe)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(src)
        self.scan()
        return path
