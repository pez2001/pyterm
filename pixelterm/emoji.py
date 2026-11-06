"""Built-in pixel-art emoji - colored, many of them animated.

Every emoji is drawn procedurally at the cell size, so they stay crisp with
any font. Animation frames are driven by a global 8 fps clock; animated
emoji re-render only the rows they are on.
"""
from __future__ import annotations

import math

import pygame

YEL = (255, 204, 40)
YEL_D = (200, 130, 0)
DARK = (60, 30, 10)
WHITE = (255, 255, 255)
RED = (230, 40, 60)
PINK = (255, 120, 140)
BLUE = (90, 170, 255)
FRAMES = 8

# name -> (base face?, animated?)
EMOJI = {
    '😀': 'grin', '😃': 'grin_big', '😄': 'grin_eyes', '😁': 'beam', '😆': 'laugh', '😅': 'sweat', '😂': 'joy',
    '🤣': 'rofl', '😊': 'blush', '😇': 'halo', '🙂': 'smile', '🙃': 'upside', '😉': 'wink', '😍': 'hearts',
    '😘': 'kiss', '😎': 'cool', '🤔': 'think', '😐': 'neutral', '😑': 'flat', '😮': 'wow', '😴': 'sleep',
    '😢': 'cry', '😭': 'sob', '😡': 'angry', '😠': 'angry', '🥳': 'party', '🤩': 'stars', '😱': 'scream',
    '😋': 'yum', '😜': 'tongue', '🤪': 'zany', '🥺': 'plead', '😬': 'grimace', '🤓': 'nerd', '😈': 'devil',
    '👻': 'ghost', '💀': 'skull', '❤': 'heart', '💖': 'heart', '⭐': 'star', '🌟': 'star', '✨': 'sparkles',
    '🔥': 'fire', '👍': 'thumbs', '🎉': 'tada', '🚀': 'rocket', '💩': 'poo', '🍕': 'pizza', '🐍': 'snake',
}
ANIMATED = {'joy', 'rofl', 'halo', 'wink', 'hearts', 'kiss', 'cool', 'sleep', 'cry', 'sob', 'angry', 'party',
            'stars', 'scream', 'tongue', 'zany', 'ghost', 'heart', 'star', 'sparkles', 'fire', 'tada', 'rocket',
            'laugh', 'think', 'devil', 'snake'}
_cache = {}


def is_emoji(c):
    return c in EMOJI


def is_animated(c):
    return EMOJI.get(c) in ANIMATED


def surface(c, w, h, frame=0):
    """colored emoji surface of size (w, h) for animation frame `frame`"""
    name = EMOJI.get(c)
    if name is None:
        return None
    f = frame % FRAMES if name in ANIMATED else 0
    key = (c, w, h, f)
    s = _cache.get(key)
    if s is None:
        if len(_cache) > 4000:
            _cache.clear()
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        try:
            _draw(s, name, w, h, f)
        except Exception as e:  # never let a drawing bug kill the renderer
            print('[pixelterm] emoji %s: %s' % (name, e))
            pygame.draw.circle(s, YEL, (w // 2, h // 2), max(2, min(w, h) // 2 - 1))
        _cache[key] = s
    return s


def silhouette(c, w, h):
    """white mask version (for particle effects that need glyph pixels)"""
    s = surface(c, w, h, 0)
    if s is None:
        return None
    m = s.copy()
    m.fill((255, 255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
    return m


# ---------------------------------------------------------------------------- drawing
def _face(s, cx, cy, r, col=YEL, edge=YEL_D):
    pygame.draw.circle(s, edge, (cx, cy), r)
    pygame.draw.circle(s, col, (cx, cy), max(1, r - max(1, r // 7)))
    if r >= 5:
        pygame.draw.circle(s, (255, 235, 140), (cx - r // 3, cy - r // 3), max(1, r // 4))


def _eyes(s, cx, cy, r, kind='dot', f=0):
    ex = max(1, int(r * 0.38))
    ey = cy - max(1, int(r * 0.22))
    e = max(1, int(r * 0.17))
    for side in (-1, 1):
        x = cx + side * ex
        if kind == 'dot':
            s.fill(DARK, (x - e // 2, ey - e // 2 - (r > 7), e, e + (r > 7)))
        elif kind == 'closed':      # ^ ^
            pygame.draw.lines(s, DARK, False, [(x - e, ey + e // 2), (x, ey - e // 2), (x + e, ey + e // 2)], max(1, r // 8))
        elif kind == 'line':
            s.fill(DARK, (x - e, ey, 2 * e, max(1, r // 8)))
        elif kind == 'heart':
            k = 1 + 0.25 * math.sin(f / FRAMES * 2 * math.pi)
            _heart(s, x, ey, max(2, int(e * 1.6 * k)), RED)
        elif kind == 'star':
            _star(s, x, ey, max(2, int(e * 1.7 * (1 + 0.3 * math.sin(f / FRAMES * 2 * math.pi + side)))), (255, 230, 60))
        elif kind == 'big':
            pygame.draw.circle(s, WHITE, (x, ey), max(2, e))
            s.fill(DARK, (x - max(1, e // 2) // 2, ey, max(1, e // 2), max(1, e // 2)))


def _mouth(s, cx, cy, r, kind='smile', f=0):
    w = max(2, int(r * 1.1))
    my = cy + max(1, int(r * 0.25))
    lw = max(1, r // 8)
    if kind == 'smile':
        pygame.draw.arc(s, DARK, (cx - w // 2, my - w // 2, w, w // 2 + 1), math.pi, 2 * math.pi, lw)
    elif kind == 'grin':
        pts = [(cx - w // 2, my - 1), (cx + w // 2, my - 1), (cx, my + max(2, r // 2))]
        pygame.draw.polygon(s, DARK, pts)
        if r >= 6:
            s.fill(WHITE, (cx - w // 2 + 1, my - 1, w - 2, max(1, r // 6)))
    elif kind == 'open':
        o = max(1, int(r * (0.35 + 0.15 * math.sin(f / FRAMES * 2 * math.pi))))
        pygame.draw.ellipse(s, DARK, (cx - o // 2 - 1, my - o // 2, o + 2, o + 1))
    elif kind == 'flat':
        s.fill(DARK, (cx - w // 3, my, 2 * w // 3, lw))
    elif kind == 'sad':
        pygame.draw.arc(s, DARK, (cx - w // 3, my, 2 * w // 3, w // 2), 0, math.pi, lw)
    elif kind == 'tongue':
        pygame.draw.arc(s, DARK, (cx - w // 2, my - w // 2, w, w // 2 + 1), math.pi, 2 * math.pi, lw)
        t = 1 + (f // 2) % 2
        s.fill(PINK, (cx, my, max(2, r // 3), max(1, r // 4) + t))
    elif kind == 'kiss':
        s.fill(DARK, (cx, my - 1, max(1, r // 6), max(2, r // 3)))
    elif kind == 'teeth':
        s.fill(WHITE, (cx - w // 2, my - 1, w, max(2, r // 3)))
        pygame.draw.rect(s, DARK, (cx - w // 2, my - 1, w, max(2, r // 3)), 1)


def _heart(s, cx, cy, r, col):
    if r < 2:
        s.fill(col, (cx - 1, cy - 1, 2, 2))
        return
    pygame.draw.circle(s, col, (cx - r // 2, cy - r // 4), max(1, r // 2))
    pygame.draw.circle(s, col, (cx + r // 2, cy - r // 4), max(1, r // 2))
    pygame.draw.polygon(s, col, [(cx - r, cy - r // 6), (cx + r, cy - r // 6), (cx, cy + r)])


def _star(s, cx, cy, r, col):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    pygame.draw.polygon(s, col, pts)


def _tear(s, x, y, r, f, speed=1.0):
    k = (f * speed / FRAMES) % 1.0
    yy = int(y + k * r * 1.2)
    t = max(1, r // 5)
    pygame.draw.circle(s, BLUE, (x, yy), t)
    s.fill(BLUE, (x - t // 2, yy - t * 2, max(1, t), t * 2))


def _draw(s, name, w, h, f):
    S = min(w, h)
    cx, cy = w // 2, h // 2
    r = max(3, S // 2 - 1)
    ph = f / FRAMES * 2 * math.pi
    if name == 'heart':
        k = 1 + 0.18 * max(0, math.sin(ph * 2))
        _heart(s, cx, cy, int(r * 0.8 * k), RED)
        return
    if name in ('star',):
        _star(s, cx, cy, int(r * (0.9 + 0.12 * math.sin(ph))), (255, 220, 50))
        if f % 4 == 0:
            s.fill(WHITE, (cx + r // 2, cy - r // 2, 1, 1))
        return
    if name == 'sparkles':
        for i, (dx, dy, sz) in enumerate(((-r // 2, -r // 3, r // 2), (r // 2, r // 4, r // 3), (-r // 4, r // 2, r // 4))):
            k = 0.5 + 0.5 * math.sin(ph + i * 2)
            _star(s, cx + dx, cy + dy, max(1, int(sz * (0.5 + k))), (255, 240, 120))
        return
    if name == 'fire':
        for i, col in enumerate(((255, 80, 0), (255, 170, 0), (255, 240, 120))):
            sway = int(math.sin(ph + i) * r * 0.12)
            rad = int(r * (0.9 - i * 0.28))
            pygame.draw.circle(s, col, (cx + sway, cy + r // 3), max(1, rad))
            pygame.draw.polygon(s, col, [(cx - rad + sway, cy + r // 3), (cx + rad + sway, cy + r // 3),
                                         (cx + sway * 2, cy + r // 3 - int(rad * (2.0 + 0.3 * math.sin(ph * 2 + i))))])
        return
    if name == 'thumbs':
        s.fill(YEL, (cx - r // 2, cy - r // 6, r, r))
        s.fill(YEL, (cx - r // 6, cy - r, r // 2, r))
        pygame.draw.rect(s, YEL_D, (cx - r // 2, cy - r // 6, r, r), 1)
        s.fill((40, 90, 220), (cx - r, cy - r // 6, r // 2, r))
        return
    if name == 'tada':
        pygame.draw.polygon(s, (255, 190, 40), [(cx - r, cy + r), (cx - r // 3, cy - r // 3), (cx + r // 3, cy + r // 3)])
        for i, col in enumerate(((255, 60, 90), (60, 200, 255), (120, 255, 90), (255, 230, 60))):
            a = -math.pi / 4 + (i - 1.5) * 0.45
            d = r * (0.5 + 0.5 * ((f / FRAMES + i * 0.25) % 1))
            s.fill(col, (cx - r // 3 + math.cos(a) * d, cy - r // 3 + math.sin(a) * d, max(1, r // 4), max(1, r // 4)))
        return
    if name == 'rocket':
        dy = int(math.sin(ph) * 1.5)
        pygame.draw.ellipse(s, (230, 230, 240), (cx - r // 3, cy - r + dy, 2 * r // 3, int(r * 1.5)))
        s.fill(RED, (cx - r // 2, cy + r // 3 + dy, r, r // 3))
        pygame.draw.circle(s, BLUE, (cx, cy - r // 3 + dy), max(1, r // 5))
        fl = (255, 200, 40) if f % 2 else (255, 100, 0)
        pygame.draw.polygon(s, fl, [(cx - r // 4, cy + 2 * r // 3 + dy), (cx + r // 4, cy + 2 * r // 3 + dy),
                                    (cx, cy + r + (f % 3) + dy)])
        return
    if name == 'ghost':
        dy = int(math.sin(ph) * r * 0.15)
        pygame.draw.circle(s, (240, 240, 255), (cx, cy - r // 4 + dy), int(r * 0.8))
        s.fill((240, 240, 255), (cx - int(r * 0.8), cy - r // 4 + dy, int(r * 1.6), int(r * 0.9)))
        for i in range(3):
            pygame.draw.circle(s, (0, 0, 0, 0), (cx - int(r * 0.55) + i * int(r * 0.55), cy + int(r * 0.7) + dy), max(1, r // 5))
        _eyes(s, cx, cy - r // 6 + dy, r, 'dot')
        _mouth(s, cx, cy - r // 6 + dy, r, 'open', f)
        return
    if name == 'skull':
        pygame.draw.circle(s, (235, 235, 225), (cx, cy - r // 6), int(r * 0.85))
        s.fill((235, 235, 225), (cx - r // 2, cy + r // 3, r, r // 2))
        for side in (-1, 1):
            pygame.draw.circle(s, (20, 20, 20), (cx + side * r // 3, cy - r // 6), max(1, r // 4))
        s.fill((20, 20, 20), (cx - 1, cy + r // 6, 2, max(1, r // 5)))
        return
    if name == 'poo':
        col = (130, 80, 40)
        for i, rr in enumerate((0.85, 0.65, 0.42)):
            pygame.draw.ellipse(s, col, (cx - int(r * rr), cy + r // 2 - int(r * 0.45) * (i + 1), int(2 * r * rr), int(r * 0.6)))
        _eyes(s, cx, cy + r // 6, r, 'big')
        return
    if name == 'pizza':
        pygame.draw.polygon(s, (250, 200, 80), [(cx - r, cy - r // 2), (cx + r, cy - r // 2), (cx, cy + r)])
        s.fill((200, 120, 40), (cx - r, cy - r // 2 - 1, 2 * r, max(2, r // 4)))
        for dx, dy in ((-r // 3, 0), (r // 4, -r // 8), (0, r // 3)):
            pygame.draw.circle(s, (210, 40, 30), (cx + dx, cy + dy), max(1, r // 6))
        return
    if name == 'snake':
        pts = [(cx - r + i * (2 * r) / 8, cy + math.sin(ph + i * 0.9) * r * 0.35) for i in range(9)]
        pygame.draw.lines(s, (60, 200, 80), False, pts, max(2, r // 3))
        pygame.draw.circle(s, (60, 200, 80), (int(pts[-1][0]), int(pts[-1][1])), max(2, r // 3))
        s.fill(DARK, (int(pts[-1][0]), int(pts[-1][1]) - 1, 1, 1))
        if f % 4 < 2:
            s.fill(RED, (int(pts[-1][0]) + max(2, r // 3), int(pts[-1][1]), max(1, r // 4), 1))
        return
    # ---------------------------------------------------------------- faces
    shake = 0
    if name in ('angry', 'rofl', 'scream'):
        shake = (1 if f % 2 else -1) if name != 'rofl' else 0
    col, edge = YEL, YEL_D
    if name == 'angry':
        col, edge = (240, 80, 50), (160, 30, 20)
    if name == 'devil':
        col, edge = (170, 80, 220), (100, 40, 140)
    if name == 'upside':
        tmp = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        tmp.fill((0, 0, 0, 0))
        _face(tmp, cx, cy, r)
        _eyes(tmp, cx, cy, r, 'dot')
        _mouth(tmp, cx, cy, r, 'smile')
        s.blit(pygame.transform.flip(tmp, False, True), (0, 0))
        return
    if name == 'rofl':
        tmp = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        tmp.fill((0, 0, 0, 0))
        _face(tmp, cx, cy, r)
        _eyes(tmp, cx, cy, r, 'closed')
        _mouth(tmp, cx, cy, r, 'grin')
        _tear(tmp, cx - int(r * 0.6), cy - r // 6, r, f, 2)
        _tear(tmp, cx + int(r * 0.6), cy - r // 6, r, f + 4, 2)
        rot = pygame.transform.rotate(tmp, 20 * math.sin(ph))
        s.blit(rot, rot.get_rect(center=(cx, cy)))
        return
    cx += shake
    _face(s, cx, cy, r, col, edge)
    if name == 'devil':
        for side in (-1, 1):
            pygame.draw.polygon(s, edge, [(cx + side * r // 2, cy - r + 2), (cx + side * r, cy - r - 1 - (f % 2)),
                                          (cx + side * r * 0.9, cy - r // 2)])
    eyes, mouth = {
        'grin': ('dot', 'grin'), 'grin_big': ('big', 'grin'), 'grin_eyes': ('closed', 'grin'), 'beam': ('closed', 'teeth'),
        'laugh': ('closed', 'open'), 'sweat': ('closed', 'grin'), 'joy': ('closed', 'grin'), 'blush': ('closed', 'smile'),
        'halo': ('closed', 'smile'), 'smile': ('dot', 'smile'), 'wink': ('dot', 'smile'), 'hearts': ('heart', 'grin'),
        'kiss': ('closed', 'kiss'), 'cool': ('dot', 'smile'), 'think': ('dot', 'flat'), 'neutral': ('dot', 'flat'),
        'flat': ('line', 'flat'), 'wow': ('big', 'open'), 'sleep': ('line', 'open'), 'cry': ('dot', 'sad'),
        'sob': ('closed', 'sad'), 'angry': ('dot', 'sad'), 'party': ('closed', 'grin'), 'stars': ('star', 'grin'),
        'scream': ('big', 'open'), 'yum': ('closed', 'tongue'), 'tongue': ('closed', 'tongue'), 'zany': ('big', 'tongue'),
        'plead': ('big', 'sad'), 'grimace': ('dot', 'teeth'), 'nerd': ('big', 'teeth'), 'devil': ('dot', 'grin'),
    }.get(name, ('dot', 'smile'))
    if name == 'wink' and (f % 8) in (2, 3, 4):
        # animated wink: right eye closes
        _eyes(s, cx, cy, r, 'dot')
        ex = cx + max(1, int(r * 0.38))
        ey = cy - max(1, int(r * 0.22))
        e = max(1, int(r * 0.17))
        s.fill(col, (ex - e, ey - e, 2 * e + 1, 2 * e + 1))
        s.fill(DARK, (ex - e, ey, 2 * e, max(1, r // 8)))
    elif name == 'cool':
        gy = cy - max(1, int(r * 0.25))
        s.fill((20, 20, 30), (cx - int(r * 0.75), gy - max(1, r // 6), int(r * 1.5), max(2, r // 3)))
        if f % 8 < 2:   # glint
            s.fill(WHITE, (cx - int(r * 0.6) + (f % 8) * r // 3, gy - max(1, r // 6), 1, 1))
    else:
        _eyes(s, cx, cy, r, eyes, f)
    if name == 'zany':
        e = max(1, int(r * 0.17))
        s.fill(col, (cx + int(r * 0.38) - e, cy - int(r * 0.22) - e, 2 * e + 1, 2 * e + 1))
        s.fill(DARK, (cx + int(r * 0.38) - e // 2, cy - int(r * 0.22) + (f % 2), e, e))
    _mouth(s, cx, cy, r, mouth, f)
    if name == 'think':
        s.fill(YEL_D, (cx - r // 2, cy + r // 2 - (f // 4), max(2, r // 3), max(2, r // 3)))
    if name in ('blush', 'hearts', 'kiss', 'party', 'plead'):
        for side in (-1, 1):
            s.fill(PINK, (cx + side * int(r * 0.55) - 1, cy + max(1, r // 8), max(1, r // 4), max(1, r // 6)))
    if name == 'sweat':
        _tear(s, cx + int(r * 0.7), cy - int(r * 0.7), r, 0)
    if name in ('joy', 'cry', 'sob'):
        _tear(s, cx - int(r * 0.4), cy, r, f, 1.0 if name != 'sob' else 2.0)
        if name != 'cry':
            _tear(s, cx + int(r * 0.4), cy, r, f + 3, 1.0 if name != 'sob' else 2.0)
    if name == 'halo':
        a = int(r * 0.7)
        pygame.draw.ellipse(s, (255, 255, 160) if f % 4 < 2 else (255, 240, 90), (cx - a, 0, 2 * a, max(2, r // 3)), max(1, r // 6))
    if name == 'kiss' and r >= 4:
        k = (f / FRAMES)
        _heart(s, cx + int(r * 0.8), int(cy - k * r), max(1, r // 4), RED)
    if name == 'sleep':
        k = (f / FRAMES)
        z = max(1, r // 3)
        x, y = cx + int(r * 0.6 + k * r * 0.3), int(cy - r * 0.4 - k * r * 0.6)
        s.fill((80, 140, 255), (x, y, z, 1))
        s.fill((80, 140, 255), (x, y + z, z, 1))
        s.fill((80, 140, 255), (x + z // 2, y + z // 2, 1, 1))
    if name == 'angry':
        for side in (-1, 1):
            pygame.draw.line(s, DARK, (cx + side * int(r * 0.15), cy - int(r * 0.35)),
                             (cx + side * int(r * 0.6), cy - int(r * 0.55)), max(1, r // 8))
        if f % 4 < 2:
            pygame.draw.circle(s, (240, 240, 240), (cx + r, cy - r + 1), max(1, r // 4))
    if name == 'party':
        pygame.draw.polygon(s, (60, 160, 255), [(cx - r // 3, cy - r + 1), (cx + r // 3, cy - r + 1), (cx + r // 6, cy - r - r // 2)])
        cols = ((255, 60, 90), (120, 255, 90), (255, 230, 60))
        for i in range(3):
            s.fill(cols[(i + f) % 3], (cx - r + i * r, cy - r + ((f + i * 3) % FRAMES) * r // 4 % (2 * r), 1, 1))
    if name == 'nerd':
        for side in (-1, 1):
            pygame.draw.circle(s, DARK, (cx + side * int(r * 0.38), cy - int(r * 0.22)), max(2, int(r * 0.3)), 1)
    if name == 'scream':
        for side in (-1, 1):
            s.fill(YEL_D, (cx + side * r - (side > 0), cy, 1, max(2, r // 2)))
