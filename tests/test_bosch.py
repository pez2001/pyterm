"""The bosch scene and theme: registered, loads, survives odd window sizes, parameters and terminal events.

    python -m unittest discover -s tests -v
"""
import os
import sys
import time
import unittest

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from pyterm import backgrounds, signals, themes  # noqa: E402


class BoschTests(unittest.TestCase):
    def test_registered_and_theme_loads(self):
        self.assertIn('bosch', backgrounds.BACKGROUNDS)
        th = themes.load_theme('bosch')
        self.assertEqual(th['name'], 'bosch')
        self.assertEqual(list(th['background']), ['bosch'])

    def test_draws_at_odd_sizes(self):
        for w, h in ((1280, 800), (640, 400), (317, 201), (200, 120), (48, 32), (1920, 1080)):
            b = backgrounds.BACKGROUNDS['bosch'](w, h, {'bosch': {}})
            surf = pygame.Surface((w, h))
            for _ in range(5):
                b.update(1 / 30, 0.5)
                b.draw(surf, True)
            self.assertEqual(surf.get_size(), (w, h))
            self.assertNotEqual(surf.get_at((w // 2, h // 2))[:3], (0, 0, 0), 'something is painted at %dx%d' % (w, h))

    def test_params(self):
        b = backgrounds.BACKGROUNDS['bosch'](640, 400, {'bosch': {'riders': 0, 'souls': False, 'speed': 2.0, 'fire': 0.0}})
        surf = pygame.Surface((640, 400))
        for _ in range(10):
            b.update(1 / 30, 0)
            b.draw(surf, True)
        self.assertEqual(len(b.riders), 0)
        self.assertEqual(len(b.souls), 0)

    def test_reacts_to_the_terminal(self):
        b = backgrounds.BACKGROUNDS['bosch'](640, 400, {'bosch': {}})
        surf = pygame.Surface((640, 400))
        b.update(1 / 30, 0)
        signals.letter_seq += 1
        signals.letters.append((signals.letter_seq, 'a', 100, 100, True))
        b.update(1 / 30, 0)
        self.assertGreaterEqual(len(b.souls), 1, 'a typed letter releases a soul')
        signals.cmd = (1, 0.1, time.time())
        b.update(1 / 30, 0)
        self.assertGreater(b.boost, 0.5, 'a failed command makes hell flare up')
        signals.cmd = (0, 0.1, time.time())
        b.update(1 / 30, 0)
        self.assertGreater(b.surge, 0.5, 'a command that works makes the fountain surge')
        signals.bell = time.time()
        b.update(1 / 30, 0)
        self.assertGreater(b.owl_wide, 0, 'the bell wakes the owl')
        for _ in range(60):
            b.update(1 / 30, 1.5)
            b.draw(surf, True)

    def test_everything_moves(self):
        b = backgrounds.BACKGROUNDS['bosch'](640, 400, {'bosch': {}})
        surf = pygame.Surface((640, 400))
        b.draw(surf, True)
        a = pygame.image.tostring(surf, 'RGB')
        for _ in range(90):
            b.update(1 / 30, 0)
        b.draw(surf, True)
        self.assertNotEqual(a, pygame.image.tostring(surf, 'RGB'), 'the painting is alive')


if __name__ == '__main__':
    unittest.main()
