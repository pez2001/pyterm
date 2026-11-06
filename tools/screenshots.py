"""Render README screenshots offline (no window needed):

    python tools/screenshots.py docs/media
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

FPS = 30
# (file name, theme, demo command, seconds to let it run after typing)
SHOTS = [
    ('neon', 'neon', 'lorem', 3.0),
    ('c64', 'c64', 'boxes', 2.5),
    ('amiga', 'amiga', 'lorem', 2.5),
    ('emerald_mine', 'emerald_mine', 'lorem', 5.0),
    ('vaporwave', 'vaporwave', 'lorem', 3.0),
    ('inferno', 'inferno', 'error', 3.0),
    ('gameboy', 'gameboy', 'info', 2.5),
    ('weather', 'weather', 'weather', 5.0),
]


def main(outdir='docs/media', only=None):
    os.makedirs(outdir, exist_ok=True)
    cfg, args = build_config(['--demo', '-t', 'neon', '--size', '1280x720', '--gpu', 'false'])
    cfg['intro'] = False
    App._demo_used = True
    app = App(cfg, args)

    def run(sec):
        for _ in range(int(sec * FPS)):
            for ev in pygame.event.get():
                app.handle(ev)
            app.frame(1.0 / FPS)
            pygame.time.wait(3)

    run(2.0)
    for fname, theme, cmd, secs in SHOTS:
        if only and fname not in only:
            continue
        app.cfg['background'] = None
        app.cfg['letter_effect'] = app.cfg['delete_effect'] = None
        app.apply_theme(themes.load_theme(theme))
        app.pane.send('clear\r')
        run(0.6)
        for c in cmd:
            app.pane.send(c)
            run(1 / 18)
        app.pane.send('\r')
        run(secs)
        path = os.path.join(outdir, fname + '.png')
        pygame.image.save(app.presenter.frame_surface(), path)
        print('saved', path)
    pygame.quit()


if __name__ == '__main__':
    main(*(sys.argv[1:2] or ['docs/media']))
