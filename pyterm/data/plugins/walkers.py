"""WALKERS - a horde of tiny critters that drop out of a hatch and stroll over
your terminal *text*: letters are the landscape. They walk along lines, climb
small steps, fall off line ends (umbrellas open on long drops), and now and
then a critter gets a job: BLOCKER, BUILDER (lays a brick staircase) or
EXPLODER (5..4..3..2..1.. poof). A failed command makes one of them explode,
a successful one makes them cheer. Reaching the exit door saves them.

Enable:  theme -> plugins: {walkers: {enabled: true}}   or Ctrl+Shift+N
"""
import math
import random

import numpy as np
import pygame

PLUGIN = {'name': 'walkers', 'description': 'tiny critters walk over your terminal text (Ctrl+Shift+N)'}

PAL = {'H': (255, 150, 40), 'S': (250, 205, 165), 'T': (40, 205, 185), 'L': (50, 90, 170), 'K': (70, 45, 30)}
SPR = {
    'walk1': [".HH..", "HHS..", ".SS..", ".TT..", "TTTT.", ".TT..", ".LL..", ".KK.."],
    'walk2': [".HH..", "HHS..", ".SS..", ".TT..", ".TTT.", ".TT..", "L..L.", "K..K."],
    'fall':  [".HH..", "THST.", "TSST.", ".TT..", ".TT..", ".TT..", "L..L.", "K..K."],
    'block': [".HH..", "HHS..", ".SS..", "TTTTT", ".TT..", ".TT..", "L..L.", "K..K."],
    'build': ["..HH.", ".HHS.", "..SS.", ".TTT.", "TTTT.", ".TTL.", ".LLK.", ".K..."],
    'cheer': ["T.HT.", "THHT.", ".SS..", ".TT..", ".TT..", ".TT..", "L..L.", "K..K."],
}
S = {'on': None, 'pane': None, 'walkers': [], 'bricks': None, 'saved': 0, 'lost': 0, 'spawn': 0.0,
     'dt': 0.0, 'job': 3.0, 'size': None, 'cheer': 0.0, 'cache': {}}


def sprite(name, face, k):
    key = (name, face, k)
    img = S['cache'].get(key)
    if img is None:
        rows = SPR[name]
        img = pygame.Surface((5, 8), pygame.SRCALPHA)
        img.fill((0, 0, 0, 0))
        for y, r in enumerate(rows):
            for x, c in enumerate(r):
                if c in PAL:
                    img.set_at((x, y), PAL[c])
        if face < 0:
            img = pygame.transform.flip(img, True, False)
        if k > 1:
            img = pygame.transform.scale(img, (5 * k, 8 * k))
        S['cache'][key] = img
    return img


class Walker:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.dir = 1
        self.state = 'fall'
        self.vy = 0.0
        self.fallen = 0.0
        self.t = 0.0
        self.job_t = 0.0
        self.bricks = 0
        self.umbrella = False
        self.dead = False


def register(api):
    def enabled():
        return S['on'] if S['on'] is not None else bool(api.settings.get('enabled'))

    def frame(dt):
        S['dt'] = dt
        api.animating(enabled())

    def reset(pane):
        S['pane'] = pane
        S['walkers'] = []
        r = pane.rect
        S['size'] = r.size
        S['bricks'] = np.zeros(r.size, bool)
        S['brick_surf'] = None
        S['tot'] = pane.screen.total_scrolled

    def draw(surf, rect):
        if not enabled():
            return
        pane = api.app.pane
        if S['pane'] is not pane or S['size'] != pane.rect.size:
            reset(pane)
        dt = min(0.05, S['dt'])
        k = max(1, api.cell[1] // 10)
        r = pane.rect
        W, H = r.size
        yoff = int(round(pane.yoff))
        try:
            alpha = pygame.surfarray.pixels_alpha(pane.renderer.tsurf)
        except Exception:
            return
        bricks = S['bricks']

        # ride along when the text scrolls
        tot = pane.screen.total_scrolled
        d = tot - S.get('tot', tot)
        S['tot'] = tot
        if d:
            dy = d * api.cell[1]
            for w in S['walkers']:
                w.y -= dy
            if dy < H:
                bricks[:, :H - dy] = bricks[:, dy:].copy()
                bricks[:, H - dy:] = False
            else:
                bricks[:] = False
            S['brick_surf'] = None
            S['walkers'] = [w for w in S['walkers'] if w.y > 0]

        def solid(x, y):
            xi, yi = int(x), int(y)
            if yi >= H - 1 or xi < 0 or xi >= W:
                return True
            if yi < 0:
                return False
            ty = yi - yoff
            if 0 <= ty < H and alpha[xi, ty] > 40:
                return True
            return bool(bricks[xi, yi])

        # spawn
        S['spawn'] -= dt
        maxn = int(api.settings.get('max', 18))
        if S['spawn'] <= 0 and len(S['walkers']) < maxn:
            S['spawn'] = float(api.settings.get('spawn_every', 2.2))
            S['walkers'].append(Walker(14 * k, 6 * k))
        # jobs
        S['job'] -= dt
        idle = [w for w in S['walkers'] if w.state == 'walk']
        if S['job'] <= 0 and idle:
            S['job'] = random.uniform(3, 7)
            w = random.choice(idle)
            job = random.choices(['block', 'build', 'boom'], [2, 4, 1])[0]
            if job == 'block' and sum(1 for x in S['walkers'] if x.state == 'block') >= 2:
                job = 'build'
            w.state = job
            w.job_t = 0.0
            w.bricks = 0
        exit_x = W - 12 * k
        S['cheer'] = max(0.0, S['cheer'] - dt)
        blockers = [w for w in S['walkers'] if w.state == 'block']
        step_max = 3 * k
        for w in S['walkers']:
            w.t += dt
            w.job_t += dt
            if w.state == 'fall':
                w.vy = min(w.vy + 400 * dt, 30 * k if w.umbrella else 160 * k)
                dy = w.vy * dt
                w.fallen += dy
                if w.fallen > 40 * k:
                    w.umbrella = True
                steps = int(math.ceil(dy))
                for _ in range(max(1, steps)):
                    if solid(w.x + 2 * k, w.y + 1):
                        if w.fallen > 70 * k and not w.umbrella:
                            w.dead = True
                            splat(w, r)
                        else:
                            w.state = 'walk'
                        w.vy = 0
                        w.fallen = 0
                        w.umbrella = False
                        break
                    w.y += 1
                if w.y > H + 20:
                    w.dead = True
                continue
            if w.state == 'block':
                if w.job_t > 9:
                    w.state = 'walk'
                continue
            if w.state == 'boom':
                if w.job_t > 5:
                    w.dead = True
                    explode(w, r, bricks)
                continue
            if not solid(w.x + 2 * k, w.y + 1) and not solid(w.x + 2 * k, w.y + 2):
                w.state = 'fall'
                continue
            if w.state == 'build':
                if w.job_t > 0.45:
                    w.job_t = 0
                    bx = int(w.x + (2 * k if w.dir > 0 else -2 * k) + 2 * k)
                    by = int(w.y)
                    for xx in range(bx - 2 * k, bx + 2 * k):
                        if 0 <= xx < W and 0 <= by < H:
                            bricks[xx, by] = True
                    S['brick_surf'] = None
                    w.y -= 1
                    w.x += w.dir * 2 * k
                    w.bricks += 1
                    if w.bricks >= 10 or solid(w.x + 2 * k + w.dir * 3 * k, w.y - 4 * k):
                        w.state = 'walk'
                continue
            # walking
            sp = 14 * k * dt
            nx = w.x + w.dir * sp
            fx = nx + 2 * k + w.dir * 2 * k
            turn = False
            for b in blockers:
                if b is not w and abs(b.x - nx) < 4 * k and abs(b.y - w.y) < 6 * k and (b.x - w.x) * w.dir > 0:
                    turn = True
            if not turn and solid(fx, w.y):
                up = next((u for u in range(1, step_max + 1) if not solid(fx, w.y - u)), None)
                if up is None:
                    turn = True
                else:
                    w.y -= up
            if turn:
                w.dir = -w.dir
                continue
            w.x = nx
            if not solid(w.x + 2 * k, w.y + 1):
                down = next((d for d in range(1, step_max + 1) if solid(w.x + 2 * k, w.y + d + 1)), None)
                if down is not None:
                    w.y += down
            if w.y >= H - 2 and w.x >= exit_x:
                w.dead = True
                S['saved'] += 1
                api.particles.emit(8, np.float32(w.x + 2 * k), np.float32(w.y - 4 * k + api.app.fx.voff * api.cell[1]),
                                   vy=-40, vx=np.random.uniform(-20, 20, 8).astype(np.float32), life=0.6,
                                   col=(255, 255, 160), pal=3, add=True)
        alpha = None  # release the surface lock
        S['walkers'] = [w for w in S['walkers'] if not w.dead]
        ox, oy = r.x, r.y
        # bricks
        if bricks.any():
            if S.get('brick_surf') is None:
                bs = pygame.Surface((W, H), pygame.SRCALPHA)
                rgb = pygame.surfarray.pixels3d(bs)
                rgb[bricks] = (200, 110, 50)
                del rgb
                a = pygame.surfarray.pixels_alpha(bs)
                a[:] = bricks * 255
                del a
                S['brick_surf'] = bs
            surf.blit(S['brick_surf'], (ox, oy))
        # hatch & exit
        surf.fill((90, 60, 40), (ox + 8 * k, r.y + 2 * k, 14 * k, 3 * k))
        surf.fill((40, 25, 15), (ox + 10 * k, r.y + 5 * k, 10 * k, k))
        door = pygame.Rect(ox + exit_x, r.bottom - 10 * k, 9 * k, 10 * k)
        surf.fill((120, 70, 30), door)
        surf.fill((255, 200, 60) if int(api.app.t * 3) % 2 else (200, 140, 30), door.inflate(-4 * k, -4 * k).move(0, 2 * k))
        for w in S['walkers']:
            name = {'fall': 'fall', 'block': 'block', 'build': 'build'}.get(w.state)
            if name is None:
                name = 'cheer' if S['cheer'] > 0 else ('walk1' if int(w.t * 8) % 2 else 'walk2')
            img = sprite(name, w.dir, k)
            x, y = int(ox + w.x), int(oy + w.y - 8 * k + 1)
            surf.blit(img, (x, y))
            if w.umbrella:
                pygame.draw.arc(surf, (255, 80, 120), (x - 2 * k, y - 4 * k, 9 * k, 6 * k), 0, math.pi, k)
                surf.fill((220, 220, 220), (x + 2 * k, y - 2 * k, k, 3 * k))
            if w.state == 'boom':
                n = 5 - int(w.job_t)
                api.draw_text(surf, x, y - api.cell[1], str(max(1, n)), (255, 255, 255))
        t = 'OUT %d  IN %d  LOST %d' % (len(S['walkers']), S['saved'], S['lost'])
        api.draw_text(surf, r.right - (len(t) + 1) * api.cell[0], r.y, t, (140, 255, 140))

    def splat(w, r):
        S['lost'] += 1
        k = max(1, api.cell[1] // 10)
        n = 14
        api.particles.emit(n, np.float32(w.x + 2 * k), np.float32(w.y + api.app.fx.voff * api.cell[1] - 2),
                           vx=np.random.uniform(-50, 50, n).astype(np.float32),
                           vy=np.random.uniform(-80, -10, n).astype(np.float32), grav=300, life=0.6,
                           col=(40, 205, 185), pal=2)

    def explode(w, r, bricks):
        S['lost'] += 1
        k = max(1, api.cell[1] // 10)
        cx, cy = int(w.x + 2 * k), int(w.y - 4 * k)
        rad = 9 * k
        x0, x1 = max(0, cx - rad), min(bricks.shape[0], cx + rad)
        y0, y1 = max(0, cy - rad), min(bricks.shape[1], cy + rad)
        if x1 > x0 and y1 > y0:
            xx, yy = np.mgrid[x0:x1, y0:y1]
            bricks[x0:x1, y0:y1] &= (xx - cx) ** 2 + (yy - cy) ** 2 > rad * rad
            S['brick_surf'] = None
        n = 60
        ang = np.random.uniform(0, 6.283, n).astype(np.float32)
        sp = np.random.uniform(30, 160, n).astype(np.float32)
        api.particles.emit(n, np.float32(cx), np.float32(cy + api.app.fx.voff * api.cell[1]), vx=np.cos(ang) * sp,
                           vy=np.sin(ang) * sp, grav=200, drag=1, life=np.random.uniform(0.3, 0.9, n).astype(np.float32),
                           pal=1, add=True)
        api.app.sound.play('break', min_gap=0.1)

    def command_done(code, secs, cmd):
        if not enabled():
            return
        if code:
            walking = [w for w in S['walkers'] if w.state == 'walk']
            if walking:
                w = random.choice(walking)
                w.state = 'boom'
                w.job_t = 0.0
        else:
            S['cheer'] = 1.5

    def toggle():
        S['on'] = not enabled()
        api.notify('walkers %s' % ('ON - let\'s go!' if S['on'] else 'off'))

    api.on('frame', frame)
    api.on('draw', draw)
    api.on('command_done', command_done)
    api.add_hotkey('n', toggle, 'walkers')
