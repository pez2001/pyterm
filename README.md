# pyterm — the pixel-art overkill terminal

[![CI](https://github.com/pez2001/pyterm/actions/workflows/ci.yml/badge.svg)](https://github.com/pez2001/pyterm/actions/workflows/ci.yml)

<p align="center">
  <img src="docs/media/showcase.gif" alt="pyterm showcase" width="720">
</p>

<p align="center"><a href="docs/media/showcase.mp4"><b>▶ Watch the full showcase video (MP4)</b></a><br>
The show is run by the <b>zeroday</b> theme: it boots the deck (uplink splash, <i>ACCESS GRANTED</i>), roots a node
with <code>hack</code>, lets all other themes take their turn - and gets the last word when a failing command trips the ICE.</p>

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
  (`glow trail ripple sparkle orbit smoke reticle`, or your own) — `cursor_effects: [glow, trail]`, Ctrl+Shift+U cycles
  styles, Ctrl+Shift+Alt+U effect sets, `--cursor hero --cursor-fx ripple,trail`, demo shell: `cursor ghost comet`
* **cute cursors**: `cursor_style: miner` (walks, mines, blinks, looks around, hops on Enter, `!` on bell,
  `?` on failed commands, `♥` on success, falls asleep with z z z), `hero` (the jump'n'run kid), `train`
  (a tiny steam loco with turning wheels that puffs smoke while you type) or `settler` (with hammer)
* **living scenes** that run on your local clock and react to the terminal (typing, Enter, command results,
  output energy):
  * **computerpeople** — a cute little resident (big head, rosy cheeks, pajamas at night) lives in a cutaway
    3-floor house on your real clock with a dog and a cat: sleeps, takes a bath and sings, cooks, eats, watches
    TV, plays the piano, dances to the record player, does jumping jacks, vacuums, waters the plant and the
    garden (they grow), reads, feeds the pets, plays fetch, watches the stars, waves at you. It **runs to its
    computer whenever you type** (the monitor shows your last letters, the cat may jump on the desk, fast typing
    makes it sweat), nods on Enter, throws a confetti party after a long command, gets a fright when one fails
    (the cat puffs up, the dog barks) and fetches the mail when the bell rings. The cat's head follows your
    cursor. `bg_params: {dollhouse: {hour: null, shirt: '#e04848', hair: '#6e411e', pets: true, busy: 1.0}}`
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
* **zeroday** — the hacker's deck, the biggest theme so far (`-t zeroday`, try `hack` and `error` in `--demo`):
  * a **holographic dot-matrix globe** (real coastlines, 32 cities) turns in falling hex rain; every key you
    type flies off as a **packet** to your home node and is routed on along a great-circle arc to the city you
    are attacking; program output drives the rain, the ambient traffic and the throughput scope
  * a command that **succeeds roots the node** — *ACCESS GRANTED*, a green diamond stays on the map; a command
    that **fails trips the ICE**: red counter-traces race back to your home node, the picture tears, the
    **TRACE meter** climbs — at 100 % the connection is *burned* and all rooted nodes are lost
  * Enter sweeps a scan ring over the globe, the bell pings like a sonar, ←/→ spin the globe
  * HUD: UTC clock, node id, hex tap of the keys you type, throughput scope, typing speed, packets, rooted
    nodes, trace meter, uptime — all colors, the home node, rain, HUD and globe are `bg_params: {zeroday: {...}}`
  * new building blocks, usable in any theme: letter effect `breach` (bits → hex under a targeting bracket →
    RGB-split lock-in), delete effect `derez` (scan lines torn apart in cyan/magenta), cursor effect `reticle`
    (targeting brackets that kick on every key, scan line on Enter), boot splash `uplink` (boot log, key
    cracked digit by digit, ACCESS GRANTED), sound pack `cyber`
* **interlace** emulation (`crt: {interlace: 0.8}`): alternating fields + motion combing, theme `interlace`
* backgrounds: plasma, fire (the chunky oldschool one: `bg_params: {fire: {chunk: 6, palette: classic|red|blue|green|purple, height: 1.0}}`, `style: doom` for the fine speckled fire), tunnel, starfield, copper bars (`bg_params: {copper: {speed: 1.0}}`), synthwave grid, matrix rain, metaballs, rasterwave,
  shadebobs, rotozoomer, twister, Amiga boing ball, vectorballs, parallax, platformer, invaders, weather, dollhouse, railway, settlers, discocity, neonsigns, watermirror, aquarium, spacestation, garden, pinball, c64load, beach, fireworks, christmas, halloween, easter,
  autumn, sakura, winter, seasonal, stone, zeroday (all stackable)
* CRT stack: scanlines, vignette, bloom, phosphor afterglow, chromatic aberration, barrel curvature, flicker, noise, glitch
* procedural sound packs (chime, typewriter, 8bit, glass, cyber): every key chimes, deletes blip, BEL rings
* letter-writer output pacing: smart roll-out, authentic **baud rates** (300…115200), human typewriter
* boot intro with a particle logo, copper bars and a sine scroller
* the world reacts to your workload: backgrounds speed up and glow with output throughput, and errors make the screen shake

…and it stays useful for daily work:

* real PTY (Linux `pty`, Windows **ConPTY** via `pywinpty`), xterm-256color + truecolor, alt screen, mouse reporting,
  scroll regions, bracketed paste, OSC 52 clipboard (`osc52: write | read-write | off`; `read-write` lets pytermwm's right click paste your clipboard), DEC line drawing — `vim`, `htop`, `less`, `tmux`, PowerShell all work.
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
  scroll with the text, survive scrollback (`python -m pyterm.imgcat pic.png [--sixel|--iterm]`)
* **shell integration / command blocks** (OSC 133 + OSC 7): green/red/blue gutter per command, hover for exit code +
  duration, jump between prompts, copy the last command's output, notification when long commands finish.
  Auto-injected for PowerShell, bash and cmd; script for zsh (docs/SHELL.md)
* **video export**: MP4 / GIF straight from the effects (Ctrl+Shift+G / J) or offline:
  `python -m pyterm --demo -t c64 --record c64.gif --frames 300`
* **smooth scrolling** (pixel-smooth output scroll + scrollback), **GPU presenter** (SDL2 renderer, vsync, GPU
  upscaling), **eco mode** (zero CPU when nothing moves), reduced fps when idle/unfocused, cached background rate
* **boot splashes** are pluggable classes (`splash: demo | c64 | c64_clean | uplink | none`, `--splash NAME|random`, demo shell `splash c64`):
  the **c64** theme powers up like the breadbin — READY., `LOAD"$",8,1`, `LIST` with the disk directory,
  `LOAD"PYTERM",8,1` with loading stripes and a picture building up, `RUN` — and then uses only the real
  **320×200 text area inside the big C64 border**, in **80-column mode** with a 4×8 font like the C64's 80-column
  programs (`screen: {cols: 80, rows: 25, border: [32, 36]}`, `font: builtin:c64narrow`), scaled to fit;
  **c64_40** is the faithful original 40×25 screen with the 8×8 font, for real C64 text content
  — and **c64_raw** is the plain version: same screen and exact colors, but no CRT, glow, effects, stripes or sound,
  with a quiet text-only boot (`splash: c64_clean`)
* retro console themes: **c64**, **amiga**, **nes_famicom**, **gameboy** with matching generated pixel fonts
  (`builtin:fat8`, `builtin:topaz`, `builtin:thin8`, `builtin:vga` for the tall DOS text mode), **palette lock** (everything quantized to the console palette,
  optional ordered dithering) and a dot-matrix **LCD** filter

## Screenshots

| | |
|---|---|
| ![neon](docs/media/neon.png)<br>**neon** | ![emerald mine](docs/media/emerald_mine.png)<br>**emerald_mine** |
| ![c64](docs/media/c64.png)<br>**c64** | ![amiga](docs/media/amiga.png)<br>**amiga** |
| ![vaporwave](docs/media/vaporwave.png)<br>**vaporwave** | ![inferno](docs/media/inferno.png)<br>**inferno** |
| ![gameboy](docs/media/gameboy.png)<br>**gameboy** | ![weather](docs/media/weather.png)<br>**weather** |
| ![zeroday](docs/media/zeroday.png)<br>**zeroday** | |

Regenerate them with `python tools/screenshots.py docs/media` and the video with `python tools/showcase.py docs/media/showcase.mp4`
(zeroday hosts it - see the top of `tools/showcase.py`; the raw render is 1280x720, shrink it with
`ffmpeg -i showcase.mp4 -vf scale=1024:576 -c:v libx264 -crf 27 -pix_fmt yuv420p -movflags +faststart out.mp4`; the README GIF is the
first nine seconds from 3.6 s on: `ffmpeg -ss 3.6 -t 9 -i showcase.mp4 -vf "fps=10,scale=640:-1,split[a][b];[a]palettegen=max_colors=64[p];[b][p]paletteuse" showcase.gif`).

## Install & run

```
pip install pyterm-pixel                  # from PyPI - includes all themes, fonts, effects, plugins and sounds
pip install "pyterm-pixel[all]"           # + MP4/GIF export (imageio-ffmpeg) and MQTT / Home Assistant (paho-mqtt)
pyterm --demo                          # the command is `pyterm`; --demo = built-in demo shell, plain `pyterm` starts your shell
```

User themes, fonts and plugins go to `%APPDATA%\pyterm` (Windows) or `~/.config/pyterm` (Linux/macOS).

**Upgrading from 1.0.0** (when the project was called *pyvterm*): on first start pyterm copies your old
`%APPDATA%\pyvterm` / `~/.config/pyvterm` folder (config, themes, fonts, plugins) to the new location; the old folder
is left untouched. If you use the Home Assistant / MQTT bridge, see the upgrade note in `docs/HOMEASSISTANT.md`.

From a source checkout instead:

```bash
pip install -r requirements.txt        # pygame-ce, numpy, pyyaml (+ pywinpty on Windows)
python -m pyterm                      # your shell, default theme "neon"
python -m pyterm --demo               # no shell: built-in show + demo commands (type "help")
python -m pyterm -t emerald_mine      # dig, miner, dig!
python -m pyterm --studio             # editor docked next to the live terminal
python -m pyterm --cat art.ans -t dos # ANSI art viewer (cp437)
python -m pyterm --list               # themes, effects, backgrounds, fonts
python -m pyterm --benchmark          # headless performance numbers
```

Windows: `run.bat`, Linux: `./run.sh`. Use Python 3.8+. **pygame-ce** is recommended; classic pygame 2 works too.

Useful flags: `-t THEME`, `-f FONT` (`builtin`, `sys:Consolas`, `fonts/x.ttf|.bdf|.psf|.png|.yaml`), `-s SIZE`, `-x SCALE`,
`--effect NAME`, `--delete-effect NAME`, `--cursor STYLE`, `--cursor-fx a,b`, `--bg plasma,starfield`, `--writer baud --baud 1200`, `--miner`,
`-e "powershell.exe"`, `--encoding cp437`, `--no-sound`, `--fullscreen`, `--size 1600x900`,
`--mqtt mqtt://user:pass@host:1883`.

**Random selection** — every option that takes a name from a list also accepts `random`, a shortlist
`random:a,b,c`, and for stackable lists `randomN`:

```bash
python -m pyterm --random                                   # random theme + random font
python -m pyterm -t random                                  # any theme
python -m pyterm -t random:c64,amiga,gameboy,nes_famicom    # one of these
python -m pyterm -f random --cursor random --cursor-fx random2
python -m pyterm --bg random3                               # one scene + two see-through layers on top
python -m pyterm --effect pick --delete-effect pick         # one random effect for the whole session
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
| Ctrl+Shift+C / V, Ctrl+Insert / Shift+Insert, middle click | copy / paste (selection copies automatically) |
| right click | copy the selection, or paste if nothing is selected (like Windows Terminal). Programs with mouse support (mc, pytermwm) get the click – Shift+right click is always pyterm's; `right_click: always` makes it pyterm's everywhere, `off` disables it |
| Ctrl+Shift+L | search scrollback |
| Ctrl+Shift+X | screenshot |
| Ctrl+Shift+G / J | record MP4 / GIF (press again to stop) |
| Ctrl+Shift+R | record asciinema `.cast` |
| Ctrl+Shift+K / Z / I / N | fireworks / sine scroller / HUD meter / walkers (plugins) |
| Shift+PgUp/PgDn, wheel | scrollback |
| Ctrl+Click | open URL (`ctrl_click_urls: false` to turn off) |
| F11, Alt+Enter | fullscreen (`alt_enter_fullscreen: false` / `--no-alt-enter` leaves Alt+Enter to the program, e.g. pytermwm) |

**Hotkey & mouse options** - hand keys to full-screen programs (pytermwm, vim, tmux ...) instead of pyterm (`config.yaml`, every one has a flag):

| option | default | effect |
|---|---|---|
| `alt_enter_fullscreen` / `--no-alt-enter` | `false` in the bundled config | Alt+Enter toggles fullscreen (F11 always does) |
| `disabled_hotkeys: [...]` / `--disable-hotkeys a,b` | `[]` | `alt_arrows` (pane focus), `ctrl_tab`, `ctrl_pgup_pgdn` (tab switching), `shift_pgup` (scrollback keys), or single hotkeys as `ctrl+shift+<key>`, e.g. `[ctrl+shift+t, alt_arrows]` |
| `ctrl_click_urls` / `--no-ctrl-click` | `true` | Ctrl+Click opens URLs |
| `middle_click_paste` / `--no-middle-paste` | `true` | middle mouse button pastes |
| `copy_on_select` / `--no-copy-on-select` | `true` | selecting copies; off: Ctrl+Shift+C or right click |
| `insert_keys`, `right_click` | `true`, `copy-paste` | Shift/Ctrl+Insert clipboard keys, right click behaviour |

## Performance & power

* `gpu: auto` (config.yaml) uses the SDL2 GPU renderer: one texture upload per frame, scaling/blending on the GPU,
  vsync. Falls back to software automatically. `--gpu false` forces software.
* **eco mode**: when nothing animates (no background effect, no running effects, no output) pyterm stops
  rendering completely and sleeps until input/output arrives — ~0% CPU in the `zen`/`dos` themes.
* `idle_fps` (30) after 3 s without activity, `unfocused_fps` (15) when the window is in the background,
  `bg_fps` (30) background effects are rendered at their own rate and cached, `fps: 0` = uncapped (vsync).
* `smooth_scroll_lines: 3` (0 disables).

## Layout

```
python -m pyterm      launcher (or the `pyterm` command after pip install)
pyterm/               the engine
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
pyterm/data/          bundled assets (shipped in the wheel)
  config.yaml         global settings (also read from %APPDATA%\pyterm / ~/.config/pyterm)
  themes/*.yaml       themes          docs/THEMES.md
  fonts/              fonts           docs/FONTS.md
  plugins/*.py        plugins         docs/PLUGINS.md
  sounds/<pack>/      optional wav/ogg overrides
  shell/              shell integrations (ps1 / bash / zsh)
docs/                 documentation
```

## Performance notes

* Text is rendered per dirty row into a cached layer; scrolling uses `Surface.scroll` (no re-render).
* Effects and particles live in *virtual rows*, so scrolling them is O(1).
* All particles are one numpy system drawn with a single surfarray write.
* Background effects run at ¼–⅓ resolution and are scaled up (free chunky pixels).
* Under heavy output: at most `spawn_budget` new effects per frame, effect durations shrink with load, letters that
  scroll away inside the same frame never get effects, and full-screen apps are effect-free.
* `python -m pyterm --benchmark` prints parser MB/s and frame times per theme.

## License

pyterm is free software: you can redistribute it and/or modify it under the terms of the
**GNU Lesser General Public License, version 3** as published by the Free Software Foundation
(`LGPL-3.0-only`).
See [COPYING.LESSER](COPYING.LESSER) and [COPYING](COPYING) (the GPL v3 it builds on).
