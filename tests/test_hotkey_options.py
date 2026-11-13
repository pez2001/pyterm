"""Hotkey options: Alt+Enter fullscreen can be turned off (pytermwm uses Alt+Enter), and built-in hotkeys can be
handed to the program with disabled_hotkeys.

    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from pyterm import app as appmod  # noqa: E402
from pyterm.config import build_config  # noqa: E402

CS = pygame.KMOD_LCTRL | pygame.KMOD_LSHIFT


def make_app(*flags):
    appmod.App._demo_used = True
    cfg, args = build_config(['--demo', '--size', '800x480', '--gpu', 'false', '--no-sound'] + list(flags))
    cfg['intro'] = False
    app = appmod.App(cfg, args)
    app.intro = None
    app.frame(1 / 30)
    return app


def key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode='')


class HotkeyOptions(unittest.TestCase):
    def test_defaults_keep_current_behaviour(self):
        cfg, _ = build_config(['--demo'])
        # the bundled config.yaml turns Alt+Enter off; everything else stays on
        self.assertIn('alt_enter_fullscreen', cfg)
        self.assertEqual(cfg['disabled_hotkeys'], [])
        self.assertTrue(cfg['ctrl_click_urls'] and cfg['middle_click_paste'] and cfg['copy_on_select'])

    def test_alt_enter_fullscreen_option(self):
        app = make_app()
        app.cfg['alt_enter_fullscreen'] = True
        fs = app.presenter.fullscreen
        app.on_key(key(pygame.K_RETURN, pygame.KMOD_LALT))
        self.assertNotEqual(app.presenter.fullscreen, fs, 'Alt+Enter toggles fullscreen when enabled')
        app.cfg['alt_enter_fullscreen'] = False
        fs = app.presenter.fullscreen
        app.on_key(key(pygame.K_RETURN, pygame.KMOD_LALT))
        self.assertEqual(app.presenter.fullscreen, fs, 'Alt+Enter is left alone when disabled')
        app.on_key(key(pygame.K_F11))
        self.assertNotEqual(app.presenter.fullscreen, fs, 'F11 always toggles fullscreen')

    def test_no_alt_enter_flag(self):
        cfg, _ = build_config(['--demo', '--no-alt-enter'])
        self.assertFalse(cfg['alt_enter_fullscreen'])

    def test_disabled_hotkeys(self):
        app = make_app('--disable-hotkeys', 'ctrl+shift+t')
        self.assertTrue(app.hk_off('ctrl+shift+t'))
        self.assertFalse(app.hk_off('ctrl_tab'))
        n = len(app.tabs)
        app.on_key(key(pygame.K_t, CS))
        self.assertEqual(len(app.tabs), n, 'disabled hotkey does not open a tab')
        app.cfg['disabled_hotkeys'] = []
        app.on_key(key(pygame.K_t, CS))
        self.assertEqual(len(app.tabs), n + 1, 'enabled hotkey opens a tab')

    def test_disabled_hotkeys_accepts_list_and_string(self):
        app = make_app()
        app.cfg['disabled_hotkeys'] = ['Alt_Arrows', ' ctrl_tab ']
        self.assertTrue(app.hk_off('alt_arrows') and app.hk_off('ctrl_tab'))
        app.cfg['disabled_hotkeys'] = 'shift_pgup, ctrl_pgup_pgdn'
        self.assertTrue(app.hk_off('shift_pgup') and app.hk_off('ctrl_pgup_pgdn'))
        self.assertFalse(app.hk_off('alt_arrows'))

    def test_mouse_option_flags(self):
        cfg, _ = build_config(['--demo', '--no-ctrl-click', '--no-middle-paste', '--no-copy-on-select'])
        self.assertFalse(cfg['ctrl_click_urls'] or cfg['middle_click_paste'] or cfg['copy_on_select'])


if __name__ == '__main__':
    unittest.main()
