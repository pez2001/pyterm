# Themes

A theme is a YAML file in `themes/` (or `%APPDATA%\pyterm\themes`, `~/.config/pyterm/themes`).
Every key is optional; missing keys use the defaults below. Saved files are **hot-reloaded**,
and the Studio (Ctrl+Shift+F12) edits all of this live and writes it back to YAML.

```yaml
name: mytheme
description: one line shown when switching themes
palette: ['#000000', '#cd0000', ...]   # 16 ANSI colors (256-color cube is generated)
fg: '#d0d0d0'                          # default text color
bg: '#000000'                          # default background
bg_alpha: 255                          # 0 = text cells see-through to the background effect
cell_bg_alpha: 170                     # cells with their own bg color (mc, htop, powerline); default 170 when bg_alpha < 255, else 255
splash: demo                           # boot sequence: demo | c64 | c64_clean | uplink | none (+plugins, see pyterm/splash.py)
command_blocks: true                   # false = no command gutter / separator lines in this theme
screen: null                           # fixed text grid like the original machine, e.g. C64:
                                       #   {cols: 40, rows: 25, border: [32, 36]}  (320x200 inside 384x272, scaled to fit)
cursor: '#ffcc00'
cursor_style: block                    # block | underline | beam | outline | miner | hero | settler | train | chisel (+plugins)
alt_miner: false                       # keep the character cursor inside vim/htop too
color_overlay: [[0, 0.12, '#ff5050']]  # arcade cellophane bands: [y0, y1, color] (fractions of height)
cursor_effects: [glow]                 # stack: glow trail ripple sparkle orbit smoke reticle (+plugins)  - docs/CURSORS.md
cursor_params: {trail: {count: 10}, ripple: {color: '#ff40c0', typing: false}}
                                       # (old  cursor_glow / cursor_trail  booleans are still understood)
bold_bright: true                      # bold ANSI 0-7 -> bright 8-15
text_shadow: false                     # readable text over busy backgrounds
border: 6                              # margin in virtual pixels
border_solid: false                    # paint the margin with border_color
border_color: '#000000'
border_fx: none                        # none | c64 (loading stripes while busy) | rainbow
font: builtin                          # builtin | builtin:fat8 | builtin:topaz | builtin:thin8 | builtin:c64narrow | builtin:amiga | builtin:roman | sys:Consolas | fonts/x.ttf|.bdf|.psf|.png|.yaml
font_size: 18                          # for TTF fonts
antialias: true                        # TTF smoothing (false = crisp pixels)
scale: null                            # pixel scale; null = 2 for pixel fonts, 1 for TTF
background: [plasma]                   # stack: plasma fire tunnel starfield copper grid matrix metaballs rasterwave
                                       #        shadebobs rotozoom twister boing vectorballs parallax platformer invaders weather
                                       #        dollhouse railway settlers discocity neonsigns watermirror
                                       #        aquarium spacestation garden pinball c64load beach
                                       #        fireworks christmas halloween easter autumn sakura winter seasonal stone zeroday (+plugins)
bg_dim: 0.4                            # background brightness
bg_params: {tunnel: {color: [255, 80, 220]}, starfield: {count: 600},
            dollhouse: {hour: null, shirt: '#e04848', hair: '#6e411e', pets: true, busy: 1.0},   # hour: fix the time of day
            fire: {chunk: 6, palette: classic, height: 1.0, style: classic},   # palette: classic|red|blue|green|purple or
                                       # ['#000000', ..., '#ffffff'] cold -> hot; style: classic (chunky oldschool) | doom (fine)
            weather: {location: auto, refresh_min: 10, simulate: null},  # location: auto | "Berlin" | [lat, lon]
            watermirror: {level: 0.62, tint: '#5a8cd2', waves: 1.0, speed: 1.0, text: true, sky: auto},
            c64load: {stripes: calm}, seasonal: {force: null},    # stripes: calm|authentic|off, force: halloween ...
            zeroday: {accent: '#00ffd0', accent2: '#ff2e88', alert: '#ff2846', ok: '#3cff78', home: [64.1, -21.9],
                      rain: 1.0, spin: 1.0, hud: true, globe: true, globe_x: 0.68, globe_y: 0.47, globe_size: 0.36,
                      callsign: 'ZERODAY//OS'}}                   # home: your node [lat, lon]; rain 0 = off
letter_effect: flame                   # none flame laser sand dissolve construction teleport fluid decrypt drop glitch pop
                                       # bump shoot puff neon chisel breach random (+plugins)
delete_effect: shatter                 # none shatter dust burn melt rainbow bricks invader spark firework leaves snow petals crumble derez random (+plugins)
alt_effects: typed                     # full-screen apps (vim, mc, htop): off | typed (only what you type) | all
drama: true                            # shake + red flash on error output
writer: {mode: smart, baud: 9600}      # smart | instant | baud | human
crt: {scanlines: 0, vignette: 0, bloom: 0, phosphor: 0, flicker: 0, noise: 0, glitch: 0, aberration: 0, curvature: 0,
      lcd: 0, interlace: 0}
sound: {pack: chime, volume: 0.4}      # chime | typewriter | 8bit | glass | cyber | 'off'   (quote 'off' - YAML!)
miner: false                           # EMERALD MINE
banner: "READY.\n"                     # text printed when a pane opens
palette_lock:                          # quantize the whole picture to a console palette
  mode: nearest                        # nearest (any palette) | luma (shades, e.g. game boy)
  dither: 0.4                          # ordered (bayer) dithering 0..1
  colors: ['#000000', '#ffffff', ...]
# crt also has  lcd: 0..1  (dot-matrix pixel grid, needs scale >= 2)
plugins:                               # per-plugin settings, read via api.settings
  sine_scroller: {enabled: true, text: 'hello scene'}
```

Tip: YAML reads bare `off`, `no`, `yes` as booleans — quote them.
