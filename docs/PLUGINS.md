# Plugins

A plugin is one `.py` file in `plugins/` (or `%APPDATA%\pyterm\plugins`, `~/.config/pyterm/plugins`).
Files starting with `_` are ignored (`_template.py` is the scaffold the Studio copies).

* **Hot reload**: save the file and it is unloaded (all its hooks, hotkeys, effects removed) and loaded again.
* **Safe**: an exception disables only the failing plugin; the traceback shows in Studio → PLUGINS / CONSOLE.
* **Workbench**: Studio → PLUGINS → *Create & open* scaffolds a plugin and opens it in your editor.

```python
PLUGIN = {'name': 'hello', 'description': 'shown in the Studio', 'author': 'me'}

def register(api):
    api.on('draw', lambda surf, rect: api.draw_text(surf, rect.x, rect.y, 'hi!', (255, 200, 0)))
    api.add_hotkey('y', lambda: api.notify('Ctrl+Shift+Y pressed'), 'say hi')

def unregister(api):   # optional
    pass
```

## Events — `api.on(event, fn)`

| event | signature | notes |
|---|---|---|
| `frame` | `fn(dt)` | every frame, before rendering |
| `draw_under` | `fn(surf, rect)` | after the background, below the text (virtual pixel surface) |
| `draw` | `fn(surf, rect)` | above text and effects; `rect` = terminal area |
| `post` | `fn(window)` | on the final window surface (after scaling + CRT) |
| `key` | `fn(event) -> bool` | pygame KEYDOWN; return True to swallow it |
| `output` | `fn(text) -> str or None` | program output before parsing; return modified text |
| `put` / `del` | `fn(ev)` | `(type, x, y, char, attr)` letter appeared / vanished |
| `bell` | `fn()` | BEL |
| `theme` | `fn(theme)` | theme applied |
| `command` | `fn(cmd) -> str or None` | demo shell commands nobody else handled |
| `show` / `show_end` | `fn(name)` | a show (fireworks, confetti, ...) started / ended |
| `alarm` / `alarm_end` | `fn(name, message)` / `fn(name, dismissed)` | an alarm started / ended (dismissed = someone pressed a key) |

## API

| member | |
|---|---|
| `api.app` | the App (screen, fx, renderer, sound, post, theme, cfg …) |
| `api.screen` | `vt.Screen`: `chars`, `attrs`, `cx`, `cy`, `cols`, `rows`, `scrollback` |
| `api.theme`, `api.settings` | theme dict; this plugin's settings (`theme.plugins.<name>` over `config.plugin_settings.<name>`) |
| `api.cell` | `(cell_w, cell_h)` in virtual pixels |
| `api.particles` | the numpy particle system — `emit(n, x, y, vx=, vy=, life=, col=, pal=, grav=, drag=, add=, delay=, kind=HOMING, tx=, ty=, travel=, ease=)`; y is in *virtual rows* (add `api.app.fx.voff * cell_h`) |
| `api.register_letter_effect(name, cls)` | subclass `pyterm.effects.Appear` (`start`, `update(dt)`, `draw(surf, ox, oy)`) |
| `api.register_delete_effect(name, fn)` | `fn(manager, x, vy, char, attr)` – usually emits particles |
| `api.register_background(name, cls)` | subclass `pyterm.backgrounds.Background` (`resize`, `update(dt, energy)`, `draw(surf, first)`) |
| `api.register_cursor(name, cls)` | cursor style: subclass `pyterm.cursors.CursorStyle` (`update(dt, st)`, `draw(surf, ox, oy, st)`) — docs/CURSORS.md |
| `api.register_cursor_effect(name, cls)` | cursor effect: subclass `pyterm.cursors.CursorEffect` (`layer = 'under'` or `'over'`) |
| `pyterm.signals` | what the terminal is doing, for scenes: `typing`, `enter`, `bell` (timestamps), `cmd` = (exit, secs, t), `energy`, `cursor_x/y`, `letters` (`take_letters(last_seq)` → (seq, char, x, y, typed)), set `shake` to shake the screen |
| background `wants_text = True` | the layer gets `self.text_layers = [(text_surface, (x, y)), ...]` each frame (see `pyterm/water.py`) |
| `api.register_splash(name, cls)` | boot sequence: subclass `pyterm.splash.Splash` (`update(dt)`, `draw(surf, colored)`, `skip()`, set `done`); themes use it with `splash: name` |
| `api.register_alarm(name, cls)` | alarm (sound + full-screen display): subclass `pyterm.alarms.Alarm` – `sound(snd)` → `(pygame Sound, repeat seconds)`, `draw(surf, app)`; helpers `self.card(surf, app, title, rgb, icon=)`, `self.edge(surf, rgb, width, k)`, `self.tint(surf, rgb)`; class attrs `duration`, `label`, `ha_icon`. Gets its own Home Assistant button automatically – example: `plugins/party_alarm.py` |
| `api.register_show(name, cls)` | show (full-window effect over everything, several at once, never takes keys): subclass `pyterm.shows.Show` – `start()`, `step(dt)`, `draw(surf, app)`; helpers `self.emit(...)` (particles, 2x2 on big windows), `self.glow(surf, x, y, r, rgb)`, `self.layer(surf)` (additive scratch surface), `self.snd('boom')`, `self.pal` (palette option), `self.intensity`, `self.fade`; class attrs `duration`, `label`, `ha_icon`. Gets a Home Assistant button and can be named in a theme's `events:` |
| `api.app.trigger_show(name, **options)` / `api.app.stop_shows()` | start a show (`duration`, `intensity`, `palette`, `sound`, ...) / end all |
| `api.app.trigger_alarm(name, message, duration=None)` / `api.app.stop_alarm()` | start / stop an alarm yourself |
| `api.add_hotkey(key, fn, desc)` | Ctrl+Shift+`key` (pygame key name) |
| `api.notify(text)` | on-screen message |
| `api.write(text)` | type into the running program |
| `api.feed(text)` | display text as if the program printed it (ANSI allowed) |
| `api.draw_text(surf, x, y, text, rgb)` | draw with the terminal font |
| `api.log(msg)` | Studio console |

Particle palettes (`pyterm.particles`): `SOLID FIRE FADE SPARKLE FLASH COOL RAINBOW`;
motion: `BALLISTIC HOMING`; easing for homing: `SMOOTH FALL BACK LINEAR`.

Shipped examples: `sine_scroller.py`, `fireworks.py` (Konami code!), `hud_meter.py`, `example_effect.py`
(adds letter effect `spiral`, delete effect `confetti`, background `rain`), `cursor_demo.py` (cursor style `ghost`,
cursor effect `comet`).
