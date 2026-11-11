# pyterm – notes for Claude Code

Pixel-art "overkill" terminal emulator in Python + pygame-ce (Windows via pywinpty/ConPTY, Linux via pty).
Oldschool demoscene look: themes, letter/delete effects, background scenes, splashes, plugins.
The user is on Windows (PowerShell), window ~1600x1000.

## Run / test
- Unit tests: `python -m unittest discover -s tests -v` (pty/process tests are skipped on Windows); smoke test: `python tools/ci_smoke.py`
- `python -m pyterm` (or `run.bat`), `--demo` = built-in fake shell (no real shell, good for tests)
- Useful flags: `-t THEME`, `--size 1280x720`, `--random`, `--mqtt URL --mqtt-debug`, `--alt-effects`, `--splash`
- Headless check: set `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`, build `App(*build_config([...,'--demo','--gpu','false']))`,
  call `app.frame(1/30)` in a loop, save `app.presenter.frame_surface()` with `pygame.image.save`.
  Set `App._demo_used = True` and `cfg['intro'] = False` to skip the splash.
- Demo shell commands: `help`, `themes`, `effects`, `bgs`, `cursors`, `splash NAME`, `alarm NAME msg`, `sixel`, `info`, `hack` …

## Layout (pyterm/)
- `app.py` – App: window, event loop (eco mode = no render when idle; `anim_until` forces frames), layout
  (fixed grid themes: `screen: {cols, rows, border}`), overlays, hotkeys, demo commands, alarms (`trigger_alarm`)
- `pane.py` – one terminal: backend IO, vt events → effects, cursor, clipboard (OSC 52), full-screen app effect mode
- `vt.py` – VT/xterm parser (`Screen`), sixel layer on alt screen, XTWINOPS, OSC 7/52/133/1337
- `renderer.py` – glyph cache, row rendering; `bg_alpha` (default cells), `cell_bg_alpha` (colored cells)
- `effects.py` – letter appear (`APPEAR`) / vanish (`VANISH`) effects; `fx.near` limits effects to typed cells
- `backgrounds.py` (+ `scenes.py`, `scenes2.py`, `seasons*.py`, `water.py`, `roman.py`, `weather.py`, `cyber.py`) – `Background` layers:
  `resize`, `update(dt, energy)`, `draw(surf, first)`, `self.p(key, default)` reads `bg_params`
- `signals.py` – blackboard between terminal and scenes (typing, enter, bell, cmd, letters, typing_speed, shake)
- `fonts.py` – builtin pixel fonts (`builtin:*`), colored fonts, TTF; `cursors.py`; `splash.py`; `scroller.py`
- `mqtt.py` – optional MQTT/Home Assistant bridge (discovery, sensors, selects, alarms); never types into the terminal
- `alarms.py` – Alarm base class + redalert/warning/doorbell/timer/calm; `plugins.py` – PluginAPI (`register_*`)
- `pyterm/data/` – bundled assets: `themes/*.yaml`, `fonts/`, `sounds/`, `shell/`, `config.yaml` (global config, CLI overrides), `plugins/*.py` (hot-reloaded). Screenshots/recordings go to the current directory.
- docs/: THEMES, PLUGINS, FONTS, CURSORS, SHELL, HOMEASSISTANT

## Conventions
- Keep features optional & configurable (config.yaml key + CLI flag + Studio where it fits); document in docs/ and README.
- Privacy: MQTT `publish_text` stays opt-in; remote control is limited to looks (+ alarms).
- Performance matters: numpy for particles, cache static surfaces, avoid per-frame full-screen allocations.
- Plugins are keyed by file path in `app.plugins.plugins`; look them up by `.name`.
