"""EMERALD MINE - the whole-suite mode.

The terminal is a block of underground earth and every printed letter is an
EMERALD buried in it. The miner cursor (see minercursor.py) walks along with
the cursor, swings its pickaxe at the emerald ore next to it and harvests the
letters - each one flies into the counter. When output floods in, he swings
faster and reaches wider; letters he can't reach crumble free on their own
after a moment, and at the very top of the overload scale: TNT.
"""
from __future__ import annotations

import math
import random
import time

import numpy as np
import pygame

from . import particles as P

DIRT, ROCK, EMERALD, RUBY, DIAMOND, GOLD, TUNNEL = range(7)
ORE = EMERALD   # buried letters are drawn as emerald ore
TILE_W = [(DIRT, 84), (ROCK, 11), (RUBY, 1.2), (DIAMOND, 0.8), (GOLD, 3)]
GEM_COL = {EMERALD: ((30, 210, 90), (190, 255, 210), (10, 110, 50)),
           RUBY: ((220, 30, 60), (255, 180, 200), (110, 10, 30)),
           DIAMOND: ((150, 230, 255), (255, 255, 255), (60, 120, 170))}
NAMES = {RUBY: 'ruby', DIAMOND: 'diamond', GOLD: 'gold'}


def _pick_tile():
    r = random.random() * 100
    acc = 0
    for t, w in TILE_W:
        acc += w
        if r < acc:
            return t
    return DIRT


class Mine:
    def __init__(self, manager, screen, sound=None):
        self.m = manager
        self.screen = screen
        self.sound = sound
        self.cw, self.ch = manager.cw, manager.ch
        self.pending = {}            # (x, vy) -> time queued
        self.stats = {'emerald': 0, 'ruby': 0, 'diamond': 0, 'gold': 0, 'tnt': 0}
        self.shake = 0.0
        self.flash = 0.0
        self.cols = self.rows = 0
        self.surf = None
        self.events = []
        self._build_tiles()
        self.resize(screen.cols, screen.rows)

    # ------------------------------------------------------------ assets
    def _build_tiles(self):
        cw, ch = self.cw, self.ch
        rng = random.Random(1234)
        self.tiles = {}
        for t in range(7):
            variants = []
            for v in range(4):
                s = pygame.Surface((cw, ch))
                if t == TUNNEL:
                    s.fill((14, 10, 8))
                    for _ in range(max(1, cw * ch // 25)):
                        s.set_at((rng.randrange(cw), rng.randrange(ch)), (24, 17, 12))
                    variants.append(s)
                    continue
                base, lo, hi = ((62, 62, 72), (46, 46, 54), (84, 84, 96)) if t == ROCK else \
                    ((64, 40, 24), (50, 31, 18), (82, 54, 32))
                s.fill(base)
                for y in range(ch):
                    for x in range(cw):
                        r = rng.random()
                        if r < 0.10:
                            s.set_at((x, y), lo)
                        elif r < 0.17:
                            s.set_at((x, y), hi)
                s.fill(hi, (0, 0, cw, 1))
                s.fill(lo, (0, ch - 1, cw, 1))
                if t == ROCK:
                    x = rng.randrange(cw)
                    for y in range(ch // 4, ch * 3 // 4):
                        x = max(0, min(cw - 1, x + rng.choice((-1, 0, 1))))
                        s.set_at((x, y), (40, 40, 48))
                if t in GEM_COL:
                    c, hl, dk = GEM_COL[t]
                    cx, cy = cw // 2, ch // 2
                    r = max(1, (min(cw, ch) - 1) // 2) if t == EMERALD else max(1, min(cw, ch) // 3)
                    for dy in range(-r, r + 1):
                        for dx in range(-r, r + 1):
                            if abs(dx) + abs(dy) <= r:
                                col = hl if dx + dy < -r // 2 else (dk if dx + dy > r // 2 else c)
                                s.set_at((cx + dx, cy + dy), col)
                if t == GOLD:
                    for _ in range(3):
                        gx, gy = rng.randrange(1, max(2, cw - 1)), rng.randrange(1, max(2, ch - 1))
                        s.fill((255, 210, 60), (gx, gy, max(1, cw // 5), max(1, ch // 8)))
                variants.append(s)
            self.tiles[t] = variants

    # ------------------------------------------------------------ world
    def resize(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.grid = [[_pick_tile() for _ in range(cols)] for _ in range(rows)]
        self.var = [[random.randrange(4) for _ in range(cols)] for _ in range(rows)]
        self.surf = pygame.Surface((cols * self.cw, rows * self.ch))
        self.row_key = [None] * rows
        self.pending.clear()
        self._pool = []
        self._scroll_px = 0

    def _new_row(self):
        if len(self._pool) < 48:
            self._pool.append(([_pick_tile() for _ in range(self.cols)], [random.randrange(4) for _ in range(self.cols)]))
            g, v = self._pool[-1]
        else:
            g, v = random.choice(self._pool)
            k = random.randrange(self.cols)
            g, v = g[k:] + g[:k], v[k:] + v[:k]  # rotate: cheap variety
        return list(g), list(v)

    def scrolled(self, n):
        n2 = min(n, self.rows)
        for _ in range(n2):
            self.grid.pop(0)
            self.var.pop(0)
            g, v = self._new_row()
            self.grid.append(g)
            self.var.append(v)
            self.row_key.pop(0)
            self.row_key.append(None)
        self._scroll_px += n2 * self.ch

    def partial_scroll(self, top_v, bot_v, n):
        new = {}
        for (x, vy) in self.pending:
            if top_v <= vy <= bot_v:
                if top_v <= vy - n <= bot_v:
                    new[(x, vy - n)] = self.pending[(x, vy)]
            else:
                new[(x, vy)] = self.pending[(x, vy)]
        self.pending = new
        voff = self.m.voff
        for y in range(max(0, top_v - voff), min(self.rows, bot_v - voff + 1)):
            self.row_key[y] = None

    def row_changed(self, vy):
        y = vy - self.m.voff
        if 0 <= y < self.rows:
            self.row_key[y] = None

    def enqueue(self, x, vy):
        if (x, vy) not in self.pending:
            self.pending[(x, vy)] = time.time()

    def cell_cleared(self, x, vy):
        self.pending.pop((x, vy), None)
        # dirt crumbles back in
        px, py = x * self.cw, vy * self.ch
        n = 5
        self.m.particles.emit(n, px + np.random.uniform(0, self.cw, n).astype(np.float32),
                              py - np.random.uniform(0, self.ch, n).astype(np.float32), vy=20, grav=300,
                              life=0.3, col=(110, 72, 42))

    def reset_pending(self):
        self.pending.clear()
        self.row_key = [None] * self.rows

    # ------------------------------------------------------------ harvesting
    def _harvest(self, x, vy, fly=True, debris=True):
        if self.pending.pop((x, vy), None) is None:
            return False
        cw, ch = self.cw, self.ch
        px, py = x * cw, vy * ch
        self.stats['emerald'] += 1
        y = vy - self.m.voff
        if debris:
            n = 5
            self.m.particles.emit(n, px + np.random.uniform(0, cw, n).astype(np.float32),
                                  py + np.random.uniform(0, ch, n).astype(np.float32),
                                  vx=np.random.uniform(-70, 70, n).astype(np.float32),
                                  vy=np.random.uniform(-110, -20, n).astype(np.float32), grav=500,
                                  life=np.random.uniform(0.25, 0.6, n).astype(np.float32), col=(105, 68, 40))
            n = 4
            self.m.particles.emit(n, px + cw / 2, py + ch / 2, vx=np.random.uniform(-60, 60, n).astype(np.float32),
                                  vy=np.random.uniform(-100, -30, n).astype(np.float32), grav=260,
                                  life=0.5, col=(60, 255, 130), pal=P.SPARKLE, add=True)
        if fly and self._fly_budget > 0:
            self._fly_budget -= 1
            hx = (self.cols - 4) * cw
            hy = self.m.voff * ch + ch / 2
            self.m.particles.emit(1, np.float32(px + cw / 2), np.float32(py + ch / 2), kind=P.HOMING,
                                  tx=np.float32(hx), ty=np.float32(hy), travel=random.uniform(0.45, 0.8),
                                  ease=P.BACK, life=0.85, col=(60, 255, 120), pal=P.SPARKLE, add=True)
        # bonus treasure in the rock around the letter
        if 0 <= y < self.rows and 0 <= x < self.cols:
            t = self.grid[y][x]
            if t in NAMES:
                self.stats[NAMES[t]] += 1
                self.grid[y][x] = DIRT
                if self.sound:
                    self.sound.play('gem', min_gap=0.2, vol=0.8)
        return True

    def _tnt(self):
        keys = list(self.pending)
        self.stats['tnt'] += 1
        for (x, vy) in random.sample(keys, min(6, len(keys))):
            n = 150
            ang = np.random.uniform(0, 6.283, n).astype(np.float32)
            sp = np.random.uniform(40, 320, n).astype(np.float32)
            self.m.particles.emit(n, x * self.cw, vy * self.ch, vx=np.cos(ang) * sp, vy=np.sin(ang) * sp,
                                  drag=1.5, grav=120, life=np.random.uniform(0.4, 1.1, n).astype(np.float32),
                                  pal=P.FIRE, add=True)
        self._fly_budget = 60
        for k in keys:
            self._harvest(*k, debris=False)
        self.shake = 0.6
        self.flash = 1.0
        self.events.append('tnt')
        if self.sound:
            self.sound.play('boom', min_gap=0.4)

    def update(self, dt, mc=None):
        """mc: the MinerCursor (screen space) or None when the cursor is hidden"""
        voff = self.m.voff
        cw, ch = self.cw, self.ch
        now = time.time()
        self._fly_budget = 25
        for k0 in [k for k in self.pending if k[1] < voff]:
            del self.pending[k0]
        backlog = len(self.pending)
        if backlog > 1400:
            self._tnt()
            backlog = 0
        if backlog and mc is not None and mc.x is not None:
            mx = int(round(mc.x / cw))
            my = int(round(mc.y / ch)) + voff
            rx = 2 + min(10, backlog // 15)
            ry = 0 if backlog < 25 else min(3, backlog // 50)
            near = [(x, vy) for (x, vy) in self.pending if abs(vy - my) <= ry and abs(x - mx) <= rx]
            if near:
                tx = min(near, key=lambda c: abs(c[0] - mx) + abs(c[1] - my) * 3)[0]
                mc.strike(-1 if tx < mx else 1, max(0.05, 0.17 / (1 + backlog / 25)))
                if mc.hits:
                    for c in near:
                        self._harvest(*c)
                    if self.sound:
                        self.sound.play('pick', min_gap=0.05, vol=0.6)
        # letters the miner can't reach crumble free on their own
        if self.pending:
            stale = [k for k, t0 in self.pending.items() if now - t0 > 0.6]
            take = max(3, len(stale) // 6)
            for k in stale[:take]:
                self._harvest(*k)
        self.shake *= math.exp(-dt * 5)
        self.flash *= math.exp(-dt * 4)
        # glints on buried emeralds and treasure
        if self.rows and random.random() < 0.5:
            if self.pending and random.random() < 0.7:
                x, vy = random.choice(list(self.pending)[:200])
                y = vy - voff
            else:
                y, x = random.randrange(self.rows), random.randrange(self.cols)
                if self.grid[y][x] not in GEM_COL:
                    return
            self.m.particles.emit(1, x * cw + cw / 2 + random.uniform(-1.5, 1.5), (y + voff) * ch + ch / 2 - 1,
                                  life=0.3, col=(220, 255, 230), pal=P.SPARKLE, add=True)

    # ------------------------------------------------------------ render
    def draw_world(self, surf, ox, oy):
        voff = self.m.voff
        chars = self.screen.chars
        tiles = self.tiles
        pend_rows = {}
        for (x, vy) in self.pending:
            pend_rows.setdefault(vy - voff, set()).add(x)
        cw, ch = self.cw, self.ch
        ws = self.surf
        if self._scroll_px:
            if self._scroll_px < ws.get_height():
                ws.scroll(0, -self._scroll_px)
            self._scroll_px = 0
        for y in range(self.rows):
            rc = chars[y] if y < len(chars) else None
            if rc is None:
                continue
            pr = pend_rows.get(y)
            key = (''.join(rc), frozenset(pr) if pr else None, id(self.grid[y]))
            if key == self.row_key[y]:
                continue
            self.row_key[y] = key
            g, v = self.grid[y], self.var[y]
            for x in range(min(self.cols, len(rc))):
                c = rc[x]
                if pr and x in pr:
                    t = ORE
                else:
                    t = TUNNEL if c != ' ' else g[x]
                ws.blit(tiles[t][v[x]], (x * cw, y * ch))
        surf.blit(ws, (ox, oy))

    def hud(self):
        s = self.stats
        return '◆%d emeralds  ♦%d ●%d $%d  %dm' % (s['emerald'], s['ruby'], s['diamond'], s['gold'],
                                                  self.screen.total_scrolled)
