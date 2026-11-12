"""Clipboard keys and right click: Shift+Insert / Ctrl+Insert and right click must reach pyterm's clipboard
instead of leaking to the program as escape sequences (pytermwm / bash showed '2~').

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


class ClipboardKeys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        appmod.App._demo_used = True
        cfg, args = build_config(['--demo', '--size', '800x480', '--gpu', 'false', '--no-sound'])
        cfg['intro'] = False
        cls.app = appmod.App(cfg, args)
        cls.app.frame(1 / 30)

    def setUp(self):
        self.clip = ['CLIP']
        self._get, self._put = appmod.clip_get, appmod.clip_put
        appmod.clip_get = lambda: self.clip[0]
        appmod.clip_put = lambda t: self.clip.__setitem__(0, t)
        pane = self.app.pane
        self.sent = []
        self.pasted = []
        self._send, self._paste, self._write = pane.send, pane.paste_text, pane.backend.write
        pane.send = self.sent.append
        pane.paste_text = self.pasted.append
        pane.backend.write = self.sent.append
        pane.screen.mouse_mode = 0
        self.app.cfg['right_click'] = 'copy-paste'
        self.app.cfg['insert_keys'] = True

    def tearDown(self):
        appmod.clip_get, appmod.clip_put = self._get, self._put
        pane = self.app.pane
        pane.send, pane.paste_text, pane.backend.write = self._send, self._paste, self._write
        pane.screen.mouse_mode = 0
        pane.sel = None
        pygame.key.set_mods(0)

    def key(self, k, mod):
        self.app.on_key(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode='', scancode=0))

    def click(self, button=3):
        for t in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            self.app.handle(pygame.event.Event(t, button=button, pos=(200, 200)))

    def test_shift_insert_pastes(self):
        self.key(pygame.K_INSERT, pygame.KMOD_LSHIFT)
        self.assertEqual(self.pasted, ['CLIP'])
        self.assertEqual(self.sent, [])

    def test_ctrl_insert_copies_selection(self):
        pane = self.app.pane
        pane.selection_text = lambda: 'selected'
        try:
            self.key(pygame.K_INSERT, pygame.KMOD_LCTRL)
        finally:
            del pane.selection_text
        self.assertEqual(self.clip[0], 'selected')
        self.assertEqual(self.sent, [])

    def test_insert_keys_off_sends_sequence(self):
        self.app.cfg['insert_keys'] = False
        self.key(pygame.K_INSERT, pygame.KMOD_LSHIFT)
        self.assertEqual(self.sent, ['\x1b[2;2~'])

    def test_right_click_pastes(self):
        self.click()
        self.assertEqual(self.pasted, ['CLIP'])

    def test_right_click_goes_to_mouse_programs(self):
        self.app.pane.screen.mouse_mode = 1002
        self.click()
        self.assertEqual(self.pasted, [])
        self.assertEqual(len(self.sent), 2)                 # press + release

    def test_shift_right_click_is_ours_without_release_leak(self):
        self.app.pane.screen.mouse_mode = 1002
        pygame.key.set_mods(pygame.KMOD_LSHIFT)
        self.click()
        self.assertEqual(self.pasted, ['CLIP'])
        self.assertEqual(self.sent, [])                     # no orphan release for the program

    def test_right_click_always(self):
        self.app.pane.screen.mouse_mode = 1002
        self.app.cfg['right_click'] = 'always'
        self.click()
        self.assertEqual(self.pasted, ['CLIP'])
        self.assertEqual(self.sent, [])


class Osc52Queries(unittest.TestCase):
    """Programs asking for the clipboard (OSC 52 ; c ; ?) always get an answer, the content only when allowed."""

    def setUp(self):
        self.app = ClipboardKeys.app if hasattr(ClipboardKeys, 'app') else None
        if self.app is None:
            ClipboardKeys.setUpClass()
            self.app = ClipboardKeys.app
        self.pane = self.app.pane
        self.out = []
        self._write, self._get = self.pane.backend.write, appmod.clip_get
        self.pane.backend.write = self.out.append
        appmod.clip_get = lambda: 'secret'

    def tearDown(self):
        self.pane.backend.write, appmod.clip_get = self._write, self._get
        self.app.cfg['osc52'] = 'write'

    def ask(self, mode):
        self.app.cfg['osc52'] = mode
        self.pane.screen.clip_ops.append(('get', 'c'))
        self.pane._clipboard_ops(self.pane.screen)
        return self.out[-1]

    def test_default_answers_empty(self):
        self.assertEqual(self.ask('write'), '\x1b]52;c;\x1b\\')

    def test_read_write_answers_with_the_clipboard(self):
        self.assertEqual(self.ask('read-write'), '\x1b]52;c;c2VjcmV0\x1b\\')


if __name__ == '__main__':
    unittest.main()
