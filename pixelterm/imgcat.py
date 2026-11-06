"""Show an image inside pixelterm (or any sixel / kitty / iTerm2 capable terminal).

    python -m pixelterm.imgcat picture.png              # kitty protocol (default)
    python -m pixelterm.imgcat picture.png --sixel
    python -m pixelterm.imgcat picture.png --iterm --width 40
"""
import argparse
import io
import os
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog='imgcat')
    ap.add_argument('files', nargs='+')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--sixel', action='store_true')
    g.add_argument('--iterm', action='store_true')
    ap.add_argument('--width', type=int, help='width in cells')
    a = ap.parse_args(argv)
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
    import pygame
    pygame.init()
    from . import images
    out = sys.stdout
    for f in a.files:
        with open(f, 'rb') as fh:
            raw = fh.read()
        if a.sixel:
            surf = pygame.image.load(io.BytesIO(raw), f)
            if a.width:
                k = a.width * 10 / surf.get_width()
                surf = pygame.transform.smoothscale(surf, (int(surf.get_width() * k), int(surf.get_height() * k)))
            out.write(images.encode_sixel(surf))
        elif a.iterm:
            out.write(images.encode_iterm(raw, os.path.basename(f), a.width))
        else:
            if not f.lower().endswith('.png'):
                surf = pygame.image.load(io.BytesIO(raw), f)
                buf = io.BytesIO()
                pygame.image.save(surf, buf, 'x.png')
                raw = buf.getvalue()
            out.write(images.encode_kitty(raw, cols=a.width))
        out.write('\n')
    out.flush()


if __name__ == '__main__':
    main()
