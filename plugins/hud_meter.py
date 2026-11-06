"""Tiny pixel HUD: clock, fps, effect/particle counters and an output
throughput sparkline. Toggle with Ctrl+Shift+I."""
import time

PLUGIN = {'name': 'hud_meter', 'description': 'clock / fps / throughput sparkline (Ctrl+Shift+I)'}
S = {'on': False, 'hist': [0.0] * 40, 'acc': 0.0}


def register(api):
    def frame(dt):
        S['acc'] += dt
        if S['acc'] > 0.1:
            S['acc'] = 0
            S['hist'] = S['hist'][1:] + [api.app.energy]

    def draw(surf, rect):
        if not S['on']:
            return
        cw, ch = api.cell
        app = api.app
        t = time.strftime('%H:%M:%S') + '  %3.0ffps  fx%4d  p%6d' % (app.clock.get_fps(), len(app.fx.active), app.fx.particles.n)
        x = rect.x + cw
        y = rect.y + 2
        surf.fill((0, 0, 0), (x - 2, y - 2, (len(t) + 44) * cw, ch + 4))
        x = api.draw_text(surf, x, y, t, (120, 255, 200))
        x += cw
        for i, v in enumerate(S['hist']):
            h = max(1, int(min(1.0, v / 2) * ch))
            surf.fill((255, int(255 - 200 * min(1, v / 2)), 60), (x + i * cw, y + ch - h, cw - 1, h))

    def toggle():
        S['on'] = not S['on']
        api.animating(S['on'])

    api.on('frame', frame)
    api.on('draw', draw)
    api.add_hotkey('i', toggle, 'HUD meter')
