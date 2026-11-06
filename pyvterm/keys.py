"""pygame keyboard / mouse events  ->  terminal byte sequences."""
from __future__ import annotations

import pygame

K = pygame


SPECIAL = {
    K.K_RETURN: '\r', K.K_KP_ENTER: '\r', K.K_BACKSPACE: '\x7f', K.K_TAB: '\t',
    K.K_ESCAPE: '\x1b', K.K_DELETE: '\x1b[3~', K.K_INSERT: '\x1b[2~',
    K.K_PAGEUP: '\x1b[5~', K.K_PAGEDOWN: '\x1b[6~',
    K.K_F1: '\x1bOP', K.K_F2: '\x1bOQ', K.K_F3: '\x1bOR', K.K_F4: '\x1bOS',
    K.K_F5: '\x1b[15~', K.K_F6: '\x1b[17~', K.K_F7: '\x1b[18~', K.K_F8: '\x1b[19~',
    K.K_F9: '\x1b[20~', K.K_F10: '\x1b[21~', K.K_F11: '\x1b[23~', K.K_F12: '\x1b[24~',
}
CURSOR = {K.K_UP: 'A', K.K_DOWN: 'B', K.K_RIGHT: 'C', K.K_LEFT: 'D', K.K_HOME: 'H', K.K_END: 'F'}
TILDE_NUM = {K.K_DELETE: 3, K.K_INSERT: 2, K.K_PAGEUP: 5, K.K_PAGEDOWN: 6,
             K.K_F5: 15, K.K_F6: 17, K.K_F7: 18, K.K_F8: 19, K.K_F9: 20, K.K_F10: 21,
             K.K_F11: 23, K.K_F12: 24}


def xterm_mod(mods):
    m = 1
    if mods & K.KMOD_SHIFT:
        m += 1
    if mods & K.KMOD_ALT:
        m += 2
    if mods & K.KMOD_CTRL:
        m += 4
    return m


def key_to_seq(ev, app_cursor=False):
    """Return the string to send for a KEYDOWN, or None if TEXTINPUT will
    deliver it (plain printable characters)."""
    key, mods = ev.key, ev.mod
    ctrl = bool(mods & K.KMOD_CTRL)
    alt = bool(mods & K.KMOD_LALT)   # right alt is AltGr on many layouts (German!)
    shift = bool(mods & K.KMOD_SHIFT)
    # AltGr on Windows arrives as Ctrl+Alt: let TEXTINPUT handle it
    if (mods & K.KMOD_MODE) or (ctrl and alt and getattr(ev, 'unicode', '') and ev.unicode.isprintable()):
        return None
    m = xterm_mod(mods)
    if key in CURSOR:
        f = CURSOR[key]
        if m > 1:
            return '\x1b[1;%d%s' % (m, f)
        return ('\x1bO' if app_cursor else '\x1b[') + f
    if key in TILDE_NUM and m > 1:
        return '\x1b[%d;%d~' % (TILDE_NUM[key], m)
    if key == K.K_TAB and shift:
        return '\x1b[Z'
    if key == K.K_BACKSPACE:
        return ('\x1b' if alt else '') + ('\x08' if ctrl else '\x7f')
    if key in SPECIAL:
        s = SPECIAL[key]
        return ('\x1b' + s) if alt and len(s) == 1 else s
    if ctrl and not alt:
        if K.K_a <= key <= K.K_z:
            return chr(key - K.K_a + 1)
        cmap = {K.K_SPACE: '\x00', K.K_2: '\x00', K.K_LEFTBRACKET: '\x1b', K.K_3: '\x1b',
                K.K_BACKSLASH: '\x1c', K.K_4: '\x1c', K.K_RIGHTBRACKET: '\x1d', K.K_5: '\x1d',
                K.K_6: '\x1e', K.K_MINUS: '\x1f', K.K_7: '\x1f', K.K_SLASH: '\x1f', K.K_8: '\x7f'}
        if key in cmap:
            return cmap[key]
    if alt and not ctrl:
        u = getattr(ev, 'unicode', '')
        if u and u.isprintable():
            return '\x1b' + u
        if K.K_a <= key <= K.K_z:
            return '\x1b' + chr(key)
    return None


def mouse_seq(button, col, row, press=True, sgr=True, motion=False):
    """button: 0 left 1 middle 2 right 64 wheel-up 65 wheel-down"""
    b = button + (32 if motion else 0)
    if sgr:
        return '\x1b[<%d;%d;%d%s' % (b, col + 1, row + 1, 'M' if press else 'm')
    if not press:
        b = 3
    return '\x1b[M' + chr(32 + b) + chr(32 + min(col + 1, 222)) + chr(32 + min(row + 1, 222))
