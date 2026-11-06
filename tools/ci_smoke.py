"""Headless smoke test for CI: boots the app with the demo shell and renders frames."""
import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import pygame  # noqa: E402
from pixelterm.app import App  # noqa: E402
from pixelterm.config import build_config  # noqa: E402


def main():
    themes = sys.argv[1:] or [None]
    for theme in themes:
        argv = ['--demo', '--gpu', 'false', '--size', '800x480']
        if theme:
            argv += ['-t', theme]
        App._demo_used = True
        built = build_config(argv)
        cfg = built[0]
        cfg['intro'] = False
        app = App(*built)
        for _ in range(30):
            app.frame(1 / 30)
        surf = app.presenter.frame_surface()
        assert surf.get_width() > 0 and surf.get_height() > 0
        print('ok', theme or 'default', surf.get_size())
    pygame.quit()


if __name__ == '__main__':
    main()
