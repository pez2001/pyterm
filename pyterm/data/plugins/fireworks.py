"""Fireworks! Ctrl+Shift+K, the Konami code (up up down down left right left
right b a), or automatically when a command prints 'success' / 'passed'."""
import random
import re

import numpy as np

PLUGIN = {'name': 'fireworks', 'description': 'fireworks: Ctrl+Shift+K, konami code, success output, long commands'}

KONAMI = ['up', 'up', 'down', 'down', 'left', 'right', 'left', 'right', 'b', 'a']
S = {'keys': [], 'rockets': [], 'cool': 0.0}
OK = re.compile(r'(?i)\b(all tests passed|success(fully)?|build succeeded|\d+ passed)\b')


def register(api):
    import pygame
    from pyterm import particles as P

    def launch(n=5):
        cw, ch = api.cell
        cols, rows = api.screen.cols, api.screen.rows
        for _ in range(n):
            S['rockets'].append([random.uniform(0.1, 0.9) * cols * cw, rows * ch, random.uniform(-40, 40),
                                 random.uniform(-420, -300), random.uniform(0.6, 1.1)])

    def frame(dt):
        S['cool'] = max(0, S['cool'] - dt)
        api.animating(bool(S['rockets']))
        fx = api.app.fx
        voff = fx.voff * api.cell[1]
        keep = []
        for r in S['rockets']:
            r[0] += r[2] * dt
            r[1] += r[3] * dt
            r[3] += 260 * dt
            r[4] -= dt
            api.particles.emit(2, np.float32(r[0]), np.float32(r[1] + voff), vy=40, life=0.3, pal=P.FIRE, add=True)
            if r[4] <= 0:
                n = 220
                ang = np.random.uniform(0, 6.283, n).astype(np.float32)
                sp = np.random.uniform(30, 190, n).astype(np.float32)
                col = random.choice([(255, 80, 80), (80, 255, 120), (90, 160, 255), (255, 220, 60), (255, 90, 255)])
                api.particles.emit(n, np.float32(r[0]), np.float32(r[1] + voff), vx=np.cos(ang) * sp,
                                   vy=np.sin(ang) * sp, grav=90, drag=1.2,
                                   life=np.random.uniform(0.6, 1.4, n).astype(np.float32),
                                   col=col, pal=P.SPARKLE if random.random() < 0.5 else P.FADE, add=True)
                api.app.sound.play('break', min_gap=0.05, vol=0.5)
            else:
                keep.append(r)
        S['rockets'] = keep

    def key(ev):
        S['keys'] = (S['keys'] + [pygame.key.name(ev.key)])[-10:]
        if S['keys'] == KONAMI:
            S['keys'] = []
            launch(12)
            api.notify('+30 lives')
        return False

    def output(text):
        if S['cool'] <= 0 and OK.search(text):
            S['cool'] = 5
            launch(4)
        return text

    def command_done(exit_code, seconds, cmdline):
        # long-running command finished successfully -> celebrate
        if exit_code == 0 and seconds >= 10:
            launch(5)

    api.on('command_done', command_done)
    api.on('frame', frame)
    api.on('key', key)
    api.on('output', output)
    api.add_hotkey('k', lambda: launch(6), 'fireworks')
