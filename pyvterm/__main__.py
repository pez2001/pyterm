import os
import sys


def main(argv=None):
    from .config import build_config
    cfg, args = build_config(argv)
    if args.benchmark:
        os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
        os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
        from .bench import run_benchmark
        return run_benchmark(cfg, args)
    if args.screenshot:
        os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    import pygame  # noqa
    if args.list:
        pygame.init()
        from . import backgrounds, cursors, effects, fonts, themes
        print('themes     :', ', '.join(themes.list_themes()))
        print('letter fx  :', ', '.join(effects.APPEAR))
        print('delete fx  :', ', '.join(effects.VANISH))
        print('cursors    :', ', '.join(cursors.CURSORS))
        print('cursor fx  :', ', '.join(cursors.CURSOR_EFFECTS))
        from . import splash
        print('splashes   :', ', '.join(splash.SPLASHES))
        print('backgrounds:', ', '.join(backgrounds.BACKGROUNDS), '(+ mine via --miner)')
        print('fonts      :', ', '.join(fonts.list_fonts()))
        return 0
    if args.export_font:
        pygame.init()
        pygame.display.set_mode((1, 1), pygame.HIDDEN) if hasattr(pygame, 'HIDDEN') else None
        from . import fonts
        f = fonts.load_font(cfg.get('font') or 'builtin', cfg.get('font_size') or 18, cfg.get('antialias') is not False)
        pf = fonts.PixelFont.from_font(f)
        name = os.path.splitext(os.path.basename(args.export_font))[0]
        p = pf.save(name)
        print('exported %s (+ %s.png) - edit the PNG, then run with --font %s' % (p, name, os.path.relpath(p)))
        return 0
    from .app import App
    App(cfg, args).run()
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
