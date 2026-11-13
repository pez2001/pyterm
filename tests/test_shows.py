"""Shows (fireworks, confetti, lightning ...): registry, options, theme events, plugins, MQTT payloads.

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

from pyterm import backgrounds, shows, themes  # noqa: E402,F401
from pyterm.app import App  # noqa: E402
from pyterm.config import build_config  # noqa: E402


def make_app():
    app = App(*build_config(['--demo', '--gpu', 'false', '--size', '800x500', '--no-sound']))
    app._demo_used = True
    app.intro = None
    for _ in range(5):
        app.frame(1 / 30)
    return app


class ParseTests(unittest.TestCase):
    def test_parse_string_and_json(self):
        self.assertEqual(shows.parse('fireworks style=willow duration=15 finale=false'),
                         ('fireworks', {'style': 'willow', 'duration': 15, 'finale': False}))
        self.assertEqual(shows.parse('{"show": "confetti", "intensity": 2}'), ('confetti', {'intensity': 2}))
        self.assertEqual(shows.parse('lasers'), ('lasers', {}))

    def test_specs(self):
        self.assertEqual(shows.specs(['lightning', {'show': 'confetti', 'palette': 'gold'}]),
                         [('lightning', {}), ('confetti', {'palette': 'gold'})])
        self.assertEqual(shows.specs(None), [])

    def test_palettes(self):
        self.assertEqual(shows.palette_of(None, '#f00,#00ff00'), [(255, 0, 0), (0, 255, 0)])
        self.assertTrue(shows.palette_of(None, 'gold'))
        self.assertTrue(shows.palette_of(None, 'nonsense'))


class ShowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app()

    def run_show(self, name, seconds, **kw):
        app = self.app
        s = app.trigger_show(name, **kw)
        vs = pygame.Surface((app.vw, app.vh))
        for _ in range(int(seconds * 30)):
            app.frame(1 / 30)
            s.draw(vs, app)
        return s

    def test_every_builtin_runs_and_ends(self):
        for name in shows.SHOWS:
            with self.subTest(show=name):
                s = self.run_show(name, 1.5, duration=1.2)
                self.app.frame(1 / 30)
                self.assertTrue(s.done)
                self.assertNotIn(s, self.app.shows)

    def test_all_fireworks_styles(self):
        for st in shows.STYLES:
            with self.subTest(style=st):
                s = self.app.trigger_show('fireworks', style=st, duration=3, finale=False)
                s._burst(100, 100, st, (255, 0, 0), (0, 0, 255))
                for _ in range(10):
                    self.app.frame(1 / 30)
                s.stop()
                self.app.frame(1 / 30)

    def test_retrigger_extends_fireworks(self):
        s = self.app.trigger_show('fireworks', duration=2)
        for _ in range(10):
            self.app.frame(1 / 30)
        s2 = self.app.trigger_show('fireworks', duration=6)
        self.assertIs(s, s2)
        self.assertGreater(s.duration, 6)
        s.stop()

    def test_unknown_show(self):
        with self.assertRaises(ValueError):
            self.app.trigger_show('nope')

    def test_odd_sizes(self):
        app = self.app
        for name in shows.SHOWS:
            cls = shows.SHOWS[name]
            app.vw, app.vh = 48, 32
            s = cls(app, duration=1)
            s.update(1 / 30)
            s.draw(pygame.Surface((48, 32)), app)

    def test_theme_events(self):
        app = self.app
        app.theme['events'] = {'bell': 'confetti duration=1', 'success': ['lasers', 'shockwave']}
        app.shows.clear()
        app.show_event('bell')
        self.assertEqual([s.name for s in app.shows], ['confetti'])
        app.show_event('success')
        self.assertEqual({s.name for s in app.shows}, {'confetti', 'lasers', 'shockwave'})
        app.cfg['shows'] = False
        app.shows.clear()
        app.show_event('bell')
        self.assertEqual(app.shows, [])
        app.cfg['shows'] = True
        app.theme['events'] = {'bell': 'doesnotexist'}
        app.show_event('bell')           # logged, not raised
        app.shows.clear()

    def test_bundled_themes_with_events_are_valid(self):
        for name in themes.list_themes():
            ev = themes.load_theme(name).get('events') or {}
            for key, value in ev.items():
                for show, _ in shows.specs(value):
                    self.assertIn(show, shows.SHOWS, '%s: %s' % (name, key))

    def test_plugin_register_and_unload(self):
        class Mine(shows.Show):
            duration = 0.5
        app = self.app
        p = app.plugins
        from pyterm.plugins import PluginAPI
        owner = type('P', (), {'owned': [], 'name': 'x'})()
        PluginAPI(p, owner).register_show('mine', Mine)
        self.assertIn('mine', shows.SHOWS)
        app.trigger_show('mine')
        p._remove_hooks(owner)
        self.assertNotIn('mine', shows.SHOWS)
        app.shows.clear()

    def test_fireworks_plugin_delegates_to_show(self):
        hk = self.app.plugins.hotkeys.get('k')
        self.assertIsNotNone(hk)
        self.app.shows.clear()
        hk[1]()
        self.assertEqual([s.name for s in self.app.shows], ['fireworks'])
        self.app.shows.clear()


if __name__ == '__main__':
    unittest.main()
