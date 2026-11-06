# Fonts

| spec | what |
|---|---|
| `builtin` | the hand-drawn 5x9 pixel font (6x10 cell), editable in the Studio |
| `sys:Consolas` | any installed system font by name |
| `fonts/name.ttf` / `.otf` | TrueType/OpenType, `font_size`, `antialias` (false = crisp) |
| `fonts/name.bdf` | X11 BDF bitmap fonts (e.g. Terminus, Spleen, Cozette) |
| `fonts/name.psf[.gz]` | Linux console fonts, e.g. from `/usr/share/consolefonts` |
| `fonts/name.png` | glyph sheet, 16x16 grid in CP437 order, white ink on black/transparent |
| `fonts/name.yaml` | metadata for a sheet: `{name, type: sheet, file: name.png, cell: [w, h]}` |

Any file dropped into `fonts/` shows up in Ctrl+Shift+F cycling and the Studio font list.

## Make your own pixel font

1. **Studio** → FONT tab: pick a glyph (click it, or hover and press the key), paint with left/right mouse,
   shift/mirror/invert/bold tools. Every stroke is live in the terminal. *Save font* writes
   `fonts/<name>.png` + `fonts/<name>.yaml` and sets it as the theme font.
2. Or export any font as a sheet and edit it in Aseprite/GIMP/whatever:
   `python pyvterm.py -f sys:Consolas -s 16 --no-aa --export-font myfont.png`
   then edit `fonts/myfont.png` — the font hot-reloads while pyvterm runs with `-f fonts/myfont.yaml`.
3. "Create (resample current)" in the Studio makes a new cell size from the current font as a starting point.

Box drawing, blocks, shades, braille and powerline glyphs are generated procedurally at any cell size
(so every font gets perfect TUI borders). If you paint one of those glyphs in the Studio, your version wins.
Missing glyphs (CJK, emoji…) fall back to a system font scaled into the cell.

## Animated fonts

`fonts/name.yaml` with `type: animated`:

```yaml
name: sparkle
type: animated
fps: 6
cell: [6, 10]
frames: [sparkle_0.png, sparkle_1.png, sparkle_2.png, sparkle_3.png]   # one CP437 sheet per frame
```

Generated ones: `builtin:wave`, `builtin:shimmer`, `builtin:jelly`, `builtin:bounce`.

**Big Amiga demo fonts** (18x22 cells, use `scale: 2`): `builtin:amiga` (copper rainbow), `builtin:amigachrome`,
`builtin:amigafire`. Chunky Topaz-style letters with a dark outline, a bevel highlight and a horizontal color
sweep running through the inside — the sweep repeats exactly every cell, so it flows seamlessly from letter to
letter. The ANSI color still tints the sweep a little (so red error text stays reddish). Palettes live in
`fonts.SWEEPS` — add your own there. Theme `amigademo` shows them off; `animfont` in the demo shell cycles all animated fonts.

**Scroller fonts** (huge, 37x45 cells): `builtin:scroller` (classic chrome: blue sky, white horizon, copper
ground), `builtin:scrollergold`, `builtin:scrollerice` — chunky letters with 45° beveled corners, inner bevel,
2 px outline, drop shadow and a glint sweeping across. Made for sine scrollers: the boot intro and the
`sine_scroller` plugin (Ctrl+Shift+Z) use them, with every 2-pixel column riding the wave
(`pyvterm/scroller.py`, `SineScroller`). They also work as a terminal font (`scale: 1`).

**Cute** (`builtin:cute`, 6x11): the small built-in font, calm and friendly — every few seconds a letter does a
tiny one-pixel hop (each letter at its own moment, never all at once, 6 fps), and the dots of `. ! ?` turn into
little hearts for a moment.
In the Studio FONT tab: step through frames, *Hold* the animation on the frame you edit, duplicate/delete
frames, change fps, *Make animated* turns any pixel font into a 4-frame animated one; *Save font* writes the
frame PNGs + YAML. Animated fonts redraw only at their own frame rate.

## Emoji

Smileys and a few symbols (😀😎😂😍😉🤩😴😡🥳👻💀❤⭐✨🔥👍🎉🚀 …) are drawn procedurally in color, so
they work with every font; the animated ones update at 8 fps and only their rows are redrawn.
Other emoji fall back to your system font.

**Roman** (`builtin:roman`, 12x20): classic serif capitals taken from the system's serif font (Times New Roman,
Georgia, Liberation/DejaVu/Free Serif ...) and carved into the stone: every groove gets a shadowed upper-left
wall and a lit lower-right wall. A colored font - the text color tints it like the paint Romans filled their
inscriptions with. Without any serif font installed it falls back to a carved Topaz.
