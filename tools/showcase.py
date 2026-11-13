"""Render a showcase video of pyterm offline (no window needed):

    python tools/showcase.py showcase.mp4      (or .gif)

The zeroday theme is the showrunner: it boots the show (uplink splash, a hack), the other themes take
their turn in between, and zeroday gets the last word (a failed command trips the ICE).
"""
import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from pyterm import themes  # noqa: E402
from pyterm.app import App  # noqa: E402
from pyterm.config import build_config  # noqa: E402
from pyterm.recorder import VideoRecorder  # noqa: E402

FPS = 30


def main(out='showcase.mp4'):
    cfg, args = build_config(['--demo', '-t', 'zeroday', '--size', '1280x720', '--gpu', 'false'])
    cfg['intro'] = True
    app = App(cfg, args)
    rec = VideoRecorder(out, fps=FPS, fixed_step=True, max_width=1280)
    clock = [0.0]

    def run(sec):
        for _ in range(int(sec * FPS)):
            for ev in pygame.event.get():
                app.handle(ev)
            app.frame(1.0 / FPS)
            rec.add(app.presenter.frame_surface())
            clock[0] += 1.0 / FPS
            pygame.time.wait(3)   # let the demo shell thread breathe

    def theme(name):
        app.cfg['background'] = None
        app.cfg['letter_effect'] = app.cfg['delete_effect'] = None
        app.apply_theme(themes.load_theme(name))

    def type_(text, cps=18):
        for c in text:
            app.pane.send(c)
            run(1.0 / cps)
        app.pane.send('\r')

    run(5.6)                      # boot intro: zeroday's uplink splash (5.4 s)
    run(2.5)                      # demo output under the hex rain and the globe
    type_('hack')                 # the showrunner opens the show: packets fly, a node gets rooted
    run(4.5)
    type_('lorem')
    run(2.0)
    for name, cmd in (('emerald_mine', 'lorem'), ('jumpnrun', 'lorem'), ('invaders', 'lorem'), ('walkers', 'lorem'),
                      ('c64', 'boxes'), ('amiga', 'lorem'), ('gameboy', 'info'), ('nes_famicom', 'logo'),
                      ('interlace', 'lorem'), ('vaporwave', 'lorem'), ('inferno', 'error'), ('sandstorm', 'lorem'),
                      ('computerpeople', 'info'), ('trains', 'lorem'), ('settlers', 'info'), ('discocity', 'lorem')):
        theme(name)
        app.pane.send('clear\r')
        run(0.6)
        type_(cmd)
        run(3.5 if name in ('emerald_mine', 'walkers', 'jumpnrun', 'invaders', 'computerpeople', 'trains', 'settlers', 'discocity') else 2.4)
    theme('weather')
    wl = [l for l in app.bg.layers if hasattr(l, 'sim')][0]
    wl.timelapse = 16           # a whole day in 16 seconds
    wl.t = 16 * (7.0 / 24)      # start at dawn
    for cond, secs in (('clear', 4.0), ('rain', 4.0), ('storm', 4.0), ('snow', 4.0)):
        wl.sim = cond
        for k, v in wl.target().items():
            wl.cur[k] = v
        if cond == 'snow':
            wl.snow_cover = 0.8
        if cond == 'clear':
            app.pane.send('clear\r')
            run(0.3)
            type_('weather')
        run(secs)
    theme('dos')
    app.pane.send('clear\r')
    run(0.5)
    type_('emoji')
    run(2.5)
    type_('animfont')
    run(2.5)
    type_('font builtin')
    run(0.5)
    theme('shadebobs')
    app.split('v')
    run(0.5)
    type_('image')
    run(1.5)
    app.split('h')
    run(0.5)
    type_('flood')
    run(3.0)
    while len(app.all_panes()) > 1:   # close the splits again: the showrunner gets the whole window
        app.close_pane()
        run(0.3)
    theme('zeroday')              # the showrunner has the last word
    app.pane.send('clear\r')
    run(0.6)
    type_('hack')
    run(3.5)
    type_('error')                # a failing command trips the ICE: counter-traces, torn picture, TRACE meter
    run(4.0)
    print('frames', rec.count, '->', rec.stop())
    pygame.quit()


if __name__ == '__main__':
    main(*(sys.argv[1:2] or ['showcase.mp4']))
