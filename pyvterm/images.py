"""Inline image protocols: Sixel (DCS q), kitty graphics (APC G) and iTerm2
(OSC 1337 File=). Each decoder returns a pygame Surface (SRCALPHA)."""
from __future__ import annotations

import base64
import colorsys
import io
import re
import zlib

import numpy as np
import pygame

DEFAULT16 = [(0, 0, 0), (51, 51, 204), (204, 33, 33), (51, 204, 51), (204, 51, 204), (51, 204, 204),
             (204, 204, 51), (135, 135, 135), (66, 66, 66), (84, 84, 153), (153, 66, 66), (84, 153, 84),
             (153, 84, 153), (84, 153, 153), (153, 153, 84), (204, 204, 204)]
_SIX = re.compile(r'#(\d+)(?:;(\d+);(\d+);(\d+);(\d+))?|!(\d+)([?-~])|"[\d;]*|([?-~]+)|(\$)|(-)')
MAX_DIM = 4096


def _surface_from_rgba(rgba):
    """rgba: (w, h, 4) uint8"""
    w, h = rgba.shape[:2]
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.surfarray.pixels3d(s)[:] = rgba[..., :3]
    a = pygame.surfarray.pixels_alpha(s)
    a[:] = rgba[..., 3]
    del a
    return s


def decode_sixel(data):
    pal = {i: c for i, c in enumerate(DEFAULT16)}
    color = 0
    x = 0
    band = 0
    xs_l, bits_l, col_l, band_l = [], [], [], []
    maxx = 0
    for m in _SIX.finditer(data):
        g = m.groups()
        if g[0] is not None:
            color = int(g[0])
            if g[1] is not None:
                pu, a, b, c = int(g[1]), int(g[2]), int(g[3]), int(g[4])
                if pu == 2:
                    pal[color] = (min(255, a * 255 // 100), min(255, b * 255 // 100), min(255, c * 255 // 100))
                elif pu == 1:
                    r, gg, bb = colorsys.hls_to_rgb(((a - 120) % 360) / 360.0, b / 100.0, c / 100.0)
                    pal[color] = (int(r * 255), int(gg * 255), int(bb * 255))
        elif g[5] is not None:
            n = min(int(g[5]), MAX_DIM)
            v = ord(g[6]) - 63
            if v:
                xs_l.append(np.arange(x, x + n))
                bits_l.append(np.full(n, v, np.int16))
                col_l.append(np.full(n, color, np.int16))
                band_l.append(np.full(n, band, np.int16))
            x += n
        elif g[7] is not None:
            run = g[7]
            v = np.frombuffer(run.encode('latin-1'), np.uint8).astype(np.int16) - 63
            nz = np.nonzero(v)[0]
            if len(nz):
                xs_l.append(nz + x)
                bits_l.append(v[nz])
                col_l.append(np.full(len(nz), color, np.int16))
                band_l.append(np.full(len(nz), band, np.int16))
            x += len(run)
        elif g[8] is not None:
            maxx = max(maxx, x)
            x = 0
        elif g[9] is not None:
            maxx = max(maxx, x)
            x = 0
            band += 1
        if x > MAX_DIM or band * 6 > MAX_DIM:
            break
    maxx = max(maxx, x)
    if not xs_l or maxx == 0:
        return None
    xs = np.concatenate(xs_l)
    bits = np.concatenate(bits_l)
    cols = np.concatenate(col_l)
    bands = np.concatenate(band_l)
    h = int(bands.max() + 1) * 6
    w = int(min(maxx, MAX_DIM))
    canvas = np.full((w, h), -1, np.int32)
    keep = xs < w
    xs, bits, cols, bands = xs[keep], bits[keep], cols[keep], bands[keep]
    for b in range(6):
        mk = (bits >> b) & 1 == 1
        canvas[xs[mk], bands[mk] * 6 + b] = cols[mk]
    # trim empty bottom rows
    used = np.nonzero((canvas >= 0).any(axis=0))[0]
    if len(used):
        canvas = canvas[:, :used[-1] + 1]
    lut = np.zeros((max(pal) + 2, 4), np.uint8)
    for k, c in pal.items():
        lut[k] = (c[0], c[1], c[2], 255)
    rgba = lut[np.clip(canvas, 0, len(lut) - 2)]
    rgba[canvas < 0] = 0
    return _surface_from_rgba(rgba)


def _load_bytes(raw, hint='img.png'):
    try:
        s = pygame.image.load(io.BytesIO(raw), hint)
        return s.convert_alpha() if pygame.display.get_surface() else s
    except Exception:
        return None


def decode_iterm(arg):
    """'name=..;width=..;height=..;inline=1:BASE64' -> (surf, cols, rows)"""
    head, _, b64 = arg.partition(':')
    opts = {}
    for kv in head.split(';'):
        k, _, v = kv.partition('=')
        opts[k] = v
    if opts.get('inline', '0') != '1':
        return None
    try:
        raw = base64.b64decode(b64, validate=False)
    except Exception:
        return None
    name = base64.b64decode(opts['name']).decode('utf-8', 'ignore') if opts.get('name') else 'img.png'
    surf = _load_bytes(raw, name)
    if surf is None:
        return None

    def cells(v):
        if v and v.isdigit():
            return int(v)
        return None
    cols, rows = cells(opts.get('width')), cells(opts.get('height'))
    for key, idx in (('width', 0), ('height', 1)):
        v = opts.get(key, '')
        if v.endswith('px') and v[:-2].isdigit():
            size = list(surf.get_size())
            k = int(v[:-2]) / max(1, size[idx])
            surf = pygame.transform.smoothscale(surf, (max(1, int(size[0] * k)), max(1, int(size[1] * k))))
    return surf, cols, rows


def kitty_command(screen, body):
    ctrl, _, payload = body.partition(';')
    p = {}
    for kv in ctrl.split(','):
        k, _, v = kv.partition('=')
        if k:
            p[k] = v
    # chunked transmission
    if screen._kitty_chunks is not None:
        base, parts = screen._kitty_chunks
        parts.append(payload)
        if p.get('m', '0') == '1':
            return
        screen._kitty_chunks = None
        p, payload = base, ''.join(parts)
    elif p.get('m') == '1':
        screen._kitty_chunks = (p, [payload])
        return
    a = p.get('a', 't')
    iid = int(p['i']) if p.get('i', '').isdigit() else None
    quiet = p.get('q', '0')

    def reply(msg='OK'):
        if iid is not None and quiet == '0' or (quiet == '1' and msg != 'OK' and iid is not None):
            screen.replies.append('\x1b_Gi=%d;%s\x1b\\' % (iid, msg))

    if a == 'q':
        reply('OK')
        return
    if a == 'd':
        what = p.get('d', 'a')
        if what in ('i', 'I') and iid is not None:
            screen.images = [im for im in screen.images if im.get('kid') != iid]
            screen.kitty_store.pop(iid, None)
        else:
            screen.images = [im for im in screen.images if 'kid' not in im]
        screen.full_dirty = True
        return
    surf = None
    if a in ('t', 'T'):
        try:
            raw = base64.b64decode(payload)
            if p.get('t', 'd') in ('f', 't', 's'):
                with open(raw.decode('utf-8'), 'rb') as fh:
                    raw = fh.read()
            if p.get('o') == 'z':
                raw = zlib.decompress(raw)
        except Exception:
            reply('EINVAL:bad payload')
            return
        f = p.get('f', '32')
        if f == '100':
            surf = _load_bytes(raw)
        else:
            w, h = int(p.get('s', 0) or 0), int(p.get('v', 0) or 0)
            ch = 4 if f == '32' else 3
            if w * h * ch != len(raw) or w <= 0:
                reply('EINVAL:bad size')
                return
            arr = np.frombuffer(raw, np.uint8).reshape(h, w, ch).transpose(1, 0, 2)
            if ch == 3:
                arr = np.concatenate([arr, np.full((w, h, 1), 255, np.uint8)], 2)
            surf = _surface_from_rgba(np.ascontiguousarray(arr))
        if surf is None:
            reply('EINVAL:cannot decode')
            return
        if iid is not None:
            screen.kitty_store[iid] = surf
            if len(screen.kitty_store) > 64:
                screen.kitty_store.pop(next(iter(screen.kitty_store)))
        if a == 't':
            reply('OK')
            return
    elif a == 'p':
        surf = screen.kitty_store.get(iid)
        if surf is None:
            reply('ENOENT:no such image')
            return
    if surf is None:
        return
    cols = int(p['c']) if p.get('c', '').isdigit() else None
    rows = int(p['r']) if p.get('r', '').isdigit() else None
    sx = screen.cx
    screen.place_image(surf, cols, rows, move_cursor=False)
    img = screen.images[-1]
    if iid is not None:
        img['kid'] = iid
    if p.get('C', '0') != '1':
        # kitty: cursor ends right of the image on its last row
        for _ in range(img['rows'] - 1):
            screen._linefeed()
        screen.cx = min(screen.cols - 1, sx + img['cols'])
    reply('OK')


# ---------------------------------------------------------------------------- encoders (for imgcat)
def encode_sixel(surf, max_colors=255):
    """surface -> sixel string (median-cut-ish via uniform quantization)"""
    w, h = surf.get_size()
    rgb = pygame.surfarray.array3d(surf).astype(np.int32)
    try:
        alpha = pygame.surfarray.array_alpha(surf)
    except Exception:
        alpha = np.full((w, h), 255, np.uint8)
    q = (rgb[..., 0] // 43) * 36 + (rgb[..., 1] // 43) * 6 + (rgb[..., 2] // 43)  # 6x6x6 cube
    q[alpha < 128] = -1
    out = ['\x1bPq', '"1;1;%d;%d' % (w, h)]
    used = np.unique(q[q >= 0])
    for c in used:
        r, g, b = (c // 36) * 43 + 21, ((c // 6) % 6) * 43 + 21, (c % 6) * 43 + 21
        out.append('#%d;2;%d;%d;%d' % (c, r * 100 // 255, g * 100 // 255, b * 100 // 255))
    for y0 in range(0, h, 6):
        band = q[:, y0:y0 + 6]
        colors = np.unique(band[band >= 0])
        for ci, c in enumerate(colors):
            bits = np.zeros(w, np.int32)
            for k in range(band.shape[1]):
                bits |= ((band[:, k] == c).astype(np.int32) << k)
            chars = (bits + 63).astype(np.uint8).tobytes().decode('latin-1')
            # run-length encode
            enc = re.sub(r'(.)\1{3,}', lambda m: '!%d%s' % (len(m.group()), m.group(1)), chars)
            out.append('#%d%s%s' % (c, enc, '$' if ci < len(colors) - 1 else ''))
        out.append('-')
    out.append('\x1b\\')
    return ''.join(out)


def encode_kitty(png_bytes, cols=None, rows=None):
    b64 = base64.b64encode(png_bytes).decode('ascii')
    chunks = [b64[i:i + 4096] for i in range(0, len(b64), 4096)] or ['']
    out = []
    for i, ch in enumerate(chunks):
        more = 1 if i < len(chunks) - 1 else 0
        if i == 0:
            extra = ''.join([',c=%d' % cols if cols else '', ',r=%d' % rows if rows else ''])
            out.append('\x1b_Ga=T,f=100,q=2%s,m=%d;%s\x1b\\' % (extra, more, ch))
        else:
            out.append('\x1b_Gm=%d;%s\x1b\\' % (more, ch))
    return ''.join(out)


def encode_iterm(raw, name='image.png', width=None):
    n = base64.b64encode(name.encode()).decode()
    w = ';width=%s' % width if width else ''
    return '\x1b]1337;File=name=%s;size=%d;inline=1%s:%s\x07' % (n, len(raw), w, base64.b64encode(raw).decode())
