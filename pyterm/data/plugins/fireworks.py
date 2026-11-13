"""Fireworks! Ctrl+Shift+K, the Konami code (up up down down left right left
right b a), or automatically when a command prints 'success' / 'passed' or a
long command finishes.  The display itself is the built-in `fireworks` show
(pyterm/shows.py): peony, willow, heart, crossette ... shells with a finale."""
import re

PLUGIN = {'name': 'fireworks', 'description': 'fireworks: Ctrl+Shift+K, konami code, success output, long commands'}

KONAMI = ['up', 'up', 'down', 'down', 'left', 'right', 'left', 'right', 'b', 'a']
S = {'keys': [], 'cool': 0.0}
OK = re.compile(r'(?i)\b(all tests passed|success(fully)?|build succeeded|\d+ passed)\b')


def register(api):
    import pygame

    def show(**kw):
        api.app.trigger_show('fireworks', **kw)

    def frame(dt):
        S['cool'] = max(0, S['cool'] - dt)

    def key(ev):
        S['keys'] = (S['keys'] + [pygame.key.name(ev.key)])[-10:]
        if S['keys'] == KONAMI:
            S['keys'] = []
            show(duration=16, intensity=1.8)
            api.notify('+30 lives')
        return False

    def output(text):
        if S['cool'] <= 0 and OK.search(text):
            S['cool'] = 8
            show(duration=5)
        return text

    def command_done(exit_code, seconds, cmdline):
        # long-running command finished successfully -> celebrate
        if exit_code == 0 and seconds >= 10:
            show(duration=8)

    api.on('command_done', command_done)
    api.on('frame', frame)
    api.on('key', key)
    api.on('output', output)
    api.add_hotkey('k', lambda: show(duration=10), 'fireworks')
