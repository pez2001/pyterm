"""Headless benchmark:  python pyvterm.py --benchmark [-t theme]"""
from __future__ import annotations

import random
import time

import pygame


def _sample(n_lines=4000):
    words = 'lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor'.split()
    out = []
    for i in range(n_lines):
        c = 31 + i % 7
        out.append('\x1b[%dm%05d\x1b[0m %s \x1b[38;2;%d;%d;%dm%s\x1b[0m\r\n' % (
            c, i, ' '.join(random.choice(words) for _ in range(8)), i % 255, 128, 255 - i % 255, '█▓▒░' * 3))
    return ''.join(out)


def run_benchmark(cfg, args):
    from . import vt
    data = _sample()
    print('pyvterm benchmark - %.1f KB of colored output' % (len(data) / 1024))
    s = vt.Screen(120, 40)
    s.record = False
    p = vt.Parser(s)
    t = time.perf_counter()
    p.feed(data)
    dt = time.perf_counter() - t
    print('  parser (no events)     : %7.2f MB/s' % (len(data) / dt / 1e6))
    s = vt.Screen(120, 40)
    p = vt.Parser(s)
    t = time.perf_counter()
    for i in range(0, len(data), 8192):
        p.feed(data[i:i + 8192])
        s.take_events()
    dt = time.perf_counter() - t
    print('  parser (+ fx events)   : %7.2f MB/s' % (len(data) / dt / 1e6))

    from .app import App
    cfg = dict(cfg)
    cfg['intro'] = False
    cfg['sound'] = False
    for theme in ([cfg['theme']] if args.theme else ['neon', 'emerald_mine', 'inferno', 'zen']):
        cfg['theme'] = theme
        cfg['writer'] = 'smart'
        app = App(cfg, args)
        res = {}
        for label, text in (('idle', ''), ('typing', 'hello world, this is a typing test. ' * 3),
                            ('flood', data)):
            app.inject(text)
            frames = 0
            t0 = time.perf_counter()
            worst = 0.0
            while frames < 240:
                a = time.perf_counter()
                app.frame(1 / 60)
                worst = max(worst, time.perf_counter() - a)
                frames += 1
                if label == "flood" and not app.pane.pending and frames > 30:
                    break
            el = time.perf_counter() - t0
            res[label] = (el / frames * 1000, worst * 1000, frames)
        print('  theme %-13s idle %5.1f ms | typing %5.1f ms | flood %5.1f ms avg, %5.1f worst (%d frames) | %dx%d' % (
            theme, res['idle'][0], res['typing'][0], res['flood'][0], res['flood'][1], res['flood'][2],
            app.screen.cols, app.screen.rows))
        app.backend.close()
    pygame.quit()
    return 0
