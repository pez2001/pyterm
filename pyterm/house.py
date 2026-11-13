"""dollhouse - a little person lives in a cutaway house on your clock (theme: computerpeople).

Drawn as chunky pixel art on a small logical canvas that is scaled up, so the resident, the pets and
the furniture stay the same cute size on every window.

The resident (big head, rosy cheeks, blinks, pajamas at night) lives by the real clock:
  sleeps, takes a bath (and sings), cooks, eats, drinks coffee, watches tv, plays the piano, dances to
  the record player, does jumping jacks, vacuums, waters the plant and the garden, reads in the
  armchair, feeds the pets, plays fetch with the dog, looks at the stars, comes to the glass and waves.
The dog lives in the yard (wanders, naps in its house, fetches, barks at the doorbell, howls at the
full moon); the cat lives inside (naps on the sofa, sits in the window and follows your cursor, begs
in the kitchen, jumps on the desk while you type).

Reactions to the terminal (pyterm.signals):
  typing            runs to the computer and types - the monitor shows your last letters; the cat may
                    jump on the desk; very fast typing makes them sweat and the computer smoke
  Enter             a little nod / hop
  command ok        a quick thumbs-up now and then; after a long one a party: jumping, confetti,
                    the dog spins
  command failed    sad face and a tear - or a real fright (exit code > 1): hands up, the cat puffs
                    up, the dog barks
  lots of output    stares at the scrolling monitor
  bell              the doorbell: the dog barks, the mailbox flag goes up, the resident fetches the
                    letter and is delighted
  nothing for long  yawns, dozes off at the desk, then goes back to its own life

bg_params: {dollhouse: {hour: null, shirt: '#e04848', hair: '#6e411e', pets: true, busy: 1.0}}
  hour   fix the time of day (0..24) instead of the real clock      busy   how often they change activity
"""
from __future__ import annotations

import math
import random
import time

import pygame

from . import signals
from .backgrounds import Background
from .scenes import bubble, daylight, glow, gradient, sky_colors, sprite
from .themes import hex2rgb
from .weather import _F, _lerp, moon_phase, tiny_text

KEY = (255, 0, 255)                      # transparent color of the static house layer (windows show the sky)

# ---------------------------------------------------------------------------- the resident
HEAD = ["..HHHHHH..", ".HHHHHHHH.", ".HHSSSSHH.", ".HSSSSSSH."]
FACES = {                                # eyes row, cheeks row, mouth row
    'normal': (".SSeSSeSS.", ".ScSSSScS.", "..SSmmSS.."),
    'blink': (".SSlSSlSS.", ".ScSSSScS.", "..SSmmSS.."),
    'happy': (".SSeSSeSS.", ".SCSSSSCS.", "..SmmmmS.."),
    'wow': (".SwSSSSwS.", ".SeSSSSeS.", "..SSooSS.."),
    'sad': (".SSeSSeSS.", ".StSSSScS.", "..SmSSmS.."),
    'sleep': (".SSlSSlSS.", ".ScSSSScS.", "..SSSmSS.."),
}
BODIES = {
    'stand': ["..TTTTTT..", ".sTTTTTTs.", ".sTTTTTTs.", "..PPPPPP..", "..PP..PP..", "..PP..PP..", "..KK..KK.."],
    'walk1': ["..TTTTTT..", ".sTTTTTTs.", "..TTTTTTs.", "..PPPPPP..", "..PP..PP..", "..PP...PP.", "..KK...KK."],
    'walk2': ["..TTTTTT..", ".sTTTTTTs.", ".sTTTTTT..", "..PPPPPP..", "..PP..PP..", ".PP...PP..", ".KK...KK.."],
    'up': ["s.TTTTTT.s", "sTTTTTTTTs", "..TTTTTT..", "..PPPPPP..", "..PP..PP..", "..PP..PP..", "..KK..KK.."],
    'jack': ["s.TTTTTT.s", "sTTTTTTTTs", "..TTTTTT..", "..PPPPPP..", ".PP....PP.", "PP......PP", "KK......KK"],
    'wave1': ["..TTTTTT.s", ".sTTTTTTTs", ".sTTTTTT..", "..PPPPPP..", "..PP..PP..", "..PP..PP..", "..KK..KK.."],
    'wave2': ["..TTTTTTs.", ".sTTTTTTT.", ".sTTTTTT..", "..PPPPPP..", "..PP..PP..", "..PP..PP..", "..KK..KK.."],
    'dance1': ["s.TTTTTT..", "sTTTTTTTs.", "..TTTTTTs.", "..PPPPPP..", "..PP..PP..", ".PP...PP..", ".KK...KK.."],
    'dance2': ["..TTTTTT.s", ".sTTTTTTTs", ".sTTTTTT..", "..PPPPPP..", "..PP..PP..", "..PP...PP.", "..KK...KK."],
    'carry': ["..TTTTTT..", "..TTTTTTss", "..TTTTTT..", "..PPPPPP..", "..PP..PP..", "..PP..PP..", "..KK..KK.."],
    'sit': ["..TTTTTT..", ".sTTTTTTs.", "..TTTTTT..", "..PPPPPPPP", "......PPKK"],
    'type1': ["..TTTTTT..", "..TTTTTTss", "..TTTTTT..", "..PPPPPPPP", "......PPKK"],
    'type2': ["..TTTTTT.s", "..TTTTTTs.", "..TTTTTT..", "..PPPPPPPP", "......PPKK"],
    'head': [],
}
_people = {}


def person(pose, face, flip, shirt, hair):
    key = (pose, face, flip, shirt, hair)
    s = _people.get(key)
    if s is None:
        pal = {'H': hair, 'S': (255, 214, 178), 's': (255, 214, 178), 'e': (40, 30, 45), 'l': (205, 150, 120),
               'c': (255, 170, 160), 'C': (255, 120, 130), 'm': (200, 70, 85), 'o': (120, 30, 40), 'w': (255, 255, 255),
               't': (90, 170, 255), 'T': shirt, 'P': (60, 80, 170), 'K': (60, 40, 30)}
        s = sprite(HEAD + list(FACES[face]) + BODIES[pose], pal)
        if flip:
            s = pygame.transform.flip(s, True, False)
        _people[key] = s
    return s


DOG = {
    'walk1': ["........dd.", ".......dDdd", "t......dedn", "tddddddddd.", ".ddddddddd.", ".d.d...d.d."],
    'walk2': ["t.......dd.", "t......dDdd", ".t.....dedn", ".dddddddddr", ".ddddddddd.", "..dd..dd..."],
    'sit': ["....dd.", "...dDdd", "...dedn", "..dddd.", ".ddddd.", "tddddd."],
    'sleep': [".ddddddDd..", "tddddddddln"],
    'howl': [".....d.", "....dn.", "...dDe.", "..dddd.", ".ddddd.", "tddddd."],
}
CAT = {
    'sit': [".c...c.", ".ccccc.", ".cgcgc.", ".ccncc.", "..ccc.t", ".ccccct"],
    'walk1': ["c.c.....", "ccc....t", "cgcOcccc", ".ccccccc", ".c.c.c.c"],
    'walk2': ["c.c.....", "ccc...t.", "cgcOcccc", ".ccccccc", "..cc..cc"],
    'sleep': [".c.....", "ccccOc.", "cccccct"],
    'puff': ["c.....c", "cc.c.cc", ".ccccc.", ".cwcwc.", "ccccccc", "ccccccc"],
}
_pets = {}


def pet(table, pose, flip):
    key = (id(table), pose, flip)
    s = _pets.get(key)
    if s is None:
        pal = {'d': (196, 136, 76), 'D': (130, 80, 40), 'e': (30, 20, 20), 'n': (40, 25, 25), 't': (150, 100, 55),
               'r': (230, 90, 110), 'l': (130, 80, 40), 'c': (240, 236, 228), 'O': (236, 150, 70), 'g': (70, 190, 110),
               'w': (255, 255, 255)}
        s = sprite(table[pose], pal)
        if flip:
            s = pygame.transform.flip(s, True, False)
        _pets[key] = s
    return s


class Mover:
    """something that walks along the floors of the house, takes the stairs and uses the door"""

    def __init__(self, x, floor):
        self.x, self.floor, self.face = float(x), floor, 1
        self.path = []
        self.climb = None
        self.walk_t = 0.0

    def go(self, house, floor, x):
        self.path = []
        cur = self.floor
        tf = max(0, floor)
        if cur == -1 and floor != -1:
            self.path.append(('in', house.x0 + 6))
            cur = 0
        while cur != tf:
            d = 1 if tf > cur else -1
            self.path.append(('stairs', cur, d))
            cur += d
        if floor == -1 and self.floor != -1:
            self.path.append(('walk', house.x0 + 5))
            self.path.append(('out', x))
        else:
            self.path.append(('walk', x))

    def step(self, house, dt, speed):
        if not self.path:
            self.walk_t = 0.0
            return False
        st = self.path[0]
        tx = house.stair_x if st[0] == 'stairs' else st[1]
        d = tx - self.x
        if abs(d) > 0.6:
            self.face = 1 if d > 0 else -1
            self.x += max(-speed * dt, min(speed * dt, d))
            self.walk_t += dt
            return True
        self.x = float(tx)
        if st[0] == 'stairs':
            self.climb = (self.climb or 0.0) + dt * speed / 26
            self.walk_t += dt
            if self.climb >= 1:
                self.climb = None
                self.floor = st[1] + st[2]
                self.path.pop(0)
        else:
            self.floor = {'out': -1, 'in': 0}.get(st[0], self.floor)
            self.path.pop(0)
        return True

    def base_y(self, house):
        if self.floor == -1:
            return house.gy
        y = house.floors[self.floor] + house.fh - 2
        if self.climb is not None and self.path and self.path[0][0] == 'stairs':
            y -= self.path[0][2] * self.climb * house.fh
        return y


# ---------------------------------------------------------------------------- the scene
class Dollhouse(Background):
    name = 'dollhouse'
    opaque = True
    #        spot        pose      bubble
    ACTS = {
        'sleep': ('bed', 'bed', None), 'bath': ('bath', 'bath', None), 'cook': ('stove', 'carry', None),
        'eat': ('table', 'sit', '😋'), 'coffee': ('counter', 'carry', None), 'type': ('desk', 'type', None),
        'think': ('desk', 'sit', '🤔'), 'doze': ('desk', 'sit', '😴'), 'tv': ('sofa', 'sit', '😊'),
        'piano': ('piano', 'type', None), 'dance': ('rug', 'dance', None), 'gym': ('rug', 'jack', '😅'),
        'clean': ('rug', 'carry', None), 'water': ('plant', 'carry', None), 'read': ('chair', 'sit', '🤓'),
        'feed': ('bowls', 'carry', '❤'), 'fetch': ('lawn', 'stand', '❤'), 'garden': ('flowers', 'carry', None),
        'mail': ('mailbox', 'carry', '😍'), 'stars': ('lawn', 'stand', '✨'), 'wave': ('rug', 'wave', None),
    }
    LEISURE = ['tv', 'piano', 'dance', 'gym', 'clean', 'water', 'read', 'feed', 'fetch', 'garden', 'wave', 'coffee', 'tv', 'read']

    def _rgb(self, key, default):
        v = self.p(key, None)
        try:
            return tuple(hex2rgb(v)) if v else default
        except Exception:
            return default

    def resize(self, w, h):
        super().resize(w, h)
        self.k = k = max(1, round(h / 168))
        self.lw, self.lh = lw, lh = max(60, -(-w // k)), max(40, -(-h // k))
        self.low = pygame.Surface((lw, lh))
        self.cache = {}
        self.shirt = self._rgb('shirt', (224, 72, 72))
        self.hair = self._rgb('hair', (110, 65, 30))
        self.pets = bool(self.p('pets', True))
        self.busy = max(0.2, float(self.p('busy', 1.0) or 1.0))
        self.gy = gy = lh - 12
        self.fh = fh = 34
        hw = 150
        self.x1 = x1 = lw - 6
        self.x0 = x0 = x1 - hw
        self.hw = hw
        self.floors = [gy - (i + 1) * fh for i in range(3)]
        X = lambda o: x0 + o
        self.stair_x = X(9)
        yard = max(20, x0)
        self.spots = {  # name: (floor, x)
            'stove': (0, X(40)), 'counter': (0, X(53)), 'table': (0, X(90)), 'bowls': (0, X(132)),
            'desk': (1, X(22)), 'plant': (1, X(54)), 'rug': (1, X(72)), 'sofa': (1, X(88)), 'piano': (1, X(131)),
            'bath': (2, X(30)), 'chair': (2, X(78)), 'bed': (2, X(122)),
            'window': (1, X(141)), 'mailbox': (-1, x0 - 14), 'lawn': (-1, int(yard * 0.55)), 'flowers': (-1, int(yard * 0.8)),
        }
        self.tv_x = X(114)
        self.doghouse_x = int(yard * 0.28)
        self.tree_x = int(yard * 0.1)
        if not hasattr(self, 'me'):
            self.me = Mover(self.spots['sofa'][1], 1)
            self.cat = Mover(self.spots['sofa'][1] + 9, 1)
            self.act, self.act_t, self.act_len = 'tv', 0.0, 8.0
            self.last_act = None
            self.fx = []                         # particles: [kind, x, y, vx, vy, life, extra]
            self.react = None                    # [face, emoji or None, seconds, text or None]
            self.hop = 0.0
            self.last_cmd = signals.cmd
            self.last_enter = signals.enter
            self.last_bell = signals.bell
            self.seq = signals.letter_seq
            self.typed = ''
            self.type_t = 0.0                    # seconds of continuous typing
            self.mail = False
            self.plant = 2.0
            self.garden = 1.0
            self.blink = 0.0
            self.cat_state, self.cat_t = 'nap', 0.0
            self.dog_x, self.dog_v, self.dog_state, self.dog_t = float(yard * 0.5), 8.0, 'wander', 0.0
            self.ball = None                     # [x, y, vx, vy]
            self.shoot = None                    # shooting star [x, y, life]
            self.clouds = [[random.uniform(0, lw), random.uniform(4, lh * 0.3), random.uniform(1.5, 4)] for _ in range(4)]
            self.stars = [(random.uniform(0, lw), random.uniform(0, gy * 0.75), random.random()) for _ in range(60)]
            self.fish = 0.0
            self.screen_lines = [random.randint(2, 9) for _ in range(5)]
        else:                                    # window resized: keep everybody, put them back inside
            self.me.x = float(min(max(self.me.x, 6), x1 - 6))
            self.me.path, self.me.climb = [], None
            self.cat.x = float(min(max(self.cat.x, x0 + 6), x1 - 6))
            self.cat.path, self.cat.climb = [], None
            self.dog_x = float(min(self.dog_x, yard - 8))
            self.go(self.act)
        self._build_house()

    # ------------------------------------------------------------ the static house (drawn once)
    def _build_house(self):
        lw, lh, x0, x1, fh, gy = self.lw, self.lh, self.x0, self.x1, self.fh, self.gy
        s = pygame.Surface((lw, lh))
        s.fill(KEY)
        s.set_colorkey(KEY)
        fl = self.floors
        wall = (222, 204, 176)
        papers = [((250, 236, 200), (236, 214, 170)), ((206, 232, 214), (184, 214, 194)), ((214, 220, 246), (194, 200, 232))]
        for i, fy in enumerate(fl):
            base, dot = papers[i]
            s.fill(base, (x0, fy, x1 - x0, fh))
            if i == 0:                                           # kitchen tiles
                for yy in range(fy + 2, fy + fh - 10, 6):
                    for xx in range(x0 + (yy // 6 % 2) * 3, x1, 6):
                        s.fill(dot, (xx, yy, 5, 5))
            elif i == 1:                                         # striped wallpaper
                for xx in range(x0 + 2, x1, 6):
                    s.fill(dot, (xx, fy, 2, fh))
            else:                                                # little hearts / dots
                for yy in range(fy + 3, fy + fh - 4, 7):
                    for xx in range(x0 + 3 + (yy // 7 % 2) * 4, x1 - 2, 8):
                        s.fill(dot, (xx, yy, 2, 1))
                        s.fill(dot, (xx, yy + 1, 1, 1))
            s.fill((150, 100, 60), (x0, fy + fh - 2, x1 - x0, 2))                  # floor boards
            s.fill((120, 78, 46), (x0, fy + fh - 1, x1 - x0, 1))
            s.fill((255, 255, 255), (x0, fy + fh - 4, x1 - x0, 1))                 # skirting
        # outer walls, roof, chimney
        s.fill(wall, (x0 - 3, fl[2], 3, gy - fl[2]))
        s.fill(wall, (x1, fl[2], 3, gy - fl[2]))
        rt = fl[2]
        roof, roof2 = (190, 70, 56), (160, 52, 44)
        self.chim = (x1 - 24, rt - 20)
        s.fill((170, 96, 80), (self.chim[0], self.chim[1], 9, 16))
        s.fill((120, 64, 54), (self.chim[0] - 1, self.chim[1], 11, 2))
        mid = (x0 + x1) // 2
        pygame.draw.polygon(s, roof, [(x0 - 8, rt), (x1 + 8, rt), (mid, rt - 22)])
        for yy in range(rt - 20, rt, 4):                                           # roof tiles
            half = int((rt - yy) / 22 * 0) + int((x1 + 8 - mid) * (1 - (rt - yy) / 22))
            for xx in range(mid - half + (yy // 4 % 2) * 3, mid + half - 2, 6):
                s.fill(roof2, (xx, yy, 5, 1))
        s.fill((120, 40, 34), (x0 - 8, rt - 1, x1 - x0 + 16, 1))
        pygame.draw.circle(s, wall, (mid, rt - 9), 4)                              # attic window
        pygame.draw.circle(s, KEY, (mid, rt - 9), 3)
        s.fill(wall, (mid, rt - 12, 1, 7))
        # windows on the right wall (the sky shows through)
        for i in (1, 2):
            wy = fl[i] + 7
            s.fill((255, 255, 255), (x1 - 12, wy - 1, 10, 15))
            s.fill(KEY, (x1 - 11, wy, 8, 13))
            s.fill((255, 255, 255), (x1 - 8, wy, 1, 13))
            s.fill((255, 255, 255), (x1 - 11, wy + 6, 8, 1))
            s.fill((240, 130, 150) if i == 2 else (250, 200, 90), (x1 - 13, wy - 2, 2, 12))      # curtains
            s.fill((240, 130, 150) if i == 2 else (250, 200, 90), (x1 - 3, wy - 2, 2, 12))
            s.fill((150, 100, 60), (x1 - 13, wy + 14, 12, 1))                                      # sill
        # door (left, ground floor)
        s.fill((150, 90, 50), (x0 - 3, gy - 20, 3, 20))
        s.fill((250, 210, 80), (x0 - 2, gy - 10, 1, 1))
        # stairs: a ladder-like staircase on the left
        for i in range(2):
            fy = fl[i]
            for st in range(8):
                s.fill((176, 120, 72), (self.stair_x - 7 + st, fy + fh - 3 - st * 4, 7, 1))
                s.fill((140, 92, 54), (self.stair_x - 7 + st, fy + fh - 2 - st * 4, 7, 1))
            pygame.draw.line(s, (120, 78, 46), (self.stair_x - 7, fy + fh - 12), (self.stair_x + 1, fy - 10))
        dark = (70, 50, 46)
        wood, wood2 = (166, 112, 66), (128, 84, 50)
        # ---------------- kitchen
        ky = fl[0] + fh - 2
        x = self.spots['stove'][1] - 14
        pygame.draw.rect(s, (176, 182, 198), (x - 9, ky - 13, 15, 13), 1)
        s.fill((236, 236, 240), (x - 8, ky - 12, 13, 12))                          # stove
        s.fill((60, 60, 70), (x - 7, ky - 9, 11, 7))
        s.fill((120, 120, 130), (x - 8, ky - 13, 13, 1))
        s.fill((200, 60, 60), (x - 6, ky - 11, 1, 1))
        s.fill((200, 60, 60), (x - 3, ky - 11, 1, 1))
        s.fill((150, 160, 175), (x - 5, fl[0] + 3, 9, 4))                          # extractor hood
        s.fill((120, 130, 145), (x - 2, fl[0], 3, 3))
        x = self.spots['counter'][1]
        pygame.draw.rect(s, (176, 182, 198), (x - 7, ky - 12, 17, 12), 1)
        s.fill((236, 236, 240), (x - 6, ky - 11, 15, 11))                          # counter + sink
        s.fill(wood, (x - 7, ky - 12, 17, 1))
        s.fill((160, 170, 190), (x + 2, ky - 15, 1, 3))
        s.fill((160, 170, 190), (x + 2, ky - 15, 3, 1))
        s.fill((210, 210, 220), (x - 5, ky - 7, 6, 1))
        pygame.draw.rect(s, (176, 182, 198), (x - 5, fl[0] + 4, 15, 10), 1)
        s.fill((255, 255, 255), (x - 4, fl[0] + 5, 13, 8))                         # wall cupboard
        s.fill((210, 214, 224), (x + 2, fl[0] + 5, 1, 8))
        fx_ = x + 14
        pygame.draw.rect(s, (176, 182, 198), (fx_ - 1, ky - 23, 12, 23), 1)
        s.fill((244, 246, 250), (fx_, ky - 22, 10, 22))                            # fridge
        s.fill((200, 204, 214), (fx_, ky - 13, 10, 1))
        s.fill((150, 156, 170), (fx_ + 8, ky - 19, 1, 4))
        s.fill((150, 156, 170), (fx_ + 8, ky - 10, 1, 5))
        s.fill((255, 120, 130), (fx_ + 2, ky - 18, 2, 2))                          # fridge magnet
        x = self.spots['table'][1]
        s.fill(wood2, (x - 5, ky - 6, 8, 1))                                       # chair + table
        s.fill(wood2, (x - 5, ky - 14, 1, 14))
        s.fill(wood2, (x + 2, ky - 5, 1, 5))
        s.fill(wood, (x + 5, ky - 10, 20, 2))
        s.fill(wood2, (x + 6, ky - 8, 1, 8))
        s.fill(wood2, (x + 23, ky - 8, 1, 8))
        s.fill((255, 255, 255), (x + 18, ky - 12, 3, 2))                           # vase with a flower
        s.fill((80, 180, 90), (x + 19, ky - 15, 1, 3))
        s.fill((255, 110, 150), (x + 18, ky - 17, 3, 2))
        x = self.spots['bowls'][1]
        s.fill((90, 150, 230), (x - 5, ky - 2, 5, 2))                              # pet bowls
        s.fill((240, 120, 90), (x + 2, ky - 2, 5, 2))
        # ---------------- living room
        dy = fl[1] + fh - 2
        x = self.spots['desk'][1]
        s.fill(wood, (x + 4, dy - 10, 20, 2))                                      # desk
        s.fill(wood2, (x + 5, dy - 8, 1, 8))
        s.fill(wood2, (x + 22, dy - 8, 1, 8))
        s.fill(wood2, (x + 14, dy - 8, 9, 5))
        s.fill((250, 210, 80), (x + 18, dy - 6, 1, 1))
        s.fill((226, 222, 206), (x + 9, dy - 21, 13, 10))                          # the computer
        s.fill((226, 222, 206), (x + 13, dy - 11, 5, 1))
        s.fill((200, 196, 180), (x + 7, dy - 11, 9, 1))                            # keyboard
        self.screen = pygame.Rect(x + 10, dy - 20, 11, 7)
        s.fill(wood2, (x - 5, dy - 6, 8, 1))                                       # desk chair
        s.fill(wood2, (x - 5, dy - 14, 1, 14))
        s.fill(wood2, (x + 2, dy - 5, 1, 5))
        x = self.spots['plant'][1]
        s.fill((200, 110, 70), (x - 3, dy - 5, 7, 5))                              # plant pot
        s.fill((170, 86, 54), (x - 4, dy - 6, 9, 1))
        x = self.spots['rug'][1]
        s.fill((230, 120, 130), (x - 12, dy - 1, 30, 1))                           # rug
        s.fill((250, 220, 150), (x - 10, dy - 1, 2, 1))
        s.fill((250, 220, 150), (x + 14, dy - 1, 2, 1))
        x = self.spots['sofa'][1]
        s.fill((120, 150, 220), (x - 9, dy - 8, 22, 6))                            # sofa
        s.fill((96, 126, 200), (x - 9, dy - 14, 4, 12))
        s.fill((96, 126, 200), (x + 13, dy - 10, 3, 8))
        s.fill((250, 210, 120), (x - 4, dy - 12, 4, 4))                            # cushion
        s.fill(dark, (x - 8, dy - 2, 1, 2))
        s.fill(dark, (x + 14, dy - 2, 1, 2))
        x = self.tv_x
        s.fill(wood2, (x - 5, dy - 7, 13, 7))                                      # tv cabinet + tv
        s.fill(dark, (x - 6, dy - 18, 15, 11))
        self.tv = pygame.Rect(x - 5, dy - 17, 13, 9)
        s.fill(dark, (x - 1, dy - 22, 1, 4))
        s.fill(dark, (x + 3, dy - 21, 1, 3))
        x = self.spots['piano'][1]
        s.fill(wood2, (x - 4, dy - 6, 7, 1))                                       # piano stool
        s.fill(wood2, (x - 3, dy - 5, 1, 5))
        s.fill(wood2, (x + 1, dy - 5, 1, 5))
        s.fill((60, 44, 44), (x + 7, dy - 17, 11, 17))                             # piano
        s.fill((40, 28, 28), (x + 6, dy - 18, 13, 1))
        s.fill((250, 250, 250), (x + 5, dy - 10, 9, 2))
        for kx in range(0, 9, 2):
            s.fill((20, 20, 20), (x + 5 + kx, dy - 10, 1, 1))
        s.fill((250, 250, 240), (x + 9, dy - 16, 7, 4))                            # sheet music
        self.clock = (self.spots['rug'][1] - 2, fl[1] + 8)
        pygame.draw.circle(s, (255, 255, 255), self.clock, 5)                      # wall clock (hands are live)
        pygame.draw.circle(s, wood2, self.clock, 5, 1)
        px_ = self.spots['sofa'][1] + 8
        s.fill(wood2, (px_ - 5, fl[1] + 4, 11, 9))                                 # picture: a little landscape
        s.fill((150, 210, 250), (px_ - 4, fl[1] + 5, 9, 4))
        s.fill((110, 190, 110), (px_ - 4, fl[1] + 9, 9, 3))
        s.fill((255, 240, 150), (px_ + 2, fl[1] + 6, 2, 2))
        self.record = (self.spots['plant'][1] + 9, dy - 8)                         # record player on a stool
        s.fill(wood2, (self.record[0] - 4, dy - 6, 9, 1))
        s.fill(wood2, (self.record[0] - 3, dy - 5, 1, 5))
        s.fill(wood2, (self.record[0] + 3, dy - 5, 1, 5))
        s.fill((230, 90, 90), (self.record[0] - 4, dy - 9, 9, 3))
        # ---------------- bedroom + bath
        by = fl[2] + fh - 2
        x = self.spots['bath'][1]
        pygame.draw.rect(s, (176, 182, 198), (x - 10, by - 10, 23, 9), 1)
        s.fill((250, 252, 255), (x - 9, by - 9, 21, 8))                            # bathtub
        s.fill((214, 222, 236), (x - 10, by - 10, 23, 1))
        s.fill((200, 206, 220), (x - 8, by - 1, 2, 1))
        s.fill((200, 206, 220), (x + 9, by - 1, 2, 1))
        s.fill((170, 180, 200), (x + 11, by - 20, 1, 10))                          # shower pipe
        s.fill((170, 180, 200), (x + 7, by - 20, 5, 1))
        s.fill((255, 255, 255), (x + 15, fl[2] + 6, 5, 7))                         # mirror
        s.fill((190, 226, 250), (x + 16, fl[2] + 7, 3, 5))
        x = self.spots['chair'][1]
        sx_ = x - 22
        s.fill(wood, (sx_ - 5, fl[2] + 6, 11, fh - 8))                             # bookshelf
        for row in range(3):
            yy = fl[2] + 8 + row * 8
            s.fill(wood2, (sx_ - 5, yy + 6, 11, 1))
            for i, c in enumerate([(220, 70, 70), (70, 130, 220), (240, 200, 70), (90, 180, 100), (180, 100, 200)]):
                if (i + row) % 4:
                    s.fill(c if row != 1 else c[::-1], (sx_ - 4 + i * 2, yy + (i + row) % 2, 2, 6 - (i + row) % 2))
        self.bowl = (sx_ + 1, fl[2] + 5)                                           # fish bowl on top of the shelf
        s.fill((230, 150, 90), (x - 7, by - 9, 14, 7))                             # armchair
        s.fill((206, 124, 70), (x - 9, by - 16, 4, 14))
        s.fill((206, 124, 70), (x + 6, by - 11, 3, 9))
        s.fill(dark, (x - 6, by - 2, 1, 2))
        s.fill(dark, (x + 5, by - 2, 1, 2))
        x = self.spots['bed'][1]
        s.fill(wood, (x - 14, by - 7, 28, 5))                                      # bed
        s.fill(wood2, (x + 13, by - 15, 2, 15))
        s.fill(wood2, (x - 15, by - 9, 2, 9))
        s.fill((255, 255, 255), (x - 13, by - 9, 26, 3))
        s.fill((255, 255, 255), (x + 5, by - 12, 8, 4))                            # pillow
        s.fill(wood2, (x - 24, by - 8, 7, 8))                                      # night stand + lamp
        s.fill((250, 210, 80), (x - 21, by - 5, 1, 1))
        s.fill(dark, (x - 21, by - 12, 1, 4))
        self.lamp = (x - 21, by - 14)
        s.fill((255, 226, 150), (x - 23, by - 16, 5, 4))
        self.house = s

    # ------------------------------------------------------------ brain
    def hour(self):
        h = self.p('hour', None)
        if h is None:
            return daylight()
        return daylight(hour=float(h) % 24)

    def choose(self, hour):
        if signals.recent(signals.typing, 2.5):
            return 'type'
        if self.act == 'type':
            return 'think' if self.type_t > 3 or random.random() < 0.5 else 'doze'
        if self.mail:
            return 'mail'
        if hour >= 23 or hour < 6.5:
            return 'sleep'
        if hour < 7:
            return 'bath'
        for m in (7.5, 12.5, 19):
            if m <= hour < m + 0.25:
                return 'cook'
            if m + 0.25 <= hour < m + 0.6:
                return 'eat'
        if 15 <= hour < 15.2:
            return 'coffee'
        pool = list(self.LEISURE)
        if hour >= 20.5:
            pool = ['stars', 'tv', 'read', 'bath', 'piano', 'stars', 'tv']
        elif hour < 9:
            pool += ['gym', 'coffee', 'garden']
        pool = [a for a in pool if a not in (self.act, self.last_act)] or pool
        return random.choice(pool)

    def go(self, act):
        self.last_act, self.act = self.act, act
        floor, x = self.spots[self.ACTS[act][0]]
        self.me.go(self, floor, x)
        self.act_t = 0.0
        self.act_len = random.uniform(14, 26) / self.busy
        self.thrown = False

    def emit(self, kind, x, y, vx=0.0, vy=0.0, life=1.0, extra=None):
        if len(self.fx) < 160:
            self.fx.append([kind, float(x), float(y), vx, vy, life, extra])

    def say(self, face, emo=None, secs=2.0, text=None):
        self.react = [face, emo, secs, text]

    def head_pos(self):
        return self.me.x, self.me.base_y(self) - 16

    def update(self, dt, energy):
        super().update(dt, energy)
        day, hour, sr, ss = self.hour()
        self.day, self.hr = day, hour
        me = self.me
        arrived = not me.path
        # ---- what the terminal is doing
        new, self.seq = signals.take_letters(self.seq)
        typed = [l[1] for l in new if l[4]]
        if typed:
            self.typed = (self.typed + ''.join(typed))[-3:]
        typing = signals.recent(signals.typing, 1.2)
        self.type_t = self.type_t + dt if typing else max(0.0, self.type_t - dt * 3)
        cpm = signals.typing_speed()
        if signals.enter != self.last_enter:
            self.last_enter = signals.enter
            self.hop = max(self.hop, 0.25)
        if signals.cmd is not self.last_cmd and signals.cmd:
            self.last_cmd = signals.cmd
            code, secs, _ = signals.cmd
            if code > 1:                                             # a real fright
                self.say('wow', '😱', 2.6)
                self.hop = 0.5
                self.cat_state, self.cat_t = 'puff', 2.5
                self.dog_state, self.dog_t = 'bark', 2.0
            elif code:
                self.say('sad', '😢', 2.4)
                hx, hy = self.head_pos()
                self.emit('drop', hx - 2, hy + 6, 0, 14, 0.8)
            elif secs >= 2:
                self.say('happy', '🥳', 3.0)
                self.hop = 3.0
                self.dog_state, self.dog_t = 'spin', 3.0
                hx, hy = self.head_pos()
                for _ in range(26):
                    self.emit('confetti', hx, hy - 4, random.uniform(-26, 26), random.uniform(-50, -10), random.uniform(1.0, 2.2),
                              random.choice([(255, 90, 110), (255, 210, 70), (90, 200, 255), (130, 230, 130), (220, 130, 255)]))
            elif random.random() < 0.3:
                self.say('happy', '👍', 1.4)
        if signals.bell != self.last_bell:
            self.last_bell = signals.bell
            self.mail = True
            self.dog_state, self.dog_t = 'bark', 2.2
            if self.act not in ('type', 'sleep'):
                self.say('wow', None, 1.2, 'DING!')
        if self.react:
            self.react[2] -= dt
            if self.react[2] <= 0:
                self.react = None
        self.hop = max(0.0, self.hop - dt)
        self.blink -= dt
        if self.blink < -0.15:
            self.blink = random.uniform(1.5, 5)
        # ---- choose what to do
        self.act_t += dt
        want_type = signals.recent(signals.typing, 2.5)
        if want_type and self.act != 'type':
            self.go('type')
        elif self.act == 'type' and not want_type:
            self.go(self.choose(hour))
        elif self.act == 'sleep':
            if not (hour >= 23 or hour < 6.5):
                self.go(self.choose(hour))
        elif self.act == 'mail' and arrived and self.act_t > 5 and self.mail:
            self.mail = False
        elif arrived and self.act_t > self.act_len:
            self.go(self.choose(hour))
        elif (hour >= 23 or hour < 6.5) and self.act not in ('sleep', 'type', 'think', 'doze', 'mail') and arrived:
            self.go('sleep')
        me.step(self, dt, 30.0)
        arrived = not me.path
        hx, hy = self.head_pos()
        fl, fh = self.floors, self.fh
        a = self.act
        r = random.random
        if arrived:
            # ---- things that happen while doing something
            if a == 'type':
                if r() < dt * (6 + energy * 20):
                    self.screen_lines = self.screen_lines[1:] + [random.randint(1, 9)]
                if cpm > 320 and r() < dt * 5:
                    self.emit('drop', hx + random.choice((-5, 5)), hy + 2, random.uniform(-6, 6), -8, 0.6)
                if cpm > 480 and r() < dt * 6:
                    self.emit('steam', self.screen.centerx, self.screen.top - 2, random.uniform(-3, 3), -9, 1.2, 60)
                if energy > 0.9 and not self.react and r() < dt * 0.6:
                    self.say('wow', '😮', 1.6)
            elif a == 'sleep' or a == 'doze':
                if r() < dt * 0.9:
                    self.emit('z', hx + 4, hy - 2, 3, -6, 2.2)
            elif a == 'bath':
                if r() < dt * 5:
                    self.emit('bubble', self.spots['bath'][1] + random.uniform(-8, 9), fl[2] + fh - 12, random.uniform(-2, 2), -7, 1.6)
                if r() < dt * 14:
                    self.emit('drop', self.spots['bath'][1] + 7 + random.uniform(-1, 3), fl[2] + fh - 20, 0, 34, 0.3)
                if r() < dt * 0.8:
                    self.emit('note', hx + 5, hy - 2, 4, -8, 1.6)
            elif a == 'cook':
                if r() < dt * 5:
                    self.emit('steam', self.spots['stove'][1] - 16 + random.uniform(-2, 2), fl[0] + fh - 18, random.uniform(-2, 2), -9, 1.2, 235)
            elif a == 'coffee':
                if r() < dt * 2:
                    self.emit('steam', hx + 6, hy + 8, 0, -6, 0.9, 235)
            elif a == 'piano' or a == 'dance':
                if r() < dt * 3:
                    src = (self.spots['piano'][1] + 12, fl[1] + 10) if a == 'piano' else (self.record[0], self.record[1] - 4)
                    self.emit('note', src[0] + random.uniform(-3, 3), src[1], random.uniform(-4, 4), -9, 1.8,
                              random.choice([(60, 60, 90), (220, 70, 110), (60, 130, 220)]))
            elif a == 'gym':
                if r() < dt * 2:
                    self.emit('drop', hx + random.choice((-6, 6)), hy + 3, 0, 10, 0.5)
            elif a == 'clean':
                me.x = self.spots['rug'][1] + math.sin(self.act_t * 1.2) * 16
                me.face = 1 if math.cos(self.act_t * 1.2) > 0 else -1
                if r() < dt * 6:
                    self.emit('dust', me.x + me.face * 9, fl[1] + fh - 4, random.uniform(-5, 5), -5, 0.7)
            elif a == 'water':
                self.plant = min(9.0, self.plant + dt * 0.35)
                if r() < dt * 12:
                    self.emit('drop', self.spots['plant'][1] + random.uniform(-2, 2), fl[1] + fh - 15, 0, 26, 0.35)
            elif a == 'garden':
                self.garden = min(6.0, self.garden + dt * 0.3)
                if r() < dt * 12:
                    self.emit('drop', me.x + me.face * 8 + random.uniform(-2, 2), self.gy - 9, 0, 24, 0.3)
            elif a == 'feed':
                if self.cat_state not in ('eat', 'puff'):
                    self.cat_state, self.cat_t = 'eat', 12.0
            elif a == 'fetch':
                if not self.thrown and self.act_t > 1.5 and self.ball is None and self.pets:
                    self.thrown = True
                    d = -1 if me.x > self.x0 * 0.5 else 1
                    me.face = d
                    self.ball = [me.x, self.gy - 14, d * random.uniform(24, 40), -34]
                    self.dog_state, self.dog_t = 'fetch', 12.0
                elif self.thrown and self.ball is None and self.dog_state == 'wander':
                    self.thrown = False if self.act_t < self.act_len - 5 else True
                    if r() < dt * 2:
                        self.emit('heart', self.dog_x + 5, self.gy - 10, 0, -8, 1.2)
            elif a == 'stars':
                if self.shoot is None and day < 0.3 and r() < dt * 0.35:
                    self.shoot = [random.uniform(self.lw * 0.1, self.lw * 0.6), random.uniform(4, self.gy * 0.3), 0.8]
                    self.say('wow', '✨', 1.6)
            elif a == 'mail' and self.act_t > 2 and r() < dt * 1.5:
                self.emit('heart', hx, hy - 2, random.uniform(-3, 3), -8, 1.4)
            elif a == 'wave' and self.act_t < 4 and not self.react:
                self.say('happy', None, 2.5, 'HI!')
            elif a == 'eat' and r() < dt * 0.5:
                self.emit('heart', hx + 5, hy, 0, -6, 1.0)
        # chimney smoke when someone cooks or it is cold and dark
        if (a == 'cook' and arrived or day < 0.4) and r() < dt * 2.5:
            self.emit('steam', self.chim[0] + 4, self.chim[1] - 1, random.uniform(1, 5), -8, 2.6, 200)
        if self.shoot:
            self.shoot[0] += 60 * dt
            self.shoot[1] += 22 * dt
            self.shoot[2] -= dt
            if self.shoot[2] <= 0:
                self.shoot = None
        for c in self.clouds:
            c[0] += c[2] * dt
            if c[0] > self.lw + 20:
                c[0], c[1] = -24.0, random.uniform(4, self.lh * 0.3)
        self.fish += dt
        # ---- particles
        for p in self.fx:
            p[1] += p[3] * dt
            p[2] += p[4] * dt
            p[5] -= dt
            if p[0] == 'confetti':
                p[4] += 70 * dt
                p[3] *= 1 - dt
        self.fx = [p for p in self.fx if p[5] > 0]
        if self.pets:
            self._dog(dt, day, hour)
            self._cat(dt, typing)

    def _dog(self, dt, day, hour):
        gy, lo, hi = self.gy, 4.0, float(self.x0 - 16)
        self.dog_t -= dt
        st = self.dog_state
        if self.ball:
            b = self.ball
            b[0] += b[2] * dt
            b[1] += b[3] * dt
            b[3] += 90 * dt
            if b[1] > gy - 2:
                b[1], b[3], b[2] = gy - 2, -b[3] * 0.45, b[2] * 0.6
            b[0] = max(lo, min(hi + 8, b[0]))
        if st == 'fetch':
            if self.ball and self.ball != 'dog':
                d = self.ball[0] - self.dog_x - 4
                self.dog_v = max(-46, min(46, d * 4))
                if abs(d) < 3 and self.ball[1] > gy - 6:
                    self.ball = None
                    self.dog_carry = True
            elif getattr(self, 'dog_carry', False):
                d = self.me.x - 12 - self.dog_x if self.me.floor == -1 else 0
                self.dog_v = max(-40, min(40, d * 3))
                if abs(d) < 3:
                    self.dog_carry = False
                    self.dog_state = 'wander'
                    self.emit('heart', self.dog_x + 5, gy - 10, 0, -8, 1.2)
            if self.dog_t <= 0:
                self.ball, self.dog_carry, self.dog_state = None, False, 'wander'
        elif st in ('bark', 'spin', 'howl'):
            self.dog_v = 0.0
            if st == 'bark' and random.random() < dt * 5:
                self.emit('text', self.dog_x + 12, gy - 12, 6, -10, 0.5, '!')
            if st == 'howl' and random.random() < dt * 2:
                self.emit('note', self.dog_x + 7, gy - 10, 3, -9, 1.4, (200, 210, 255))
            if self.dog_t <= 0:
                self.dog_state = 'wander'
        elif st == 'sleep':
            self.dog_v = 0.0
            if random.random() < dt * 0.7:
                self.emit('z', self.dog_x + 8, gy - 5, 3, -5, 2.0)
            if day > 0.3 or self.dog_t <= 0 and random.random() < dt * 0.05:
                self.dog_state = 'wander'
        else:
            if self.me.floor == -1 and self.act in ('fetch', 'garden', 'stars', 'mail'):
                self.dog_v = max(-22, min(22, (self.me.x - 14 - self.dog_x) * 2))       # stay close and wag
            elif random.random() < dt * 0.4 or self.dog_x <= lo or self.dog_x >= hi:
                self.dog_v = random.choice((-1, 1, 0)) * random.uniform(6, 16)
                if self.dog_x <= lo:
                    self.dog_v = abs(self.dog_v) + 4
                if self.dog_x >= hi:
                    self.dog_v = -abs(self.dog_v) - 4
            if day < 0.15 and random.random() < dt * 0.05:
                if abs(moon_phase() - 0.5) < 0.08 and random.random() < 0.5:
                    self.dog_state, self.dog_t = 'howl', 4.0
                else:
                    self.dog_x = float(self.doghouse_x + 2)
                    self.dog_state, self.dog_t = 'sleep', 40.0
        self.dog_x = max(lo, min(hi, self.dog_x + self.dog_v * dt))

    def _cat(self, dt, typing):
        cat, st = self.cat, self.cat_state
        self.cat_t -= dt
        moving = cat.step(self, dt, 26.0)
        if moving:
            return
        sofa, win, bowls, desk = self.spots['sofa'], self.spots['window'], self.spots['bowls'], self.spots['desk']
        if st == 'puff':
            if self.cat_t <= 0:
                self.cat_state, self.cat_t = 'sit', 3.0
            return
        if self.type_t > 7 and st != 'desk' and self.act == 'type' and random.random() < dt * 0.25:
            self.cat_state, self.cat_t = 'desk', random.uniform(8, 16)
            cat.go(self, desk[0], desk[1] + 17)
            return
        if st == 'desk' and (self.act != 'type' or self.cat_t <= 0):
            self.cat_state, self.cat_t = 'sit', 2.0
            cat.go(self, win[0], win[1])
            return
        if st != 'eat' and self.act in ('cook', 'eat') and not self.me.path and cat.floor != 0:
            self.cat_state, self.cat_t = 'beg', 20.0
            cat.go(self, 0, self.me.x + 12)
            return
        if st == 'eat' and (cat.floor != bowls[0] or abs(cat.x - bowls[1]) > 6):
            cat.go(self, bowls[0], bowls[1] + 3)
            return
        if st == 'beg' and random.random() < dt * 0.5:
            self.emit('heart', cat.x, cat.base_y(self) - 9, 0, -7, 1.0)
        if self.cat_t <= 0:
            nxt = random.choice(['nap', 'sit', 'sit', 'roam'])
            self.cat_state, self.cat_t = nxt, random.uniform(14, 40)
            if nxt == 'nap':
                cat.go(self, sofa[0], sofa[1] + 9)
            elif nxt == 'sit':
                cat.go(self, win[0], win[1])
            else:
                f = random.choice((0, 1, 2))
                cat.go(self, f, random.uniform(self.x0 + 24, self.x1 - 12))
        elif st == 'nap' and random.random() < dt * 0.5:
            self.emit('z', cat.x + 3, cat.base_y(self) - 12, 2, -5, 1.8)

    # ------------------------------------------------------------ render
    def tint(self, col):
        """outdoor colors by daylight"""
        d = self.day
        return (int(col[0] * (0.22 + 0.78 * d)), int(col[1] * (0.26 + 0.74 * d)), int(col[2] * (0.38 + 0.62 * d)))

    def draw(self, surf, first):
        s = self.low
        lw, lh, gy, x0, x1, fh, fl = self.lw, self.lh, self.gy, self.x0, self.x1, self.fh, self.floors
        day, hour = getattr(self, 'day', 1.0), getattr(self, 'hr', 12.0)
        _, _, sr, ss = self.hour()
        t, T = self.t, self.tint
        top, bot, dusk = sky_colors(day)
        s.blit(gradient(lw, lh, top, bot, self.cache, 'sky'), (0, 0))
        # ---- sky
        if day < 0.4:
            for x, y, tw in self.stars:
                v = max(0, min(255, int(255 * (1 - day / 0.4) * (0.5 + 0.5 * math.sin(t * 2 + tw * 30)))))
                s.fill((v, v, v), (int(x), int(y), 1, 1))
            mx, my = int(lw * 0.2), int(lh * 0.16)
            pygame.draw.circle(s, (240, 238, 214), (mx, my), 7)
            ph = moon_phase()
            if abs(ph - 0.5) > 0.06:
                pygame.draw.circle(s, top, (mx + int((ph - 0.5) * 28), my), 7)
            if self.shoot:
                x, y, life = self.shoot
                pygame.draw.line(s, (255, 255, 230), (x, y), (x - 9, y - 3))
        else:
            f = (hour - sr) / max(0.1, ss - sr)
            sx, sy = int(lw * (0.08 + 0.84 * f)), int(gy - math.sin(max(0, min(1, f)) * math.pi) * gy * 0.8)
            sun = _lerp((255, 244, 170), (255, 150, 80), dusk)
            pygame.draw.circle(s, sun, (sx, sy), 8)
            for i in range(8):                                               # little rays
                a = t * 0.4 + i * math.pi / 4
                s.fill(sun, (int(sx + math.cos(a) * 12), int(sy + math.sin(a) * 12), 1, 1))
        cc = _lerp((60, 64, 96), (255, 255, 255), day)
        for x, y, v in self.clouds:
            x, y = int(x), int(y)
            s.fill(cc, (x, y + 2, 20, 4))
            s.fill(cc, (x + 3, y, 8, 3))
            s.fill(cc, (x + 9, y + 1, 7, 2))
        # ---- yard
        s.fill(T((104, 196, 96)), (0, gy, lw, lh - gy))
        s.fill(T((84, 172, 80)), (0, gy, lw, 1))
        for x in range(3, lw, 7):
            s.fill(T((126, 214, 110)), (x + (x * 7 % 3), gy + 2 + (x * 5 % 6), 1, 2))
        s.fill(T((214, 196, 150)), (x0 - 9, gy, 7, lh - gy))                 # garden path to the door
        tx = self.tree_x
        s.fill(T((130, 84, 50)), (tx - 2, gy - 22, 4, 22))                   # tree with a swing
        sway = math.sin(t * 0.8) * 1.2
        for cx, cy, rr in ((0, -30, 10), (-7, -24, 7), (7, -25, 8), (1, -37, 7)):
            pygame.draw.circle(s, T((70, 160, 80)), (int(tx + cx + sway), gy + cy), rr)
        for cx, cy in ((-4, -32), (5, -27), (-8, -23), (2, -38)):
            s.fill(T((240, 80, 80)), (int(tx + cx + sway), gy + cy, 2, 2))   # apples
        sw = math.sin(t * 1.6) * 2
        pygame.draw.line(s, T((230, 220, 200)), (tx + 9, gy - 22), (tx + 9 + sw, gy - 8))
        pygame.draw.line(s, T((230, 220, 200)), (tx + 14, gy - 22), (tx + 14 + sw, gy - 8))
        s.fill(T((180, 120, 70)), (int(tx + 8 + sw), gy - 8, 8, 1))
        fence = T((246, 240, 226))
        for x in range(2, x0 - 12, 5):
            s.fill(fence, (x, gy - 7, 2, 7))
            s.fill(fence, (x, gy - 8, 1, 1))
        s.fill(fence, (0, gy - 5, x0 - 12, 1))
        dh = self.doghouse_x
        s.fill(T((200, 130, 80)), (dh - 2, gy - 11, 16, 11))                 # dog house
        pygame.draw.polygon(s, T((210, 70, 60)), [(dh - 4, gy - 11), (dh + 16, gy - 11), (dh + 6, gy - 19)])
        s.fill((30, 18, 14), (dh + 3, gy - 7, 6, 7))
        s.fill(T((250, 240, 220)), (dh + 3, gy - 10, 6, 2))
        # garden flowers (they grow when watered)
        gx = self.spots['flowers'][1]
        for i in range(6):
            hgt = int(min(6, self.garden + (i * 37 % 3)))
            x = gx - 14 + i * 5
            s.fill(T((70, 170, 80)), (x, gy - hgt, 1, hgt))
            s.fill(T([(255, 110, 140), (255, 220, 80), (190, 130, 255), (255, 255, 255)][i % 4]), (x - 1, gy - hgt - 2, 3, 2))
        mb = self.spots['mailbox'][1] + 6                                    # mailbox
        s.fill(T((120, 120, 130)), (mb, gy - 10, 1, 10))
        s.fill(T((90, 130, 230)), (mb - 3, gy - 14, 7, 5))
        if self.mail:
            s.fill((240, 60, 60), (mb + 4, gy - 18, 1, 5))
            s.fill((240, 60, 60), (mb + 5, gy - 18, 2, 2))
            s.fill((255, 255, 255), (mb - 2, gy - 13, 4, 2))
        # ---- house (static layer) + live details
        s.blit(self.house, (0, 0))
        a, arrived = self.act, not self.me.path
        dy, ky, by = fl[1] + fh - 2, fl[0] + fh - 2, fl[2] + fh - 2
        cx, cy = self.clock                                                  # real time on the wall clock
        lt = time.localtime() if self.p('hour', None) is None else None
        hh = (lt.tm_hour + lt.tm_min / 60) if lt else hour
        mm = lt.tm_min if lt else (hour % 1) * 60
        pygame.draw.line(s, (40, 40, 50), (cx, cy), (cx + math.sin(hh / 12 * math.tau) * 2.4, cy - math.cos(hh / 12 * math.tau) * 2.4))
        pygame.draw.line(s, (200, 60, 60), (cx, cy), (cx + math.sin(mm / 60 * math.tau) * 3.6, cy - math.cos(mm / 60 * math.tau) * 3.6))
        sc = self.screen                                                     # the computer
        if a == 'type' and arrived:
            s.fill((12, 40, 20), sc)
            for i, ln in enumerate(self.screen_lines[-2:]):
                s.fill((70, 200, 110), (sc.x + 1, sc.y + 1 + i, min(sc.w - 2, ln), 1))
            tiny_text(s, sc.x, sc.y + 2 if False else sc.bottom - 5, ''.join(c if c.upper() in _F else '*' for c in self.typed)[-3:] or '_',
                      (140, 255, 170))
        else:
            s.fill((30, 36, 44), sc)
            if int(t * 0.7) % 2:
                s.fill((70, 200, 110), (sc.x + 1, sc.y + 1, 2, 1))
        tv = self.tv
        if a == 'tv' and arrived:
            ph = int(t * 2.5) % 4
            s.fill([(90, 150, 255), (255, 130, 150), (130, 230, 150), (255, 240, 150)][ph], tv)
            s.fill((255, 255, 255), (tv.x + 2 + ph * 2, tv.y + 3, 3, 3))
            s.fill((60, 160, 90), (tv.x, tv.bottom - 2, tv.w, 2))
        else:
            s.fill((34, 40, 52), tv)
            s.fill((70, 80, 100), (tv.x + 1, tv.y + 1, 2, 1))
        rx, ry = self.record                                                 # record player
        if a == 'dance' and arrived:
            an = t * 5
            s.fill((20, 20, 24), (rx - 3, ry - 1, 7, 2))
            s.fill((255, 255, 255), (int(rx + math.cos(an) * 2), ry - 1 + (1 if math.sin(an) > 0 else 0), 1, 1))
        else:
            s.fill((20, 20, 24), (rx - 3, ry - 1, 7, 2))
        px_, ph_ = self.spots['plant'][1], int(self.plant)                   # the house plant grows and blooms
        s.fill((70, 170, 80), (px_, dy - 6 - ph_, 1, ph_))
        for i in range(1, ph_, 2):
            s.fill((90, 200, 100), (px_ + (1 if i % 4 == 1 else -2), dy - 6 - i, 2, 1))
        if ph_ >= 7:
            s.fill((255, 120, 160), (px_ - 1, dy - 8 - ph_, 3, 2))
            s.fill((255, 230, 120), (px_, dy - 8 - ph_, 1, 1))
        bx, bwy = self.bowl                                                  # fish bowl
        s.fill((170, 220, 250), (bx - 3, bwy - 5, 7, 5))
        s.fill((120, 190, 240), (bx - 3, bwy - 4, 7, 4))
        fx = bx + math.sin(self.fish * 1.3) * 2
        s.fill((255, 140, 50), (int(fx), bwy - 3, 2, 1))
        s.fill((255, 140, 50), (int(fx) - (1 if math.cos(self.fish * 1.3) > 0 else -2), bwy - 3, 1, 1))
        stx = self.spots['stove'][1] - 14
        if a == 'cook' and arrived:                                          # pan on the fire
            s.fill((50, 50, 60), (stx - 5, ky - 15, 8, 2))
            s.fill((50, 50, 60), (stx + 3, ky - 15, 4, 1))
            s.fill((255, 170, 40) if int(t * 10) % 2 else (255, 90, 40), (stx - 4, ky - 13, 6, 1))
            s.fill((255, 220, 90), (stx - 3 + int(t * 6) % 3, ky - 16, 2, 1))
        if a == 'eat' and arrived:
            tx_ = self.spots['table'][1]
            s.fill((255, 255, 255), (tx_ + 8, ky - 11, 6, 1))
            s.fill((240, 170, 70), (tx_ + 9, ky - 12, 4, 1))
        if a == 'bath' and arrived:                                          # water in the tub + shower curtain
            bxx = self.spots['bath'][1]
            s.fill((150, 210, 250), (bxx - 8, by - 9, 19, 2))
            s.fill((255, 255, 255), (bxx - 6 + int(t * 2) % 3, by - 10, 3, 1))
            s.fill((255, 220, 60), (bxx + 5, by - 11 + int(math.sin(t * 3) > 0), 3, 2))       # rubber duck
            s.fill((255, 140, 40), (bxx + 8, by - 10 + int(math.sin(t * 3) > 0), 1, 1))
        lit_lamp = day < 0.5 and a != 'sleep'
        if lit_lamp:
            glow(s, self.lamp[0], self.lamp[1], 9, (60, 48, 16))
        # ---- night: rooms nobody is in are dark
        if day < 0.5:
            dim = int(110 + 145 * day * 2)
            for i, fy in enumerate(fl):
                here = self.me.floor == i or (i == 1 and a == 'tv')
                if not here or a == 'sleep':
                    s.fill((dim, dim, min(255, dim + 30)), (x0, fy, x1 - x0, fh), special_flags=pygame.BLEND_RGB_MULT)
        # ---- everybody
        if self.pets:
            self._draw_cat(s)
        self._draw_me(s)
        if self.pets:
            self._draw_dog(s)
        # ---- particles
        for kind, x, y, vx, vy, life, ex in self.fx:
            x, y = int(x), int(y)
            if kind == 'z':
                tiny_text(s, x, y, 'Z', (120, 140, 230) if life > 1 else (170, 185, 240))
            elif kind == 'note':
                c = ex or (60, 60, 90)
                s.fill(c, (x + 1, y, 1, 4))
                s.fill(c, (x - 1, y + 3, 2, 2))
                s.fill(c, (x + 2, y, 1, 1))
            elif kind == 'steam':
                v = ex or 230
                pygame.draw.circle(s, (v, v, v + (20 if v < 230 else 0)), (x, y), 1 + int((1.4 - min(1.4, life)) * 2))
            elif kind == 'drop':
                s.fill((90, 170, 255), (x, y, 1, 2))
            elif kind == 'bubble':
                pygame.draw.circle(s, (220, 240, 255), (x, y), 1 + int(life) % 2, 1)
            elif kind == 'heart':
                s.fill((255, 90, 120), (x - 1, y, 1, 2))
                s.fill((255, 90, 120), (x + 1, y, 1, 2))
                s.fill((255, 90, 120), (x, y + 1, 1, 2))
            elif kind == 'confetti':
                s.fill(ex, (x, y, 2, 1) if int(life * 8) % 2 else (x, y, 1, 2))
            elif kind == 'dust':
                s.fill((200, 190, 170), (x, y, 2, 1))
            elif kind == 'text':
                tiny_text(s, x, y, ex, (255, 80, 60))
        if self.k == 1:
            surf.blit(s, (0, self.h - lh))
        else:
            big = pygame.transform.scale(s, (lw * self.k, lh * self.k))
            surf.blit(big, (self.w - lw * self.k, self.h - lh * self.k))

    def _draw_me(self, s):
        me, a = self.me, self.act
        arrived = not me.path
        t = self.t
        fl, fh = self.floors, self.fh
        night = self.hr >= 21 or self.hr < 7.2
        shirt = (150, 190, 250) if night else self.shirt                     # pajamas
        face = 'normal'
        if self.react:
            face = self.react[0]
        elif arrived and a in ('sleep', 'doze'):
            face = 'sleep'
        elif arrived and a in ('eat', 'tv', 'dance', 'fetch', 'mail', 'piano', 'bath', 'wave', 'feed'):
            face = 'happy'
        elif a == 'type' and signals.typing_speed() > 320:
            face = 'wow'
        if face == 'normal' and self.blink < 0:
            face = 'blink'
        base = me.base_y(self)
        x = int(me.x)
        flip = me.face < 0
        hop = int(abs(math.sin(t * 10)) * 4) if self.hop > 0 else 0
        dyo = 0
        if me.walk_t > 0 and not arrived:
            pose = 'walk1' if int(me.walk_t * 7) % 2 else 'walk2'
            dyo = -(int(me.walk_t * 7) % 2)
        elif not arrived:
            pose = 'stand'
        else:
            pose = self.ACTS[a][1]
            if a == 'sleep':                                                 # in bed: head on the pillow, blanket breathing
                bx, by = self.spots['bed'][1], fl[2] + fh - 2
                img = person('head', 'sleep', False, shirt, self.hair)
                s.blit(img, (bx + 4, by - 17))
                br = int(math.sin(t * 1.5) > 0)
                s.fill((250, 130, 150), (bx - 13, by - 11 - br, 20, 4 + br))
                s.fill((255, 170, 185), (bx - 13, by - 11 - br, 20, 1))
                s.fill((255, 255, 255), (bx + 5, by - 11 - br, 2, 4 + br))
                return
            if a == 'bath':                                                  # only the head looks out of the tub
                bx, by = self.spots['bath'][1], fl[2] + fh - 2
                s.blit(person('head', face, False, shirt, self.hair), (bx - 6, by - 17 + int(math.sin(t * 2) > 0.6)))
                s.fill((150, 210, 250), (bx - 8, by - 9, 19, 2))
                s.fill((250, 252, 255), (bx - 9, by - 7, 21, 6))
                s.fill((176, 182, 198), (bx - 10, by - 2, 23, 1))
                return
            if pose == 'type':
                pose = 'type1' if int(t * 9) % 2 else 'type2'
                flip = False if a == 'type' else flip
                if a == 'piano':
                    flip = False
            elif pose == 'dance':
                pose = 'dance1' if int(t * 4) % 2 else 'dance2'
                dyo = -(int(t * 8) % 2)
                flip = int(t * 1.0) % 2 == 0
            elif pose == 'jack':
                pose = 'jack' if int(t * 4) % 2 else 'stand'
                dyo = -2 if pose == 'jack' else 0
            elif pose == 'wave':
                pose = 'wave1' if int(t * 6) % 2 else 'wave2'
            elif pose == 'sit':
                flip = a in ('think', 'doze') and False
                if a == 'doze':
                    dyo = 1
            if a in ('stars',):
                pose = 'stand'
            if a == 'fetch' and self.ball and self.ball[3] < 0:
                pose = 'up'
            if a in ('tv',):
                flip = False
            if a == 'cook':
                flip = True
            if a == 'read':
                flip = True
        if self.react and self.react[0] == 'wow' and arrived and pose in ('stand', 'carry', 'wave1', 'wave2'):
            pose = 'up'
        if self.hop > 0 and pose in ('stand', 'carry'):
            pose = 'up'
        img = person(pose, face, flip, shirt, self.hair)
        seat = 0
        if pose in ('sit', 'type1', 'type2'):
            seat = {'eat': 5, 'tv': 6, 'read': 7, 'piano': 5}.get(a, 5)
        y = int(base) - img.get_height() - seat - hop + dyo
        s.blit(img, (x - 5, y))
        hx = x + (6 if not flip else -8)
        # things in the hands
        if arrived:
            if a == 'water' or a == 'garden':
                s.fill((120, 170, 230), (hx, y + 11, 5, 4))
                s.fill((120, 170, 230), (hx + (5 if not flip else -2), y + 11, 2, 1))
            elif a == 'coffee' or a == 'cook' and False:
                s.fill((255, 255, 255), (hx, y + 11, 3, 3))
            elif a == 'read':
                s.fill((200, 70, 70), (x - 10, y + 12, 5, 4))
                s.fill((255, 255, 255), (x - 9, y + 13, 3, 2))
            elif a == 'clean':
                s.fill((90, 90, 110), (hx + (-1 if not flip else 2), y + 8, 1, 4))     # handle: from the hand down to the brush
                s.fill((230, 90, 90), (hx + (-2 if not flip else -1), y + 12, 6, 2))   # brush sits on the floor (feet end at y + 14)
            elif a == 'feed':
                s.fill((240, 200, 110), (hx, y + 11, 4, 4))
            elif a == 'mail':
                s.fill((255, 255, 255), (hx, y + 11, 5, 4))
                s.fill((240, 90, 110), (hx + 2, y + 12, 1, 1))
            elif a == 'fetch' and not self.thrown:
                s.fill((240, 70, 70), (hx, y + 11, 2, 2))
        emo = text = None
        if self.react:
            emo, text = self.react[1], self.react[3]
        elif arrived and int(t * 0.4) % 3 == 0:
            emo = self.ACTS[a][2]
        if emo or text:
            bubble(s, x, y - 1, emo, text)

    def _draw_dog(self, s):
        gy, st, t = self.gy, self.dog_state, self.t
        flip = self.dog_v < 0 if abs(self.dog_v) > 0.5 else getattr(self, '_dogflip', False)
        self._dogflip = flip
        x = int(self.dog_x)
        if st == 'sleep':
            img = pet(DOG, 'sleep', False)
            s.blit(img, (self.doghouse_x + 1, gy - 2))
            return
        if st == 'howl':
            img = pet(DOG, 'howl', flip)
        elif st == 'bark':
            img = pet(DOG, 'sit' if int(t * 6) % 2 else 'walk1', flip)
        elif abs(self.dog_v) > 1 or st == 'spin':
            if st == 'spin':
                flip = int(t * 5) % 2 == 0
            img = pet(DOG, 'walk1' if int(t * 8) % 2 else 'walk2', flip)
        else:
            img = pet(DOG, 'sit' if int(t * 0.3 + 1) % 3 else 'walk1', flip)
        hop = int(abs(math.sin(t * 12)) * 3) if st in ('bark', 'spin') else 0
        s.blit(img, (x, gy - img.get_height() - hop))
        if getattr(self, 'dog_carry', False):
            s.fill((240, 70, 70), (x + (0 if flip else 10), gy - 4 - hop, 2, 2))
        if self.ball:
            s.fill((240, 70, 70), (int(self.ball[0]), int(self.ball[1]) - 1, 2, 2))

    def _draw_cat(self, s):
        cat, st, t = self.cat, self.cat_state, self.t
        base = cat.base_y(self)
        x = int(cat.x)
        if cat.path:
            img = pet(CAT, 'walk1' if int(t * 8) % 2 else 'walk2', cat.face > 0)
            s.blit(img, (x - 4, int(base) - img.get_height()))
            return
        lift = 0
        if st == 'nap':
            img, lift = pet(CAT, 'sleep', False), 8
        elif st == 'puff':
            img, lift = pet(CAT, 'puff', False), int(abs(math.sin(t * 14)) * 3)
        elif st == 'desk':
            img, lift = pet(CAT, 'sit', False), 10
        else:
            # sitting: the head follows your cursor
            flip = False
            if signals.cursor_x is not None:
                flip = signals.cursor_x / self.k < x + (self.lw - self.w / self.k)
            img = pet(CAT, 'sit', flip)
            if st == 'sit' and abs(cat.x - self.spots['window'][1]) < 3:
                lift = 17                                                    # on top of the piano, looking out
        s.blit(img, (x - 3, int(base) - img.get_height() - lift))
        if st in ('sit', 'desk', 'beg') and int(t * 2) % 5 == 0:                 # tail flick
            s.fill((240, 236, 228), (x + 4, int(base) - 3 - lift, 1, 1))
