"""Classic demoscene sine scroller across the bottom of the screen, in a big
chrome Amiga demo font (every column rides the sine wave).
Toggle with Ctrl+Shift+Z; themes can enable it via
    plugins: {sine_scroller: {enabled: true, font: builtin:scrollergold, speed: 120, text: 'HI!   '}}
fonts: builtin:scroller | builtin:scrollergold | builtin:scrollerice | builtin:amiga | any font spec"""

PLUGIN = {'name': 'sine_scroller', 'description': 'big Amiga-font sine scroller (Ctrl+Shift+Z)'}

TEXT = ('      PIXELTERM   ***   THE PIXEL ART OVERKILL TERMINAL   ***   GREETINGS TO THE SCENE, THE ANSI ARTISTS '
        'AND EVERYONE STILL TYPING IN A TERMINAL IN 2026   ***   CTRL+SHIFT+H FOR HELP   ***   ')
S = {'on': None, 'sc': None, 'key': None}


def register(api):
    from pixelterm.scroller import SineScroller

    def enabled():
        return S['on'] if S['on'] is not None else bool(api.settings.get('enabled'))

    def scroller():
        st = api.settings
        key = (st.get('font', 'builtin:scroller'), st.get('text', TEXT), st.get('speed', 120))
        if S['sc'] is None or S['key'] != key:
            S['sc'] = SineScroller(key[1], font=key[0], speed=float(key[2]))
            S['key'] = key
        return S['sc']

    def frame(dt):
        on = enabled()
        api.animating(on)
        if on:
            scroller().update(dt)

    def draw(surf, rect):
        if not enabled():
            return
        sc = scroller()
        h = sc.font.ch
        sc.draw(surf, rect, rect.bottom - h * 1.1, h * 0.45)

    def toggle():
        S['on'] = not enabled()
        api.notify('sine scroller %s' % ('on' if S['on'] else 'off'))

    api.on('frame', frame)
    api.on('draw', draw)
    api.add_hotkey('z', toggle, 'sine scroller')
