# Cursors

The cursor is two kinds of pluggable classes (`pyterm/cursors.py`):

* **one style**: draws the cursor itself
* **any number of effects**: decorate it, emit particles, react to typing

```yaml
cursor: '#ffcc00'                      # theme cursor color (st.rgb)
cursor_style: hero
cursor_effects: [glow, ripple, trail]  # [] = plain cursor
cursor_params:                         # per style / effect settings
  trail: {count: 10, color: '#40ffff'}
  ripple: {typing: false}
alt_miner: false                       # character styles stay visible in vim/htop too
```

Old themes with `cursor_glow: false` / `cursor_trail: true` are converted automatically.

Override per run: `--cursor beam --cursor-fx glow,orbit`. Live: **Ctrl+Shift+U** cycles styles,
**Ctrl+Shift+Alt+U** cycles effect sets, demo shell `cursor <style> [effects…|none]`, `cursors` lists them,
and the Studio (TEXT & CURSOR) has a style picker and one toggle per effect.

## Built-in styles

| style | |
|---|---|
| `block` | pulsing block, letter in inverse video |
| `underline`, `beam`, `outline` | pulsing bar / thin beam / hollow box |
| `miner` | the EMERALD MINE digger: walks, swings his pickaxe at typed letters, hops on Enter, `!` on bell, `?` failed command, `♥` long successful one, falls asleep (z z z) |
| `hero` | the jump'n'run kid |
| `settler` | green tunic, swings a hammer |
| `train` | tiny steam loco, turning wheels, smoke puffs while you type |

EMERALD MINE mode always uses `miner`. Character styles (`character = True`) stay visible in unfocused panes with a thin outline.

## Built-in effects

| effect | params | |
|---|---|---|
| `glow` | `strength`, `color` | soft pulsing halo under the cursor (layer `under`) |
| `trail` | `count`, `color` | sparkles where the cursor leaves |
| `ripple` | `typing`, `color` | ring on Enter, small rings while typing |
| `sparkle` | `rate`, `color` | twinkling stars hover around it |
| `orbit` | `count`, `color` | satellites circle the cursor, faster while you type |
| `smoke` | | gray puffs rise while you type |
| `reticle` | `size`, `color` | targeting brackets lock onto the cursor, kick outwards on every key, scan line along the row on Enter |

Plugin `cursor_demo.py` adds the style `ghost` and the effect `comet`.

## Writing your own

```python
from pyterm.cursors import CursorStyle, CursorEffect

class Box(CursorStyle):
    character = False                  # True: sprite-like (outlined when unfocused, hidden in vim unless alt_miner)
    def update(self, dt, st): ...
    def draw(self, surf, ox, oy, st):
        surf.fill(st.rgb, (ox + st.x, oy + st.y, st.cw, st.ch))
    def busy(self): return False       # True while it needs frames (keeps eco mode awake)

class Halo(CursorEffect):
    layer = 'under'                    # drawn before the style; 'over' = after
    defaults = {'size': 2}             # overridden by cursor_params.halo
    def draw(self, surf, ox, oy, st):
        r = st.cw * self.p('size')
        pygame.draw.circle(surf, self.color('color', st), (ox + st.x + st.cw // 2, oy + st.y + st.ch // 2), r, 1)

def register(api):
    api.register_cursor('box', Box)
    api.register_cursor_effect('halo', Halo)
```

Hooks: `start()`, `update(dt, st)`, `draw(surf, ox, oy, st)`, `busy()`, `wake()` (key pressed),
`command_done(exit_code, seconds)`. `self.pane` is the pane, `self.particles` the particle engine
(y in virtual rows: `y + st.voff * st.ch`), `self.p(key)` reads params.

`st` (CursorState): `cx cy` cell, `x y` pixel position relative to `ox, oy`, `cw ch` cell size, `voff`,
`moved`, `typed` (letters printed this frame), `newline`, `bell`, `focused`, `visible`, `alt` (full-screen
app), `eco`, `t`, `dt`, `rgb`, `screen` (vt.Screen), `mine`.
Effects are paused in full-screen apps unless `active_in_alt = True`, and in ZEN mode.
