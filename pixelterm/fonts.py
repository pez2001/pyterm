"""Font system.

Supported:  builtin pixel font | TTF/OTF (system or file, AA or pixel-crisp)
            | BDF bitmap fonts | PSF1/PSF2 (Linux console fonts, .gz ok)
            | PNG glyph sheets (16x16 grid in CP437 order)

Every font exposes the same interface: fixed cell size, ``glyph(ch, style)``
returning a white-on-transparent Surface, and ``pixels(ch, style)`` returning
numpy coordinates of lit pixels (food for the particle effects).
Missing glyphs fall through: procedural box/block glyphs -> system fallback
font -> tofu box.
"""
from __future__ import annotations

import gzip
import os

import numpy as np
import pygame

from . import emoji, fontdata
from .boxdraw import procedural_glyph

BOLD, ITALIC = 1, 4  # same bits as vt attrs

CP437_LOW = '\u0000☺☻♥♦♣♠•◘○◙♂♀♪♫☼►◄↕‼¶§▬↨↑↓→←∟↔▲▼'
CP437 = [CP437_LOW[i] if i < 32 else ('⌂' if i == 127 else bytes([i]).decode('cp437')) for i in range(256)]
UNI_TO_CP437 = {c: i for i, c in enumerate(CP437)}

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'fonts')

_MONO_SYS = ['dejavusansmono', 'consolas', 'cascadiamono', 'lucidaconsole', 'couriernew',
             'liberationmono', 'menlo', 'ubuntumono', 'notosansmono', 'freemono', 'monospace']


class _Fallback:
    """Renders glyphs the primary font lacks, sized to fit the cell."""

    def __init__(self):
        self.fonts = {}
        self.path = None
        for n in _MONO_SYS:
            p = pygame.font.match_font(n)
            if p:
                self.path = p
                break

    def render(self, c, w, h, aa=True):
        key = h
        f = self.fonts.get(key)
        if f is None:
            f = pygame.font.Font(self.path, max(6, int(h * 0.9)))
            self.fonts[key] = f
        try:
            s = f.render(c, aa, (255, 255, 255))
        except (pygame.error, ValueError):
            return None
        if s.get_width() == 0:
            return None
        s = s.convert_alpha() if pygame.display.get_surface() else s
        sw, sh = s.get_size()
        if sw > w or sh > h:
            k = min(w / sw, h / sh)
            nw, nh = max(1, int(sw * k)), max(1, int(sh * k))
            s = (pygame.transform.smoothscale(s, (nw, nh)) if aa else pygame.transform.scale(s, (nw, nh)))
            sw, sh = nw, nh
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        out.fill((0, 0, 0, 0))
        out.blit(s, ((w - sw) // 2, (h - sh) // 2))
        return out


_fallback = None


def fallback():
    global _fallback
    if _fallback is None:
        _fallback = _Fallback()
    return _fallback


# ============================================================================
class Font:
    name = 'font'
    pixel = True          # crisp pixel font? (affects synth bold & fallback AA)
    synth_styles = True   # synthesize bold/italic from regular

    def __init__(self):
        self.cw = self.ch = 8
        self.cache = {}
        self.pcache = {}

    # override: return white SRCALPHA surface (cw*width x ch) or None
    def raw(self, c, style, wide):
        return None

    def glyph(self, c, style=0, wide=False):
        key = (c, style & 5, wide)
        g = self.cache.get(key)
        if g is None:
            g = self._make(c, style & 5, wide)
            self.cache[key] = g
        return g

    animated = False

    def _make(self, c, style, wide):
        w = self.cw * (2 if wide else 1)
        if emoji.is_emoji(c):
            return emoji.silhouette(c, w, self.ch)
        s = None if c in getattr(self, 'edited', ()) else procedural_glyph(c, self.cw, self.ch)
        synth = False
        if s is None:
            s = self.raw(c, style if not self.synth_styles else 0, wide)
            synth = self.synth_styles
        if s is None:
            s = fallback().render(c, w, self.ch, aa=not self.pixel)
        if s is None:
            s = pygame.Surface((w, self.ch), pygame.SRCALPHA)
            s.fill((0, 0, 0, 0))
            pygame.draw.rect(s, (255, 255, 255, 160), (1, 1, w - 2, self.ch - 2), 1)
        if synth and style:
            s = self._synth(s, style)
        return s

    def _synth(self, s, style):
        if style & BOLD:
            b = s.copy()
            b.blit(s, (1, 0))
            s = b
        if style & ITALIC:
            w, h = s.get_size()
            it = pygame.Surface((w, h), pygame.SRCALPHA)
            it.fill((0, 0, 0, 0))
            bands = 3
            for i in range(bands):
                y0, y1 = h * i // bands, h * (i + 1) // bands
                it.blit(s, (bands - 1 - i - 1, y0), (0, y0, w, y1 - y0))
            s = it
        return s

    def pixels(self, c, style=0):
        """(xs, ys) float32 arrays of lit pixels of a glyph (cached)."""
        key = (c, style & 5)
        p = self.pcache.get(key)
        if p is None:
            g = self.glyph(c, style)
            a = pygame.surfarray.array_alpha(g)
            xs, ys = np.nonzero(a > 96)
            p = (xs.astype(np.float32), ys.astype(np.float32))
            self.pcache[key] = p
        return p

    def clear(self):
        self.cache.clear()
        self.pcache.clear()


def _bits_to_surface(rows, w, h, ox=0, oy=0):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            if v and 0 <= x + ox < w and 0 <= y + oy < h:
                s.set_at((x + ox, y + oy), (255, 255, 255, 255))
    return s


class BuiltinFont(Font):
    name = 'builtin'

    def __init__(self):
        super().__init__()
        self.cw, self.ch = fontdata.CELL_W, fontdata.CELL_H
        self.data = {c: fontdata.parse(d) for c, d in fontdata.GLYPHS.items() if d}

    def raw(self, c, style, wide):
        rows = self.data.get(c)
        if rows is None:
            return None
        return _bits_to_surface(rows, self.cw * (2 if wide else 1), self.ch)


class BitmapFont(Font):
    """generic bitmap font from a dict char -> rows of bits"""

    def __init__(self, name, cw, ch, glyphs):
        super().__init__()
        self.name, self.cw, self.ch = name, cw, ch
        self.glyphs = glyphs  # char -> (rows, ox, oy)

    def raw(self, c, style, wide):
        g = self.glyphs.get(c)
        if g is None:
            return None
        rows, ox, oy = g
        return _bits_to_surface(rows, self.cw * (2 if wide else 1), self.ch, ox, oy)


def load_psf(path):
    with open(path, 'rb') as fh:
        data = fh.read()
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)
    glyphs = {}
    if data[:2] == b'\x36\x04':
        mode, h = data[2], data[3]
        n = 512 if mode & 1 else 256
        w, size, off = 8, h, 4
        bitmaps = [data[off + i * size: off + (i + 1) * size] for i in range(n)]
        table = None
        if mode & 6:
            table = {}
            p, gi = off + n * size, 0
            while p + 1 < len(data) and gi < n:
                u = data[p] | data[p + 1] << 8
                p += 2
                if u == 0xFFFF:
                    gi += 1
                elif u != 0xFFFE:
                    table.setdefault(chr(u), gi)
    elif data[:4] == b'\x72\xb5\x4a\x86':
        import struct
        _, hs, flags, n, size, h, w = struct.unpack('<7I', data[4:32])
        bitmaps = [data[hs + i * size: hs + (i + 1) * size] for i in range(n)]
        table = None
        if flags & 1:
            table = {}
            p, gi = hs + n * size, 0
            buf = bytearray()
            while p < len(data) and gi < n:
                b = data[p]
                p += 1
                if b == 0xFF or b == 0xFE:
                    if buf:
                        try:
                            for ch in bytes(buf).decode('utf-8'):
                                table.setdefault(ch, gi)
                                break
                        except UnicodeDecodeError:
                            pass
                    buf = bytearray()
                    if b == 0xFF:
                        gi += 1
                    else:  # sequences: skip until 0xFF
                        while p < len(data) and data[p] != 0xFF:
                            p += 1
                else:
                    buf.append(b)
    else:
        raise ValueError('not a PSF font')
    bpr = (w + 7) // 8
    if table is None:
        table = {CP437[i]: i for i in range(min(256, len(bitmaps)))}

    def rows_of(bm):
        rows = []
        for y in range(h):
            line = int.from_bytes(bm[y * bpr:(y + 1) * bpr], 'big')
            rows.append([(line >> (bpr * 8 - 1 - x)) & 1 for x in range(w)])
        return rows

    for ch, gi in table.items():
        if gi < len(bitmaps):
            glyphs[ch] = (rows_of(bitmaps[gi]), 0, 0)
    return BitmapFont(os.path.basename(path).split('.')[0], w, h, glyphs)


def load_bdf(path):
    glyphs = {}
    fbb = (8, 16, 0, 0)
    ascent = descent = None
    with open(path, 'r', encoding='latin-1') as fh:
        lines = fh.read().splitlines()
    i = 0
    enc = bbx = None
    while i < len(lines):
        ln = lines[i].strip()
        if ln.startswith('FONTBOUNDINGBOX'):
            fbb = tuple(int(v) for v in ln.split()[1:5])
        elif ln.startswith('FONT_ASCENT'):
            ascent = int(ln.split()[1])
        elif ln.startswith('FONT_DESCENT'):
            descent = int(ln.split()[1])
        elif ln.startswith('ENCODING'):
            enc = int(ln.split()[1])
        elif ln.startswith('BBX'):
            bbx = tuple(int(v) for v in ln.split()[1:5])
        elif ln == 'BITMAP' and enc is not None and enc >= 0 and bbx:
            bw, bh, bx, by = bbx
            rows = []
            for k in range(bh):
                hx = lines[i + 1 + k].strip()
                v = int(hx, 16) if hx else 0
                nb = len(hx) * 4
                rows.append([(v >> (nb - 1 - x)) & 1 for x in range(bw)])
            glyphs[chr(enc)] = (rows, bbx, None)
            i += bh
            enc = bbx = None
        i += 1
    if ascent is None:
        ascent = fbb[1] + fbb[3]
    if descent is None:
        descent = -fbb[3]
    cw, ch = fbb[0], ascent + descent
    out = {}
    for c, (rows, (bw, bh, bx, by), _) in glyphs.items():
        oy = ascent - (bh + by)
        ox = bx - fbb[2]
        out[c] = (rows, ox, oy)
    return BitmapFont(os.path.basename(path).rsplit('.', 1)[0], cw, ch, out)


class PixelFont(Font):
    """Editable bitmap font: char -> bool array (cw, ch). PNG sheets load into
    this class, the Studio font editor works on it."""

    def __init__(self, name, cw, ch, bits=None):
        super().__init__()
        self.name, self.cw, self.ch = name, cw, ch
        self.bits = bits or {}
        self.path = None
        self.meta = {}
        self.edited = set()

    @classmethod
    def from_sheet(cls, path, cols=16, rows=16, cell=None):
        img = pygame.image.load(path)
        W, H = img.get_size()
        cw, ch = cell if cell else (W // cols, H // rows)
        rgb = pygame.surfarray.array3d(img).astype(np.int32)
        lum = (rgb[..., 0] * 3 + rgb[..., 1] * 6 + rgb[..., 2]) // 10
        if img.get_flags() & pygame.SRCALPHA:
            lum = np.minimum(lum, pygame.surfarray.array_alpha(img))
        ink = lum > 110
        bits = {}
        for i, c in enumerate(CP437):
            gx, gy = (i % cols) * cw, (i // cols) * ch
            if gx + cw <= W and gy + ch <= H:
                bits[c] = ink[gx:gx + cw, gy:gy + ch].copy()
        f = cls(os.path.basename(path).rsplit('.', 1)[0], cw, ch, bits)
        f.path = path
        return f

    @classmethod
    def from_font(cls, font, cw=None, ch=None, name=None):
        cw, ch = cw or font.cw, ch or font.ch
        bits = {}
        keys = list(CP437)
        extra = getattr(font, 'data', None) or getattr(font, 'glyphs', None) or {}
        keys += [k for k in extra if k not in UNI_TO_CP437]
        for c in keys:
            if c == '\u0000':
                continue
            g = font.glyph(c)
            if g.get_size() != (cw, ch):
                g = pygame.transform.scale(g, (cw, ch))
            bits[c] = pygame.surfarray.array_alpha(g) > 110
        return cls(name or (font.name + '_edit'), cw, ch, bits)

    def raw(self, c, style, wide):
        b = self.bits.get(c)
        if b is None or not b.any():
            return None if b is None else self._blank(wide)
        s = self._blank(wide)
        a = pygame.surfarray.pixels_alpha(s)
        a[:self.cw, :] = b * 255
        del a
        return s

    def _blank(self, wide):
        s = pygame.Surface((self.cw * (2 if wide else 1), self.ch), pygame.SRCALPHA)
        s.fill((255, 255, 255, 0))
        return s

    def get_bits(self, c):
        b = self.bits.get(c)
        if b is None:
            b = np.zeros((self.cw, self.ch), bool)
            self.bits[c] = b
        return b

    def touch(self, c):
        self.edited.add(c)
        for k in [k for k in self.cache if k[0] == c]:
            del self.cache[k]
        for k in [k for k in self.pcache if k[0] == c]:
            del self.pcache[k]

    def set_pixel(self, c, x, y, v):
        b = self.get_bits(c)
        if 0 <= x < self.cw and 0 <= y < self.ch and b[x, y] != v:
            b[x, y] = v
            self.touch(c)
            return True
        return False

    def save(self, name=None):
        from . import yamlio
        name = name or self.name
        os.makedirs(FONT_DIR, exist_ok=True)
        png = os.path.join(FONT_DIR, name + '.png')
        s = pygame.Surface((self.cw * 16, self.ch * 16))
        s.fill((0, 0, 0))
        arr = pygame.surfarray.pixels3d(s)
        for i, c in enumerate(CP437):
            b = self.bits.get(c)
            if b is not None:
                gx, gy = (i % 16) * self.cw, (i // 16) * self.ch
                arr[gx:gx + self.cw, gy:gy + self.ch][b] = 255
        del arr
        pygame.image.save(s, png)
        meta = {'name': name, 'type': 'sheet', 'file': name + '.png', 'cell': [self.cw, self.ch],
                'layout': 'cp437 16x16', 'description': self.meta.get('description', 'made with pixelterm studio')}
        ypath = os.path.join(FONT_DIR, name + '.yaml')
        yamlio.dump(meta, ypath, header='pixelterm pixel font - edit %s in any pixel editor (white = ink)' % (name + '.png'))
        self.name = name
        self.path = ypath
        return ypath


class TTFFont(Font):
    synth_styles = False

    def __init__(self, path, size=16, antialias=True, sysname=None):
        super().__init__()
        self.pixel = not antialias
        self.aa = antialias
        self.fonts = {}
        for st in (0, BOLD, ITALIC, BOLD | ITALIC):
            if sysname:
                f = pygame.font.SysFont(sysname, size, bold=bool(st & BOLD), italic=bool(st & ITALIC))
            else:
                f = pygame.font.Font(path, size)
                f.bold = bool(st & BOLD)
                f.italic = bool(st & ITALIC)
            self.fonts[st] = f
        f0 = self.fonts[0]
        self.cw = max(1, f0.size('M')[0])
        self.ch = max(1, f0.get_linesize())
        self.name = (sysname or os.path.basename(path).rsplit('.', 1)[0]) + '@%d' % size

    def raw(self, c, style, wide):
        f = self.fonts.get(style & 5, self.fonts[0])
        try:
            r = f.render(c, self.aa, (255, 255, 255))
        except (pygame.error, ValueError):
            return None
        if r.get_width() == 0:
            return None
        w = self.cw * (2 if wide else 1)
        # glyph not in font? pygame renders a tofu: detect via metrics
        try:
            m = f.metrics(c)
            if not m or m[0] is None:
                return None
        except Exception:
            pass
        s = pygame.Surface((w, self.ch), pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        rw = r.get_width()
        if rw > w + 1:
            r = pygame.transform.smoothscale(r, (w, r.get_height())) if self.aa else \
                pygame.transform.scale(r, (w, r.get_height()))
            rw = w
        s.blit(r, ((w - rw) // 2, 0))
        return s


# ============================================================================
def derived_builtin(kind):
    """Retro variants generated from the built-in 5x9 font:
    fat8   - 8x8 cell, double-width strokes (C64 / NES / Game Boy look)
    topaz  - 8x10 cell, double-width strokes + descenders (Amiga Topaz look)
    thin8  - 8x8 cell, single strokes (Atari / MSX look)"""
    base = BuiltinFont()
    if kind == 'c64narrow':
        return _narrow8(base)
    bold = kind in ('fat8', 'topaz')
    cw, ch = (8, 10) if kind == 'topaz' else (8, 8)
    bits = {}
    for c, rows in base.data.items():
        a = np.array(rows, bool).T  # (5, 9)
        if ch == 8:
            if a[:, 7:].any():
                # descender glyph: drop one empty row so it fits 8 rows
                drop = 0 if not a[:, 0].any() else next((y for y in range(1, 7) if not a[:, y].any()), 1)
                a = np.delete(a, drop, axis=1)
            a = a[:, :8]
        g = np.zeros((cw, ch), bool)
        h = min(a.shape[1], ch)
        g[1:6, :h] = a[:, :h]
        if bold:
            g[2:7, :h] |= a[:, :h]
        bits[c] = g
    if bold and '"' in bits:                       # doubled strokes would merge the two ticks of the quote
        q = np.zeros((cw, ch), bool)
        q[1:3, 0:3] = True
        q[4:6, 0:3] = True
        bits['"'] = q
    f = PixelFont(kind, cw, ch, bits)
    # glyphs the builtin lacks: render from a fallback, crisp
    return f


def _narrow8(base):
    """builtin:c64narrow - 4x8 cells (3 px letters + 1 px gap) for 80 columns inside the C64's 320 px,
    like the 80-column programs of the time"""
    bits = {}
    for c, rows in base.data.items():
        a = np.array(rows, bool).T  # (5, 9)
        if a[:, 7:].any():
            drop = 0 if not a[:, 0].any() else next((y for y in range(1, 7) if not a[:, y].any()), 1)
            a = np.delete(a, drop, axis=1)
        a = a[:, :8]
        g = np.zeros((4, 8), bool)
        h = a.shape[1]
        g[1, :h] = a[0] | a[1]          # column 0 stays blank like on the C64, so text never touches the border
        g[2, :h] = a[2]
        g[3, :h] = a[3] | a[4]
        bits[c] = g
    return PixelFont('c64narrow', 4, 8, bits)


class AnimatedFont(Font):
    """A font with several frames per glyph (any Font objects of equal cell size)."""
    animated = True
    synth_styles = False

    def __init__(self, name, frames, fps=8):
        super().__init__()
        self.name = name
        self.frames = frames
        self.fps = float(fps)
        self.frame = 0
        self.cw, self.ch = frames[0].cw, frames[0].ch
        self.pixel = frames[0].pixel
        self.path = None
        self.meta = {}

    def set_frame(self, i):
        self.frame = i % len(self.frames)

    def glyph(self, c, style=0, wide=False):
        return self.frames[self.frame].glyph(c, style, wide)

    def pixels(self, c, style=0):
        return self.frames[0].pixels(c, style)

    def clear(self):
        for f in self.frames:
            f.clear()

    def save(self, name=None):
        """write <name>_0.png .. <name>_N.png + <name>.yaml (editable pixel frames only)"""
        from . import yamlio
        name = name or self.name
        files = []
        for i, fr in enumerate(self.frames):
            if not isinstance(fr, PixelFont):
                fr = PixelFont.from_font(fr)
            p = fr.save('%s_%d' % (name, i))
            os.remove(p)  # frame yaml not needed, the animated yaml lists the pngs
            files.append('%s_%d.png' % (name, i))
        meta = {'name': name, 'type': 'animated', 'fps': self.fps, 'cell': [self.cw, self.ch], 'frames': files,
                'description': self.meta.get('description', 'animated pixel font')}
        ypath = os.path.join(FONT_DIR, name + '.yaml')
        yamlio.dump(meta, ypath, header='pixelterm animated font - one PNG sheet per frame (16x16 CP437 grid)')
        self.path = ypath
        self.name = name
        return ypath


class _FuncFont(Font):
    """frame generated from a base font through a surface transform"""

    def __init__(self, base, fn, cw=None, ch=None, name='frame'):
        super().__init__()
        self.base, self.fn = base, fn
        self.cw, self.ch = cw or base.cw, ch or base.ch
        self.pixel = base.pixel
        self.name = name
        self.synth_styles = False

    def raw(self, c, style, wide):
        g = self.base.glyph(c, style, wide)
        return self.fn(g, self.cw * (2 if wide else 1), self.ch)


def animated_builtin(kind, base=None):
    """wave | shimmer | jelly | bounce - generated animated variants of any font"""
    base = base or PixelFont.from_font(BuiltinFont(), name='builtin')
    n = 8
    frames = []
    for f in range(n):
        ph = f / n * 2 * np.pi
        if kind == 'wave':
            def fn(g, w, h, ph=ph):
                out = pygame.Surface((w, h), pygame.SRCALPHA)
                out.fill((0, 0, 0, 0))
                for x in range(g.get_width()):
                    dy = int(round(np.sin(ph + x * 0.7)))
                    out.blit(g, (x, 1 + dy), (x, 0, 1, g.get_height()))
                return out
            frames.append(_FuncFont(base, fn, ch=base.ch + 2, name='wave%d' % f))
        elif kind == 'shimmer':
            def fn(g, w, h, ph=ph, f=f):
                out = g.copy()
                a = pygame.surfarray.pixels_alpha(out)
                xs = np.arange(a.shape[0])[:, None]
                ys = np.arange(a.shape[1])[None, :]
                band = ((xs + ys + f * 3) % 24) < 4
                a[:] = (a * np.where(band, 1.0, 0.55)).astype(np.uint8)
                del a
                return out
            frames.append(_FuncFont(base, fn, name='shimmer%d' % f))
        elif kind == 'jelly':
            def fn(g, w, h, ph=ph):
                k = 1 + 0.12 * np.sin(ph)
                gw, gh = g.get_size()
                nw, nh = max(1, int(gw * (2 - k))), max(1, int(gh * k))
                sc = pygame.transform.scale(g, (nw, min(h, nh)))
                out = pygame.Surface((w, h), pygame.SRCALPHA)
                out.fill((0, 0, 0, 0))
                out.blit(sc, ((w - nw) // 2, h - sc.get_height()))
                return out
            frames.append(_FuncFont(base, fn, name='jelly%d' % f))
        else:  # bounce: letters hop in a travelling wave
            def fn(g, w, h, ph=ph):
                out = pygame.Surface((w, h), pygame.SRCALPHA)
                out.fill((0, 0, 0, 0))
                out.blit(g, (0, 2 - int(round(abs(np.sin(ph)) * 2))))
                return out
            frames.append(_FuncFont(base, fn, ch=base.ch + 2, name='bounce%d' % f))
    f = AnimatedFont('builtin:' + kind, frames, fps=10)
    return f


# ============================================================================ big Amiga demo fonts
SWEEPS = {
    # copper-bar palettes the inside of the letters sweeps through
    'amiga': [(255, 40, 40), (255, 140, 20), (255, 230, 40), (255, 255, 230), (40, 230, 255), (40, 90, 255),
              (190, 50, 255), (255, 40, 160)],
    'amigachrome': [(30, 60, 160), (90, 150, 230), (210, 235, 255), (255, 255, 255), (255, 220, 120), (200, 120, 40),
                    (120, 60, 30), (60, 70, 150)],
    'amigafire': [(120, 0, 0), (220, 30, 0), (255, 120, 0), (255, 210, 40), (255, 255, 200), (255, 210, 40),
                  (255, 120, 0), (220, 30, 0)],
}


class _SweepFrame(Font):
    """one frame of an outlined font: dark outline, the inside filled with a
    horizontal color sweep that moves one pixel per frame (period = cell width,
    so the sweep runs seamlessly from letter to letter)"""
    colored = True

    def __init__(self, masks, cw, ch, k, pal, frame, name):
        super().__init__()
        self.masks, self.cw, self.ch, self.k = masks, cw, ch, k
        self.pal, self.frame = pal, frame
        self.name = name
        self.synth_styles = False

    def mask(self, c):
        m = self.masks.get(c)
        if m is None:
            src = BuiltinFont().data.get(c)
            iw, ih = self.cw - 2, self.ch - 2
            if src is not None:
                a = np.array(src, bool).T                  # 5 x 9
                g = np.zeros((8, 10), bool)
                g[1:6, :9] = a
                g[2:7, :9] |= a                            # Topaz-style double strokes
                m = np.repeat(np.repeat(g, self.k, 0), self.k, 1)[:iw, :ih]
            else:
                r = fallback().render(c, iw, ih, aa=False)
                if r is None:
                    return None
                m = pygame.surfarray.array_alpha(r) > 96
            self.masks[c] = m
        return m

    def raw(self, c, style, wide):
        m = self.mask(c)
        if m is None or not m.any():
            return None if m is None else self._blank()
        cw, ch = self.cw, self.ch
        fill = np.zeros((cw, ch), bool)
        fill[1:1 + m.shape[0], 1:1 + m.shape[1]] = m
        grow = fill.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            grow |= np.roll(np.roll(fill, dx, 0), dy, 1)
        outline = grow & ~fill
        pal = np.array(self.pal, np.float32)
        n = len(pal)
        xs = (np.arange(cw) + self.frame) % cw / cw * n          # sweep position per column
        i0 = np.floor(xs).astype(int) % n
        f = (xs - np.floor(xs))[:, None]
        cols = pal[i0] * (1 - f) + pal[(i0 + 1) % n] * f         # (cw, 3)
        shade = 1.12 - 0.45 * (np.arange(ch) / max(1, ch - 1))   # lighter top, darker bottom
        rgb = np.clip(cols[:, None, :] * shade[None, :, None], 0, 255)
        # a bright bevel line on the top edge of every stroke
        top = fill & ~np.roll(fill, 1, 1)
        rgb[top] = np.minimum(255, rgb[top] * 0.4 + 170)
        rgb[outline] = (16, 8, 24)
        s = pygame.Surface((cw * (2 if wide else 1), ch), pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        tmp = pygame.Surface((cw, ch), pygame.SRCALPHA)
        pygame.surfarray.pixels3d(tmp)[:] = rgb.astype(np.uint8)
        al = pygame.surfarray.pixels_alpha(tmp)
        al[:] = np.where(fill | outline, 255, 0).astype(np.uint8)
        del al
        s.blit(tmp, (0, 0))
        return s

    def _blank(self):
        s = pygame.Surface((self.cw, self.ch), pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        return s


def amiga_big(kind='amiga', k=2):
    """big outlined demo font with an animated horizontal color sweep inside:
    builtin:amiga (copper rainbow), builtin:amigachrome, builtin:amigafire"""
    cw, ch = 8 * k + 2, 10 * k + 2
    masks = {}
    pal = SWEEPS.get(kind, SWEEPS['amiga'])
    frames = [_SweepFrame(masks, cw, ch, k, pal, i, '%s%d' % (kind, i)) for i in range(cw)]
    f = AnimatedFont('builtin:' + kind, frames, fps=18)
    f.colored = True
    f.tint_mix = 0.55      # how much of the ANSI color tints the sweep (0 = pure sweep)
    return f


# ============================================================================ scroller fonts (huge, chrome)
SCROLLER_STYLES = {
    # (top gradient, horizon line, bottom gradient) - the classic "chrome" demo look
    'scroller': ([(20, 40, 120), (90, 150, 240), (200, 230, 255)], (255, 255, 255),
                 [(90, 50, 20), (200, 120, 40), (255, 210, 120)]),
    'scrollergold': ([(110, 60, 0), (230, 160, 30), (255, 240, 170)], (255, 255, 240),
                     [(90, 40, 0), (190, 110, 20), (255, 200, 80)]),
    'scrollerice': ([(10, 60, 90), (60, 190, 230), (220, 250, 255)], (255, 255, 255),
                    [(20, 50, 110), (60, 110, 200), (160, 210, 255)]),
}


def _chamfered(base_bits, k):
    """scale a small bitmap by k and cut 45 degree bevels into its outer corners"""
    g = base_bits
    W, H = g.shape
    m = np.repeat(np.repeat(g, k, 0), k, 1)
    cut = max(1, k // 2)
    ii, jj = np.meshgrid(np.arange(k), np.arange(k), indexing='ij')
    on = lambda x, y: 0 <= x < W and 0 <= y < H and g[x, y]
    for x in range(W):
        for y in range(H):
            if not g[x, y]:
                continue
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                if not on(x + dx, y) and not on(x, y + dy) and not on(x + dx, y + dy):
                    cx = ii if dx < 0 else k - 1 - ii
                    cy = jj if dy < 0 else k - 1 - jj
                    blk = m[x * k:(x + 1) * k, y * k:(y + 1) * k]
                    blk[(cx + cy) < cut] = False
    return m


def _grad(stops, n):
    stops = np.array(stops, np.float32)
    t = np.linspace(0, 1, n) * (len(stops) - 1)
    i = np.minimum(np.floor(t).astype(int), len(stops) - 2)
    f = (t - i)[:, None]
    return stops[i] * (1 - f) + stops[i + 1] * f


class _ScrollerFrame(Font):
    colored = True

    def __init__(self, masks, k, style, frame, nframes, name):
        super().__init__()
        self.masks, self.k, self.style = masks, k, style
        self.frame, self.nframes = frame, nframes
        self.cw, self.ch = 8 * k + 5, 10 * k + 5
        self.name = name
        self.synth_styles = False

    def mask(self, c):
        m = self.masks.get(c)
        if m is None:
            src = BuiltinFont().data.get(c)
            if src is None:
                r = fallback().render(c, 8, 10, aa=False)
                if r is None:
                    return None
                g = pygame.surfarray.array_alpha(r) > 96
            else:
                a = np.array(src, bool).T
                g = np.zeros((8, 10), bool)
                g[1:6, :9] = a
                g[2:7, :9] |= a
            m = _chamfered(g, self.k)
            self.masks[c] = m
        return m

    def raw(self, c, style, wide):
        m = self.mask(c)
        cw, ch = self.cw, self.ch
        s = pygame.Surface((cw * (2 if wide else 1), ch), pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        if m is None or not m.any():
            return s if m is not None else None
        fill = np.zeros((cw, ch), bool)
        fill[2:2 + m.shape[0], 2:2 + m.shape[1]] = m
        grow = fill.copy()
        for _ in range(2):                                   # 2 px outline
            g2 = grow.copy()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                g2 |= np.roll(np.roll(grow, dx, 0), dy, 1)
            grow = g2
        outline = grow & ~fill
        shadow = np.roll(np.roll(grow, 2, 0), 2, 1) & ~grow   # drop shadow down-right
        top, horizon, bot = SCROLLER_STYLES[self.style]
        y0, y1 = 2, 2 + 10 * self.k - 1
        hy = y0 + int((y1 - y0) * 0.5)
        col = np.zeros((ch, 3), np.float32)
        col[:hy] = _grad(top, hy)
        col[hy:] = _grad(bot, ch - hy)
        col[hy] = horizon
        rgb = np.repeat(col[None, :, :], cw, 0)
        # a diagonal glint sweeping across (one pixel per frame)
        xs = np.arange(cw)[:, None] + np.arange(ch)[None, :] * 0.5
        pos = (xs - self.frame * cw / self.nframes) % cw
        glint = np.clip(1 - np.abs(pos - cw * 0.5) / 2.5, 0, 1)
        rgb = rgb + (255 - rgb) * glint[..., None] * 0.8
        # inner bevel: light top-left edge, dark bottom-right edge
        tl = fill & ~(np.roll(fill, 1, 0) & np.roll(fill, 1, 1))
        br = fill & ~(np.roll(fill, -1, 0) & np.roll(fill, -1, 1))
        rgb[tl] = np.minimum(255, rgb[tl] * 0.5 + 140)
        rgb[br] = rgb[br] * 0.55
        rgb[outline] = (10, 6, 16)
        rgb[shadow] = (0, 0, 0)
        tmp = pygame.Surface((cw, ch), pygame.SRCALPHA)
        pygame.surfarray.pixels3d(tmp)[:] = np.clip(rgb, 0, 255).astype(np.uint8)
        al = pygame.surfarray.pixels_alpha(tmp)
        al[:] = np.where(fill | outline, 255, np.where(shadow, 110, 0)).astype(np.uint8)
        del al
        s.blit(tmp, (0, 0))
        return s


def scroller_font(kind='scroller', k=4):
    """huge beveled chrome letters as used in Amiga demo scrollers (36 x 45 cells):
    builtin:scroller (chrome), builtin:scrollergold, builtin:scrollerice. Animated glint."""
    masks = {}
    n = 24
    frames = [_ScrollerFrame(masks, k, kind if kind in SCROLLER_STYLES else 'scroller', i, n, '%s%d' % (kind, i))
              for i in range(n)]
    f = AnimatedFont('builtin:' + kind, frames, fps=12)
    f.colored = True
    f.tint_mix = 0.25
    return f


# ============================================================================ cute little animated font
def cute_font(base=None):
    """builtin:cute - the small built-in font, softened; now and then a letter
    does a tiny one-pixel hop (staggered per letter, slow and calm), and the
    dots of . ! ? turn into little hearts for a moment"""
    base = base or PixelFont.from_font(BuiltinFont(), name='builtin')
    n = 24
    heartable = set('.!?')

    def soften(g):
        a = pygame.surfarray.array_alpha(g) > 96
        W, H = a.shape
        out = a.copy()
        on = lambda x, y: 0 <= x < W and 0 <= y < H and a[x, y]
        for x in range(W):
            for y in range(H):
                if a[x, y]:
                    n4 = on(x - 1, y) + on(x + 1, y) + on(x, y - 1) + on(x, y + 1)
                    # outer corner of a thick block: shave it for a rounder look
                    if n4 == 2 and ((on(x + 1, y) and on(x, y + 1) and on(x + 1, y + 1) and not on(x - 1, y) and not on(x, y - 1))
                                    or (on(x - 1, y) and on(x, y + 1) and on(x - 1, y + 1) and not on(x + 1, y) and not on(x, y - 1))):
                        out[x, y] = False
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        pygame.surfarray.pixels3d(s)[:] = 255
        al = pygame.surfarray.pixels_alpha(s)
        al[:] = (out * 255).astype(np.uint8)
        del al
        return s

    soft = {}

    class _CuteFrame(Font):
        def __init__(self, f):
            super().__init__()
            self.f = f
            self.cw, self.ch = base.cw, base.ch + 1
            self.pixel = True
            self.synth_styles = False
            self.name = 'cute%d' % f

        def raw(self, c, style, wide):
            g = base.glyph(c, style, wide)
            key = (c, style, wide)
            sg = soft.get(key)
            if sg is None:
                sg = soft[key] = soften(g)
            w = self.cw * (2 if wide else 1)
            out = pygame.Surface((w, self.ch), pygame.SRCALPHA)
            out.fill((0, 0, 0, 0))
            ph = (self.f + (ord(c[0]) * 7) % n) % n        # every letter has its own moment
            hop = 1 if ph == 0 else 0
            out.blit(sg, (0, 1 - hop))
            if c in heartable and (self.f + ord(c[0]) * 5) % n in (3, 4, 5):
                # the dot becomes a tiny 3x3 heart for a moment
                a = pygame.surfarray.array_alpha(out) > 96
                rows = np.nonzero(a.any(axis=0))[0]
                if len(rows):
                    y = int(rows[-1])
                    xs = np.nonzero(a[:, y])[0]
                    x = int(round(xs.mean()))
                    hy = y - 1
                    pygame.draw.rect(out, (0, 0, 0, 0), (x - 1, hy - 1, 3, 4))
                    for px, py in ((x - 1, hy), (x + 1, hy), (x - 1, hy + 1), (x, hy + 1), (x + 1, hy + 1), (x, hy + 2)):
                        if 0 <= px < w and 0 <= py < self.ch:
                            out.set_at((px, py), (255, 255, 255, 255))
            return out

    f = AnimatedFont('builtin:cute', [_CuteFrame(i) for i in range(n)], fps=6)
    return f


# ============================================================================ roman inscription font
SERIF_SYS = 'timesnewroman,georgia,cambria,palatinolinotype,bookantiqua,liberationserif,dejavuserif,freeserif,notoserif,serif'


class RomanFont(Font):
    """builtin:roman - classic serif capitals (from the system's serif font) carved into the stone:
    the upper-left wall of every groove lies in shadow, the lower-right wall catches the light.
    A colored font: the ANSI color tints the carving like the red paint in Roman inscriptions."""
    colored = True
    tint_mix = 0.6
    synth_styles = False

    def __init__(self, cw=12, ch=20):
        super().__init__()
        self.cw, self.ch = cw, ch
        self.name = 'roman'
        self.path = None
        for n in SERIF_SYS.split(','):
            p = pygame.font.match_font(n, bold=True) or pygame.font.match_font(n)
            if p:
                self.path = p
                break
        self.f = None
        if self.path:
            # render at 3x and shrink: smoother serifs than the small size would give
            size = 3 * int(ch * 0.92)
            self.f = pygame.font.Font(self.path, size)
            self.base = BuiltinFont()
        else:
            self.base = derived_builtin('topaz')

    def mask(self, c, wide):
        w = self.cw * (2 if wide else 1)
        if self.f is not None:
            try:
                r = self.f.render(c, True, (255, 255, 255))
            except (pygame.error, ValueError):
                r = None
            if r is None or r.get_width() == 0:
                return None
            asc = self.f.get_ascent()
            big = pygame.Surface((w * 3, self.ch * 3), pygame.SRCALPHA)
            big.fill((0, 0, 0, 0))
            rw = r.get_width()
            if rw > w * 3:
                r = pygame.transform.smoothscale(r, (w * 3, r.get_height()))
                rw = w * 3
            big.blit(r, ((w * 3 - rw) // 2, int(self.ch * 3 * 0.8) - asc))
            small = pygame.transform.smoothscale(big, (w, self.ch))
            m = pygame.surfarray.array_alpha(small) > 70
            # chisel width: every groove at least 2 px wide so it can show a shadow and a lit wall
            m2 = m.copy()
            m2[1:, :] |= m[:-1, :]
            return m2
        g = self.base.glyph(c, 0, wide)
        a = pygame.surfarray.array_alpha(pygame.transform.scale(g, (w, self.ch)))
        return a > 96

    def raw(self, c, style, wide):
        m = self.mask(c, wide)
        if m is None:
            return None
        w, h = m.shape
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        if not m.any():
            return s
        up = np.zeros_like(m)
        up[:, 1:] = m[:, :-1]
        left = np.zeros_like(m)
        left[1:, :] = m[:-1, :]
        down = np.zeros_like(m)
        down[:, :-1] = m[:, 1:]
        right = np.zeros_like(m)
        right[:-1, :] = m[1:, :]
        shadow = m & (~up | ~left)             # upper-left wall of the groove: in shadow
        light = m & (~down | ~right) & ~shadow  # lower-right wall: catches the light
        rgb = np.zeros((w, h, 3), np.float32)
        rgb[m] = (118, 100, 84)                 # bottom of the groove
        rgb[shadow] = (52, 42, 34)
        rgb[light] = (226, 214, 192)
        pygame.surfarray.pixels3d(s)[:] = rgb.astype(np.uint8)
        al = pygame.surfarray.pixels_alpha(s)
        al[:] = np.where(m, 255, 0).astype(np.uint8)
        del al
        return s


def list_fonts():
    out = ['builtin', 'builtin:fat8', 'builtin:topaz', 'builtin:thin8', 'builtin:c64narrow',
           'builtin:wave', 'builtin:shimmer', 'builtin:jelly', 'builtin:bounce',
           'builtin:amiga', 'builtin:amigachrome', 'builtin:amigafire', 'builtin:cute',
           'builtin:scroller', 'builtin:scrollergold', 'builtin:scrollerice', 'builtin:roman']
    if os.path.isdir(FONT_DIR):
        for fn in sorted(os.listdir(FONT_DIR)):
            low = fn.lower()
            base = fn.rsplit('.', 1)[0]
            if low.endswith('.png') and (os.path.exists(os.path.join(FONT_DIR, base + '.yaml')) or
                                         os.path.exists(os.path.join(FONT_DIR, base.rsplit('_', 1)[0] + '.yaml'))):
                continue  # described by a yaml
            if low.endswith(('.ttf', '.otf', '.bdf', '.psf', '.psf.gz', '.png', '.yaml', '.yml')):
                out.append('fonts/' + fn)
    out += ['sys:consolas', 'sys:dejavusansmono', 'sys:couriernew']
    return out


def load_font(spec='builtin', size=16, antialias=True):
    """spec: builtin | path | sys:Name. Paths may be relative to the fonts dir."""
    spec = (spec or 'builtin').strip()
    if spec == 'builtin':
        f = PixelFont.from_font(BuiltinFont(), name='builtin')
        return f
    if spec.startswith('builtin:'):
        kind = spec.split(':', 1)[1]
        if kind in ('wave', 'shimmer', 'jelly', 'bounce'):
            return animated_builtin(kind)
        if kind in SWEEPS:
            return amiga_big(kind)
        if kind in SCROLLER_STYLES:
            return scroller_font(kind)
        if kind == 'cute':
            return cute_font()
        if kind == 'roman':
            return RomanFont()
        return derived_builtin(kind)
    if spec.startswith('sys:'):
        name = spec[4:]
        p = pygame.font.match_font(name)
        if not p:
            p = fallback().path
        return TTFFont(p, size, antialias)
    path = spec
    if not os.path.exists(path):
        alt = os.path.join(FONT_DIR, spec)
        alt2 = os.path.join(os.path.dirname(FONT_DIR), spec)
        path = alt if os.path.exists(alt) else alt2
    low = path.lower()
    if not os.path.exists(path):
        print('[pixelterm] font not found: %s - using builtin' % spec)
        return BuiltinFont()
    if low.endswith(('.ttf', '.otf', '.ttc')):
        f = TTFFont(path, size, antialias)
        f.path = path
        return f
    if low.endswith('.bdf'):
        f = load_bdf(path)
        f.path = path
        return f
    if low.endswith(('.psf', '.psf.gz', '.psfu', '.psfu.gz')):
        f = load_psf(path)
        f.path = path
        return f
    if low.endswith('.png'):
        return PixelFont.from_sheet(path)
    if low.endswith(('.yaml', '.yml')):
        from . import yamlio
        meta = yamlio.load(path) or {}
        target = os.path.join(os.path.dirname(path), meta.get('file', ''))
        if meta.get('type') == 'animated':
            cell = tuple(meta['cell']) if meta.get('cell') else None
            frames = [PixelFont.from_sheet(os.path.join(os.path.dirname(path), fn), cell=cell) for fn in meta['frames']]
            f = AnimatedFont(meta.get('name', 'animated'), frames, meta.get('fps', 8))
            f.meta = meta
            f.path = path
            return f
        if meta.get('type', 'sheet') == 'sheet' or target.lower().endswith('.png'):
            f = PixelFont.from_sheet(target, cell=tuple(meta['cell']) if meta.get('cell') else None)
        else:
            f = load_font(target, meta.get('size', size), meta.get('antialias', antialias))
        f.meta = meta
        f.name = meta.get('name', f.name)
        f.path = path
        return f
    raise ValueError('unknown font type: %s' % spec)


def export_sheet(font: Font, path: str):
    """Write the CP437 range of any font to a 16x16 PNG sheet - edit it in
    your pixel editor and load it back as a font."""
    s = pygame.Surface((font.cw * 16, font.ch * 16))
    s.fill((0, 0, 0))
    for i, c in enumerate(CP437):
        if i == 0:
            continue
        s.blit(font.glyph(c), ((i % 16) * font.cw, (i // 16) * font.ch))
    pygame.image.save(s, path)
