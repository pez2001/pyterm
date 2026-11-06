"""my_plugin - describe what it does.

Saved changes are hot-reloaded instantly. Errors appear in the Studio
(Ctrl+Shift+F12 -> PLUGINS / CONSOLE) and never crash the terminal.
API reference: docs/PLUGINS.md
"""

PLUGIN = {'name': 'my_plugin', 'description': 'a fresh pyterm plugin', 'author': 'you'}

state = {'t': 0.0}


def register(api):
    def frame(dt):
        state['t'] += dt

    def draw(surf, rect):
        # surf: virtual (pixel art) surface, rect: terminal area on it
        api.draw_text(surf, rect.x + 4, rect.bottom - api.cell[1] - 2, 'my_plugin is alive', (255, 200, 0))

    def hello():
        api.notify('hello from my_plugin!')

    api.on('frame', frame)
    api.on('draw', draw)
    api.add_hotkey('y', hello, 'say hello')      # Ctrl+Shift+Y
    # api.animating(True)   # uncomment if you draw something that moves every frame
    # custom cursor style / cursor effect - see plugins/cursor_demo.py:
    #   from pyterm.cursors import CursorStyle, CursorEffect
    #   api.register_cursor('mycursor', MyCursor); api.register_cursor_effect('myfx', MyFx)
    # api.on('command_done', lambda exit_code, seconds, cmd: api.notify('%s -> %s' % (cmd, exit_code)))


def unregister(api):
    pass
