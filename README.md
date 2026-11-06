# pyvterm — the pixel-art overkill terminal

A real, usable terminal emulator for **Windows and Linux**, written in Python + pygame,
dressed up like a 1992 demoscene production:

* letters **burn in**, get **engraved by lasers**, **pile up from sand**, **dissolve** out of noise,
  are **built by tiny cranes**, **beam in** star-trek style, **fill with liquid**, **decrypt**, **drop**, **glitch**, **pop**
* deleted letters **shatter**, turn to **dust**, **burn**, **melt** or explode into **rainbow** sparks
* **EMERALD MINE** mode: the terminal is solid earth, every printed letter is an **emerald** buried in it,
  and the cursor is a tiny animated **miner** who walks along, swings his pickaxe and harvests them — each gem
  flies into the counter. Heavy output makes him swing faster and reach wider; at the top end: **TNT**
* **cursor styles + cursor effects** as plug-in classes (docs/CURSORS.md): pick one style
  (`block underline beam outline miner hero settler train`, or your own) and stack any effects on it
  (`glow trail ripple sparkle orbit smoke`, or your own) — `cursor_effects: [glow, trail]`, Ctrl+Shift+U cycles
  styles, Ctrl+Shift+Alt+U effect sets, `--cursor hero --cursor-fx ripple,trail`, demo shell: `cursor ghost comet`
* **cute cursors**: `cursor_style: miner` (walks, mines, blinks, looks around, hops on Enter, `!` on bell,
  `?` on failed commands, `♥` on success, falls asleep with z z z), `hero` (the jump'n'run kid), `train`
  (a tiny steam loco with turning wheels that puffs smoke while you type) or `settler` (with hammer)
* **living scenes** that run on your local clock and react to the terminal (typing, Enter, command results,
  output energy):
  * **computerpeople** — a little resident in a cutaway 3-floor house sleeps, cooks, eats, watches TV, plays
    piano (notes float up), waters its growing plant, reads and walks the dog; the moment you type it walks
    over and types on *its* computer. Failed command → 😢/😱, long successful command → it dances 🥳,
    BEL raises the mailbox flag. Showcase theme: random letter + delete effects, cursor trail, emoji
  * **trains** — steam trains with spoked wheels & connecting rods chuff past: they brake at the station,
    passengers board, the signal goes red, the level crossing closes (blinking lights, waiting car), they
    rattle over the river bridge and vanish into the tunnel; windmill, cows that *MOO*, birds, day/night with
    lit windows. Output makes trains faster, every finished command blows the whistle
  * **settlers** — a working economy: carriers walk the roads between flags hauling logs, stone, fish, wheat →
    mill → flour → bakery → bread to the HQ; the woodcutter fells grown trees, the forester plants saplings
    that grow, fields ripen and get harvested, chimneys smoke. Output speeds the economy up; every successful
    command founds a new building site that gets built
  * **discocity** — 80s retro-wave night: striped sunset, neon skyline with flickering signs, a spinning
    disco ball spraying light spots, sweeping lasers, scrolling grid, palms, a car cruising into the night,
    and an equalizer that dances to your output. Letters flicker on like neon tubes (`letter_effect: neon`)
    **You drive the car:** ← / → steer (the road bends into the curve, the camera follows, the car leans and
    bumps off the kerb), **Return** fires a **BOOST** — exhaust flames, speed streaks, the grid turns ice-blue,
    the neon posts rush past and the equalizer jumps. The keys still go to your shell as usual.
* game themes: **invaders** (alien armada marches in the background, the cannon *shoots every letter into place*,
  arcade color-band overlay), **walkers** (lemmings-style critters stroll over your text, fall, build brick stairs,
  explode when a command fails), **jumpnrun** (scrolling platform world, letters are bumped out with coins,
  deleted letters shatter like bricks)
* **pixel-art emoji**: ~50 colored smileys & symbols drawn at any cell size, many **animated** (wink, tears,
  hearts, flames, twinkling stars, sleeping z's…) — `emoji` in the demo shell
* **animated fonts**: glyphs with frames — built-in `builtin:wave`, `builtin:shimmer`, `builtin:jelly`,
  `builtin:bounce`, and a file format (`fonts/sparkle.yaml` + one PNG sheet per frame) that the Studio can
  edit frame by frame — `animfont` in the demo shell cycles them
* **big Amiga demo fonts**: `builtin:amiga`, `builtin:amigachrome`, `builtin:amigafire` — outlined, beveled
  cracktro letters with a copper color sweep running horizontally through them (theme `amigademo`)
* **scroller fonts** `builtin:scroller` / `scrollergold` / `scrollerice`: huge beveled chrome demo letters; the
  boot intro and the sine scroller plugin (Ctrl+Shift+Z) roll them along a per-column sine wave
* **cute font** `builtin:cute`: small and calm — letters do a tiny hop now and then, dots become hearts
* **live weather background** (`theme weather`): real-time conditions for your location from Open-Meteo
  (no API key) — day/night sky, sun/moon/stars, clouds, rain, snow, fog, thunderstorms with lightning and
  delayed thunder; offline it cycles through all conditions
* **neonsigns**: a rainy back alley with buzzing neon tube signs (OPEN, BAR, 24H, cocktail, heart, star, moon,
  note, arrow…) glowing on a brick wall and mirrored in the rippling wet ground. Tubes flicker and stutter, one is
  always a bit broken, they brighten with output, flash on BEL, short-circuit in a spark shower when a command
  fails and run a chase light when a long one succeeds; letters flicker on like tubes (`neon`) and deleted ones
  short out (`delete_effect: spark`)
* **water mirror** (`background: [watermirror]`, theme `watermirror`): the lower part of the window is a lake that
  mirrors everything above the waterline — the background layers below it *and your terminal text* — flipped,
  tinted and bent by waves. Typing drops ripples under the cursor, Enter sends a swell, a failed command splashes.
  Stack it on any background (`[plasma, watermirror]`); alone it brings a moonlit sky with a glitter path.
  `bg_params: {watermirror: {level: 0.62, tint: '#5a8cd2', waves: 1.0, speed: 1.0, text: true}}`
* **six more living themes** (they all react to what you type, Enter, command results and output):
  * **aquarium** — curious fish swim to your cursor while you type and scatter on Enter, the letters you type
    sink down and settle on the sand, bubbles from a diver and a castle, caustics; a turtle visits after long
    commands, the water clouds over when one fails, and the fish doze off (Z) when you're away
  * **spacestation** — cockpit window: warp-speed stars driven by your output, planets with rings drift past,
    every letter you type fires a laser at an asteroid; a failed command sounds the red alert and shakes the
    hull; HUD with speed, hull, hits and clock
  * **garden** — every letter you type is a seed that falls into the soil and grows into a flower (daisies,
    tulips, sunflowers, bells); bees and a butterfly by day, fireflies at night (real clock), cute font
  * **pinball** — the ball bounces off your *actual text* and lights up the letters it hits, bumpers flash,
    Enter fires the flippers, typing scores
  * **c64load** — endless tape loading screen: wild raster stripes while data loads, calm pilot tone between
    blocks, pictures build up line by line in the C64's interleaved order, `?LOAD ERROR` on failure, 2400 baud
  * **beach** — sunset over the sea with a glittering path (real clock), waves, your letters drop onto the sand
    and little crabs carry them around; Enter sends a big wave that washes them away; gulls, palm, lighthouse
* **roman** — a marble tablet in flickering torch light with a carved frame (S P Q R); text is set in classic
  serif capitals **carved into the stone** (`builtin:roman`: shadowed upper wall, lit lower wall, tinted like the
  red paint in Roman inscriptions); every letter is **chiseled in** line by line while stone dust trickles down
  and chips fly (`letter_effect: chisel`), a chisel & mallet cursor strikes as you type (`cursor_style: chisel`),
  deleted letters crumble (`delete_effect: crumble`)
* **seasonal & holiday themes** (`seasonal` picks the right one by date):
  * **newyear** — rockets with glowing trails burst over a city skyline into thousands of tiny colorful pixels:
    peonies, chrysanthemums, golden willows, rings, crossettes that split again, glitter, palms, hearts and the
    new year in numbers; flashes light up the sky, smoke drifts, the river mirrors it all. Enter launches
    rockets, typing fires small ones, a long command gets a finale, countdown on Dec 31 (letters you delete
    burst like fireworks: `delete_effect: firework`)
  * **christmas** — snowy village: tree with chasing lights, glowing star and presents, houses with flickering
    windows and chimney smoke, a snowman who waves on Enter, falling snow, shooting stars, Santa's sleigh
  * **halloween** — haunted house on a hill under a huge moon, bats, a ghost, fog, jack-o'-lanterns flaring up
    while you type, a spider on its thread; failed commands bring lightning, thunder and a BOO
  * **easter** — a bunny hops and sniffs, chicks peck, every letter you type drops a painted egg into the grass
  * **autumn** — maple trees shed leaves that flutter down and pile up, wind from your output, a squirrel
  * **sakura** — Mt. Fuji, pagoda, cherry trees letting petals drift onto a koi pond
  * **winter** — northern lights rippling over snowy peaks and a frozen lake, cabin, gentle snow
  * new delete effects `firework`, `leaves`, `snow`, `petals`
* **interlace** emulation (`crt: {interlace: 0.8}`): alternating fields + motion combing, theme `interlace`
* backgrounds: plasma, fire, tunnel, starfield, copper bars (`bg_params: {copper: {speed: 1.0}}`), synthwave grid, matrix rain, metaballs, rasterwave,
  shadebobs, rotozoomer, twister, Amiga boing ball, vectorballs, parallax, platformer, invaders, weather, dollhouse, railway, settlers, discocity, neonsigns, watermirror, aquarium, spacestation, garden, pinball, c64load, beach, fireworks, christmas, halloween, easter,
  autumn, sakura, winter, seasonal, stone (all stackable)
* CRT stack: scanlines, vignette, bloom, phosphor afterglow, chromatic aberration, barrel curvature, flicker, noise, glitch
* procedural sound packs (chime, typewriter, 8bit, glass): every key chimes, deletes blip, BEL rings
* letter-writer output pacing: smart roll-out, authentic **baud rates** (300…115200), human typewriter
* boot intro with a particle logo, copper bars and a sine scroller
* the world reacts to your workload: backgrounds speed up and glow with output throughput, and errors make the screen shake

…and it stays useful for daily work:

* real PTY (Linux `pty`, Windows **ConPTY** via `pywinpty`), xterm-256color + truecolor, alt screen, mouse reporting,
  scroll regions, bracketed paste, OSC 52 clipboard (`osc52: write | read-write | off`), DEC line drawing — `vim`, `htop`, `less`, `tmux`, PowerShell all work.
  In full-screen apps letter effects animate only what you type (`alt_effects: typed`, or `all` / `off`, `--alt-effects`);
  colored cell backgrounds stay see-through over scenes (`cell_bg_alpha`, `--cell-bg-alpha`)
* **UTF-8, CP437, ASCII, Latin-1** (`--encoding`) — `--cat file.ans` plays ANSI art (SAUCE stripped)
* every box/block/braille/powerline glyph is generated procedurally, so it is pixel-perfect with any font
* full-screen apps automatically get calm, effect-free rendering; **ZEN key** (Ctrl+Shift+Space) turns everything off/on
* effect governor + spawn budget: effects thin out under load, so `cat` on a huge file stays fast
* scrollback (wheel, Shift+PgUp/PgDn) + search (Ctrl+Shift+L), selection → clipboard, Ctrl+Click opens URLs
* screenshots (Ctrl+Shift+X), asciinema `.cast` recording (Ctrl+Shift+O)
* **Studio** (Ctrl+Shift+F12 / `--studio`): live theme editor, pixel font editor and plugin workbench
* **MQTT / Home Assistant** (optional, off by default, `--mqtt` or `mqtt: {enabled: true}`): the terminal appears as
  a device via MQTT discovery – events for failed / long commands, error output and BEL (flash your lights red,
  show the error on a text display, print a receipt), sensors for exit code & duration, and Home Assistant can
  switch theme, effects, zen mode, sound, show a message or run text through the sine scroller.
  **Alarms** – red alert (klaxon + rotating beacon), warning (hazard tape), doorbell, timer (ringing alarm
  clock), calm reminder, or your own as a plugin – triggered from Home Assistant, dismissed with any key,
  and Home Assistant gets told whether someone acknowledged it. Try `alarm redalert hello` in the demo shell.
  Never: typing into the terminal. Details & automation examples: docs/HOMEASSISTANT.md
* **YAML** themes/config/fonts — all hot-reloaded when you save them in any editor
* **plugins** (single `.py` files, hot reload, can add letter effects, delete effects, backgrounds, overlays, hotkeys, commands)
* **tabs & split panes** (any nesting), focus with Alt+Arrows, inactive panes dimmed, new panes open in the current folder
* **inline images**: Sixel, kitty graphics protocol, iTerm2 `OSC 1337` — drawn crisp at window resolution,
  scroll with the text, survive scrollback (`python -m pyvterm.imgcat pic.png [--sixel|--iterm]`)
* **shell integration / command blocks** (OSC 133 + OSC 7): green/red/blue gutter per command, hover for exit code +
  duration, jump between prompts, copy the last command's output, notification when long commands finish.
  Auto-injected for PowerShell, bash and cmd; script for zsh (docs/SHELL.md)
* **video export**: MP4 / GIF straight from the effects (Ctrl+Shift+G / J) or offline:
  `python pyvterm.py --demo -t c64 --record c64.gif --frames 300`
* **smooth scrolling** (pixel-smooth output scroll + scrollback), **GPU presenter** (SDL2 renderer, vsync, GPU
  upscaling), **eco mode** (zero CPU when nothing moves), reduced fps when idle/unfocused, cached background rate
* **boot splashes** are pluggable classes (`splash: demo | c64 | c64_clean | none`, `--splash NAME|random`, demo shell `splash c64`):
  the **c64** theme powers up like the breadbin — READY., `LOAD"$",8,1`, `LIST` with the disk directory,
  `LOAD"PYVTERM",8,1` with loading stripes and a picture building up, `RUN` — and then uses only the real
  **320×200 text area inside the big C64 border**, in **80-column mode** with a 4×8 font like the C64's 80-column
  programs (`screen: {cols: 80, rows: 25, border: [32, 36]}`, `font: builtin:c64narrow`), scaled to fit;
  **c64_40** is the faithful original 40×25 screen with the 8×8 font, for real C64 text content
  — and **c64_raw** is the plain version: same screen and exact colors, but no CRT, glow, effects, stripes or sound,
  with a quiet text-only boot (`splash: c64_clean`)
* retro console themes: **c64**, **amiga**, **nes_famicom**, **gameboy** with matching generated pixel fonts
  (`builtin:fat8`, `builtin:topaz`, `builtin:thin8`), **palette lock** (everything quantized to the console palette,
  optional ordered dithering) and a dot-matrix **LCD** filter

## Install & run

```bash
pip install -r requirements.txt        # pygame-ce, numpy, pyyaml (+ pywinpty on Windows)
python pyvterm.py                      # your shell, default theme "neon"
python pyvterm.py --demo               # no shell: built-in show + demo commands (type "help")
python pyvterm.py -t emerald_mine      # dig, miner, dig!
python pyvterm.py --studio             # editor docked next to the live terminal
python pyvterm.py --cat art.ans -t dos # ANSI art viewer (cp437)
python pyvterm.py --list               # themes, effects, backgrounds, fonts
python pyvterm.py --benchmark          # headless performance numbers
```

Windows: `run.bat`, Linux: `./run.sh`. Use Python 3.8+. **pygame-ce** is recommended; classic pygame 2 works too.

Useful flags: `-t THEME`, `-f FONT` (`builtin`, `sys:Consolas`, `fonts/x.ttf|.bdf|.psf|.png|.yaml`), `-s SIZE`, `-x SCALE`,
`--effect NAME`, `--delete-effect NAME`, `--cursor STYLE`, `--cursor-fx a,b`, `--bg plasma,starfield`, `--writer baud --baud 1200`, `--miner`,
`-e "powershell.exe"`, `--encoding cp437`, `--no-sound`, `--fullscreen`, `--size 1600x900`,
`--mqtt mqtt://user:pass@host:1883`.

**Random selection** — every option that takes a name from a list also accepts `random`, a shortlist
`random:a,b,c`, and for stackable lists `randomN`:

```bash
python pyvterm.py --random                                   # random theme + random font
python pyvterm.py -t random                                  # any theme
python pyvterm.py -t random:c64,amiga,gameboy,nes_famicom    # one of these
python pyvterm.py -f random --cursor random --cursor-fx random2
python pyvterm.py --bg random3                               # one scene + two see-through layers on top
python pyvterm.py --effect pick --delete-effect pick         # one random effect for the whole session
                                                             # ('random' = a different effect for every letter)
```

The picks are printed and shown on screen at startup; `theme: random` etc. also works in `config.yaml`, and the
demo shell understands `theme random`, `font random`, `bg random2`, `effect pick`, `cursor random`.

## Hotkeys

| keys | action |
|---|---|
| Ctrl+Shift+H | help overlay (with live stats) |
| Ctrl+Shift+F12 | Studio |
| Ctrl+Shift+Space | ZEN mode ↔ OVERKILL mode |
| Ctrl+Shift+T / W | new tab / close pane |
| Ctrl+Shift+E / O | split side by side / stacked |
| Alt+Arrows | focus pane |
| Ctrl+Tab, Ctrl+PgUp/PgDn, Ctrl+Shift+1…9 | switch tabs (or click the tab bar) |
| Ctrl+Shift+Up / Down | jump to previous / next command |
| Ctrl+Shift+A | copy output of the last command |
| Ctrl+Shift+F1 / F2 / F3 | next theme (Alt = previous) / letter effect / delete effect |
| Ctrl+Shift+U / Alt+U | next cursor style / next cursor effect set |
| Ctrl+Shift+F4 | writer mode, baud rates |
| Ctrl+Shift+F5 / F6 / F7 / F8 | CRT / bloom / phosphor / sound pack |
| Ctrl+Shift+B / M / F | background / Emerald Mine / font |
| Ctrl+Shift+ + / − | pixel scale |
| Ctrl+Shift+C / V, middle click | copy / paste (selection copies automatically) |
| right click | copy the selection, or paste if nothing is selected (like Windows Terminal; `right_click: off`) |
| Ctrl+Shift+L | search scrollback |
| Ctrl+Shift+X | screenshot |
| Ctrl+Shift+G / J | record MP4 / GIF (press again to stop) |
| Ctrl+Shift+R | record asciinema `.cast` |
| Ctrl+Shift+K / Z / I / N | fireworks / sine scroller / HUD meter / walkers (plugins) |
| Shift+PgUp/PgDn, wheel | scrollback |
| Ctrl+Click | open URL |
| F11, Alt+Enter | fullscreen |

## Performance & power

* `gpu: auto` (config.yaml) uses the SDL2 GPU renderer: one texture upload per frame, scaling/blending on the GPU,
  vsync. Falls back to software automatically. `--gpu false` forces software.
* **eco mode**: when nothing animates (no background effect, no running effects, no output) pyvterm stops
  rendering completely and sleeps until input/output arrives — ~0% CPU in the `zen`/`dos` themes.
* `idle_fps` (30) after 3 s without activity, `unfocused_fps` (15) when the window is in the background,
  `bg_fps` (30) background effects are rendered at their own rate and cached, `fps: 0` = uncapped (vsync).
* `smooth_scroll_lines: 3` (0 disables).

## Layout

```
pyvterm.py            launcher
config.yaml           global settings (also read from %APPDATA%\pyvterm / ~/.config/pyvterm)
pyvterm/              the engine
  vt.py               VT100/xterm parser + screen model (events for the effect engine)
  backend.py          PTY (posix), ConPTY (pywinpty), pipe fallback, demo/file sources
  renderer.py         dirty-row glyph renderer with colored glyph cache
  fonts.py fontdata.py boxdraw.py   font loaders, built-in pixel font, procedural glyphs
  effects.py particles.py           letter effects + numpy particle engine
  cursors.py minercursor.py         cursor styles & cursor effects (classes, pluggable), pixel characters
  backgrounds.py post.py            demo effects + CRT stack
  mine.py             EMERALD MINE
  sound.py            procedural synth
  studio.py           Studio editor
  plugins.py          plugin manager / API
  pane.py app.py       panes, tabs/splits, main loop
  present.py          software / GPU presenter
  images.py imgcat.py sixel / kitty / iTerm2 images
  recorder.py         MP4 / GIF export
  shell.py            shell integration injection        shell/*.ps1|bash|zsh
themes/*.yaml         themes          docs/THEMES.md
fonts/                your fonts      docs/FONTS.md
plugins/*.py          plugins         docs/PLUGINS.md
sounds/<pack>/        optional wav/ogg overrides
```

## Performance notes

* Text is rendered per dirty row into a cached layer; scrolling uses `Surface.scroll` (no re-render).
* Effects and particles live in *virtual rows*, so scrolling them is O(1).
* All particles are one numpy system drawn with a single surfarray write.
* Background effects run at ¼–⅓ resolution and are scaled up (free chunky pixels).
* Under heavy output: at most `spawn_budget` new effects per frame, effect durations shrink with load, letters that
  scroll away inside the same frame never get effects, and full-screen apps are effect-free.
* `python pyvterm.py --benchmark` prints parser MB/s and frame times per theme.

## License

pyvterm is free software: you can redistribute it and/or modify it under the terms of the
**GNU Lesser General Public License, version 3** as published by the Free Software Foundation
(`LGPL-3.0-only`).
See [COPYING.LESSER](COPYING.LESSER) and [COPYING](COPYING) (the GPL v3 it builds on).
