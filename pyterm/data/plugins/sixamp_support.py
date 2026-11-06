"""sixamp_support - exact pointer and cell size for SIXAMP (and other full-screen Sixel programs).

What used to live here is now built into pyterm itself:
  * sixels on the alternate screen paint into one screen-sized layer (vt.Screen.paint_sixel)
  * after a font / scale / size change that layer is dropped and sixels are ignored for 0.15 s
  * XTWINOPS size reports CSI 14 t / 16 t / 18 t
  * mouse drag / motion reports (modes 1002 and 1003)

This plugin only adds the SIXAMP-specific part: ConPTY carries whole cells only and may eat size
queries, so the live cell size and the exact pointer position are published in shared memory.

The first tab starts before plugins load, so the memory has a fixed name rather than one passed
down in the environment: tagname 'pyterm_sixamp_share' on Windows, and the file
pyterm_sixamp_share_<uid> in the temp folder elsewhere. Only the focused window writes the
cell size, so several pyterm windows do not fight over it.

Layout of the 20 shared bytes: b'PVTM', pointer x, pointer y, cell width, cell height (int32).
Pointer and cell are in window pixels, relative to the text area of the pane under the pointer.
Remove the file, or list it in disabled_plugins, to turn it off.
"""
import mmap
import os
import struct
import tempfile

import pygame

PLUGIN = {'name': 'sixamp_support', 'description': 'exact pointer + cell size in shared memory for SIXAMP',
          'author': 'SIXAMP'}

S = {'mem': None, 'pos': None}


def open_share():
    if os.name == 'nt':
        mem = mmap.mmap(-1, 20, tagname='pyterm_sixamp_share')
    else:
        path = os.path.join(tempfile.gettempdir(), 'pyterm_sixamp_share_%d' % os.getuid())
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        os.ftruncate(fd, 20)
        mem = mmap.mmap(fd, 20)
        os.close(fd)
    mem[0:4] = b'PVTM'
    return mem


def register(api):
    app = api.app
    S['mem'] = getattr(app, 'mouse_share', None) or open_share()
    app.mouse_share = S['mem']

    def frame(dt):
        mem = S['mem']
        focused = pygame.key.get_focused() or pygame.mouse.get_focused()
        cell = getattr(app.pane.screen, 'cell_px', None)
        if cell and (focused or mem[12:20] == bytes(8)):
            mem[12:20] = struct.pack('<ii', *cell)
        if not getattr(app, 's', None) or not focused:
            return
        pos = pygame.mouse.get_pos()
        if pos == S['pos']:
            return
        S['pos'] = pos
        W, H = app.presenter.size()
        s = app.s
        dx = (W - app.studio_w - app.vw * s) // 2
        dy = (H - app.vh * s) // 2
        pane = app.pane_at(app.to_virtual(pos)) or app.pane
        mem[4:12] = struct.pack('<ii', pos[0] - dx - pane.rect.x * s, pos[1] - dy - pane.rect.y * s)

    api.on('frame', frame)


def unregister(api):
    S['pos'] = None
