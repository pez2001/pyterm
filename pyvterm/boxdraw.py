"""Procedurally generated glyphs: box drawing, blocks, shades, braille,
powerline & geometric shapes. Pixel-perfect at every cell size, so ANSI art
and TUIs look right with *any* font."""
from __future__ import annotations

import pygame

L, H, D = 1, 2, 3  # light, heavy, double
# (up, down, left, right)
BOX = {
    '─': (0, 0, L, L), '━': (0, 0, H, H), '│': (L, L, 0, 0), '┃': (H, H, 0, 0),
    '┌': (0, L, 0, L), '┐': (0, L, L, 0), '└': (L, 0, 0, L), '┘': (L, 0, L, 0),
    '├': (L, L, 0, L), '┤': (L, L, L, 0), '┬': (0, L, L, L), '┴': (L, 0, L, L), '┼': (L, L, L, L),
    '┏': (0, H, 0, H), '┓': (0, H, H, 0), '┗': (H, 0, 0, H), '┛': (H, 0, H, 0),
    '┣': (H, H, 0, H), '┫': (H, H, H, 0), '┳': (0, H, H, H), '┻': (H, 0, H, H), '╋': (H, H, H, H),
    '┍': (0, L, 0, H), '┎': (0, H, 0, L), '┑': (0, L, H, 0), '┒': (0, H, L, 0),
    '┕': (L, 0, 0, H), '┖': (H, 0, 0, L), '┙': (L, 0, H, 0), '┚': (H, 0, L, 0),
    '┝': (L, L, 0, H), '┠': (H, H, 0, L), '┥': (L, L, H, 0), '┨': (H, H, L, 0),
    '┯': (0, L, H, H), '┰': (0, H, L, L), '┷': (L, 0, H, H), '┸': (H, 0, L, L),
    '┿': (L, L, H, H), '╂': (H, H, L, L),
    '═': (0, 0, D, D), '║': (D, D, 0, 0), '╔': (0, D, 0, D), '╗': (0, D, D, 0),
    '╚': (D, 0, 0, D), '╝': (D, 0, D, 0), '╠': (D, D, 0, D), '╣': (D, D, D, 0),
    '╦': (0, D, D, D), '╩': (D, 0, D, D), '╬': (D, D, D, D),
    '╒': (0, L, 0, D), '╓': (0, D, 0, L), '╕': (0, L, D, 0), '╖': (0, D, L, 0),
    '╘': (L, 0, 0, D), '╙': (D, 0, 0, L), '╛': (L, 0, D, 0), '╜': (D, 0, L, 0),
    '╞': (L, L, 0, D), '╟': (D, D, 0, L), '╡': (L, L, D, 0), '╢': (D, D, L, 0),
    '╤': (0, L, D, D), '╥': (0, D, L, L), '╧': (L, 0, D, D), '╨': (D, 0, L, L),
    '╪': (L, L, D, D), '╫': (D, D, L, L),
    '╭': (0, L, 0, L), '╮': (0, L, L, 0), '╯': (L, 0, L, 0), '╰': (L, 0, 0, L),
    '╴': (0, 0, L, 0), '╵': (L, 0, 0, 0), '╶': (0, 0, 0, L), '╷': (0, L, 0, 0),
    '╸': (0, 0, H, 0), '╹': (H, 0, 0, 0), '╺': (0, 0, 0, H), '╻': (0, H, 0, 0),
    '╼': (0, 0, L, H), '╽': (L, H, 0, 0), '╾': (0, 0, H, L), '╿': (H, L, 0, 0),
    '┄': (0, 0, L, L), '┅': (0, 0, H, H), '┈': (0, 0, L, L), '┉': (0, 0, H, H),
    '╌': (0, 0, L, L), '╍': (0, 0, H, H), '┆': (L, L, 0, 0), '┇': (H, H, 0, 0),
    '┊': (L, L, 0, 0), '┋': (H, H, 0, 0), '╎': (L, L, 0, 0), '╏': (H, H, 0, 0),
}
DASHED = set('┄┅┈┉╌╍┆┇┊┋╎╏')
ROUNDED = set('╭╮╯╰')

WHITE = (255, 255, 255, 255)


def _box(s, cw, ch, u, d, l, r, dashed=False):
    t = max(1, round(cw / 7))
    cx, cy = (cw - t) // 2, (ch - t) // 2
    g = max(1, t + t // 2)  # double lines sit at center -/+ g

    def th(w):
        return 2 * t if w == H else t

    def pos(c, w):
        return c - (th(w) - t) // 2

    fill = s.fill
    hd = D in (l, r)
    vd = D in (u, d)
    # join box from light/heavy perpendicular lines
    hw = max([th(w) for w in (l, r) if w in (L, H)] or [0])
    vw = max([th(w) for w in (u, d) if w in (L, H)] or [0])
    jy0, jy1 = (cy - (hw - t) // 2, cy - (hw - t) // 2 + hw) if hw else (cy, cy + t)
    jx0, jx1 = (cx - (vw - t) // 2, cx - (vw - t) // 2 + vw) if vw else (cx, cx + t)
    # ---- light / heavy segments
    if u in (L, H):
        y1 = (cy + g + t if d else cy - g + t) if hd else jy1
        fill(WHITE, (pos(cx, u), 0, th(u), y1))
    if d in (L, H):
        y0 = (cy - g if u else cy + g) if hd else jy0
        fill(WHITE, (pos(cx, d), y0, th(d), ch - y0))
    if l in (L, H):
        x1 = (cx + g + t if r else cx - g + t) if vd else jx1
        fill(WHITE, (0, pos(cy, l), x1, th(l)))
    if r in (L, H):
        x0 = (cx - g if l else cx + g) if vd else jx0
        fill(WHITE, (x0, pos(cy, r), cw - x0, th(r)))
    # ---- double segments
    if u == D:
        for side, x in ((-1, cx - g), (1, cx + g)):
            near, far = (l, r) if side < 0 else (r, l)
            if near == D:
                e = cy - g + t
            elif far == D:
                e = cy + g + t
            elif d == D:
                e = cy
            else:
                e = jy1 if (l or r) else cy + t
            fill(WHITE, (x, 0, t, e))
    if d == D:
        for side, x in ((-1, cx - g), (1, cx + g)):
            near, far = (l, r) if side < 0 else (r, l)
            if near == D:
                st = cy + g
            elif far == D:
                st = cy - g
            elif u == D:
                st = cy
            else:
                st = jy0 if (l or r) else cy
            fill(WHITE, (x, st, t, ch - st))
    if l == D:
        for side, y in ((-1, cy - g), (1, cy + g)):
            near, far = (u, d) if side < 0 else (d, u)
            if near == D:
                e = cx - g + t
            elif far == D:
                e = cx + g + t
            elif r == D:
                e = cx
            else:
                e = jx1 if (u or d) else cx + t
            fill(WHITE, (0, y, e, t))
    if r == D:
        for side, y in ((-1, cy - g), (1, cy + g)):
            near, far = (u, d) if side < 0 else (d, u)
            if near == D:
                st = cx + g
            elif far == D:
                st = cx - g
            elif l == D:
                st = cx
            else:
                st = jx0 if (u or d) else cx
            fill(WHITE, (st, y, cw - st, t))
    if dashed:
        if l or r:
            for x in range(0, cw, 3):
                s.fill((0, 0, 0, 0), (x + 2, 0, 1, ch))
        else:
            for y in range(0, ch, 4):
                s.fill((0, 0, 0, 0), (0, y + 3, cw, 1))


def _shade(s, cw, ch, level):
    for y in range(ch):
        for x in range(cw):
            if level == 1:
                on = x % 2 == 0 and y % 2 == 0 and (x // 2 + y // 2) % 2 == 0 or \
                    (x % 2 == 1 and y % 2 == 1 and (x // 2 + y // 2) % 2 == 1)
            elif level == 2:
                on = (x + y) % 2 == 0
            else:
                on = not (x % 2 == 1 and y % 2 == 1)
            if on:
                s.set_at((x, y), WHITE)


QUAD = {'▖': (0, 0, 1, 0), '▗': (0, 0, 0, 1), '▘': (1, 0, 0, 0), '▝': (0, 1, 0, 0),
        '▙': (1, 0, 1, 1), '▚': (1, 0, 0, 1), '▛': (1, 1, 1, 0), '▜': (1, 1, 0, 1),
        '▞': (0, 1, 1, 0), '▟': (0, 1, 1, 1)}


def procedural_glyph(c: str, cw: int, ch: int):
    o = ord(c)
    if not (0x2500 <= o <= 0x25FF or 0x2800 <= o <= 0x28FF or 0xE0B0 <= o <= 0xE0BF):
        return None
    s = pygame.Surface((cw, ch), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    if c in BOX:
        _box(s, cw, ch, *BOX[c], dashed=c in DASHED)
        if c in ROUNDED:  # soften the corner pixel
            t = max(1, round(cw / 7))
            cx, cy = (cw - t) // 2, (ch - t) // 2
            s.fill((0, 0, 0, 0), (cx, cy, t, t))
        return s
    if c == '╱' or c == '╳':
        pygame.draw.line(s, WHITE, (0, ch - 1), (cw - 1, 0), max(1, cw // 7))
    if c == '╲' or c == '╳':
        pygame.draw.line(s, WHITE, (0, 0), (cw - 1, ch - 1), max(1, cw // 7))
    if c in '╱╲╳':
        return s
    # ---- blocks
    if c == '█':
        s.fill(WHITE)
    elif c == '▀':
        s.fill(WHITE, (0, 0, cw, ch // 2))
    elif c == '▔':
        s.fill(WHITE, (0, 0, cw, max(1, ch // 8)))
    elif 0x2581 <= o <= 0x2588:  # lower eighths
        h = round(ch * (o - 0x2580) / 8)
        s.fill(WHITE, (0, ch - h, cw, h))
    elif 0x2589 <= o <= 0x258F:  # left eighths
        w = max(1, round(cw * (8 - (o - 0x2588)) / 8))
        s.fill(WHITE, (0, 0, w, ch))
    elif c == '▐':
        s.fill(WHITE, (cw // 2, 0, cw - cw // 2, ch))
    elif c == '▕':
        s.fill(WHITE, (cw - max(1, cw // 8), 0, max(1, cw // 8), ch))
    elif c in '░▒▓':
        _shade(s, cw, ch, '░▒▓'.index(c) + 1)
    elif c in QUAD:
        a, b, cc, d = QUAD[c]
        hw, hh = cw // 2, ch // 2
        if a: s.fill(WHITE, (0, 0, hw, hh))
        if b: s.fill(WHITE, (hw, 0, cw - hw, hh))
        if cc: s.fill(WHITE, (0, hh, hw, ch - hh))
        if d: s.fill(WHITE, (hw, hh, cw - hw, ch - hh))
    # ---- geometric
    elif c in '■▪':
        m = cw // 6 + (1 if c == '▪' else 0)
        side = cw - 2 * m
        s.fill(WHITE, (m, (ch - side) // 2, side, side))
    elif c in '□▫':
        m = cw // 6
        side = cw - 2 * m
        pygame.draw.rect(s, WHITE, (m, (ch - side) // 2, side, side), 1)
    elif c in '▲▴':
        pygame.draw.polygon(s, WHITE, [(cw // 2, ch // 4), (cw - 1, ch * 3 // 4), (0, ch * 3 // 4)])
    elif c in '▼▾':
        pygame.draw.polygon(s, WHITE, [(0, ch // 4), (cw - 1, ch // 4), (cw // 2, ch * 3 // 4)])
    elif c in '►▶▸':
        pygame.draw.polygon(s, WHITE, [(0, ch // 4), (cw - 1, ch // 2), (0, ch * 3 // 4)])
    elif c in '◄◀◂':
        pygame.draw.polygon(s, WHITE, [(cw - 1, ch // 4), (0, ch // 2), (cw - 1, ch * 3 // 4)])
    elif c in '●○◉':
        r = max(1, cw // 2 - 1)
        pygame.draw.circle(s, WHITE, (cw // 2, ch // 2), r, 0 if c != '○' else 1)
    # ---- braille
    elif 0x2800 <= o <= 0x28FF:
        bits = o - 0x2800
        pos = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3)]
        ds = max(1, cw // 4)
        for i, (bx, by) in enumerate(pos):
            if bits & (1 << i):
                px = int(cw * (1 + 2 * bx) / 4) - ds // 2
                py = int(ch * (1 + 2 * by) / 8) - ds // 2
                s.fill(WHITE, (px, py, ds, ds))
    # ---- powerline
    elif o == 0xE0B0:
        pygame.draw.polygon(s, WHITE, [(0, 0), (cw - 1, ch // 2), (0, ch - 1)])
    elif o == 0xE0B2:
        pygame.draw.polygon(s, WHITE, [(cw - 1, 0), (0, ch // 2), (cw - 1, ch - 1)])
    elif o == 0xE0B1:
        pygame.draw.lines(s, WHITE, False, [(0, 0), (cw - 1, ch // 2), (0, ch - 1)])
    elif o == 0xE0B3:
        pygame.draw.lines(s, WHITE, False, [(cw - 1, 0), (0, ch // 2), (cw - 1, ch - 1)])
    elif o == 0xE0B4:
        pygame.draw.ellipse(s, WHITE, (-cw, 0, cw * 2, ch))
    elif o == 0xE0B6:
        pygame.draw.ellipse(s, WHITE, (0, 0, cw * 2, ch))
    else:
        return None
    return s
