"""Getting pixels on screen.

SoftwarePresenter: classic pygame display surface, CPU upscaling.
GPUPresenter:      SDL2 renderer (pygame._sdl2.video) - the virtual surface is
                   uploaded once per frame and scaled / blended on the GPU,
                   vsync-capable, much lower CPU usage at high resolutions.
The GPU path falls back to software automatically on any error.
"""
from __future__ import annotations

import os
import random

import pygame

from .post import Post


class SoftwarePresenter:
    gpu = False

    def __init__(self, size, fullscreen=False, vsync=False):
        flags = pygame.RESIZABLE
        if fullscreen:
            flags = pygame.FULLSCREEN
            size = (0, 0)
        self.win = pygame.display.set_mode(size, flags)
        self.fullscreen = fullscreen
        self._win_size = size

    def size(self):
        return self.win.get_size()

    def set_caption(self, t):
        try:
            pygame.display.set_caption(t)
        except Exception:
            pass

    def set_icon(self, s):
        pygame.display.set_icon(s)

    def resized(self, w, h):
        if not self.fullscreen:
            self.win = pygame.display.set_mode((max(200, w), max(150, h)), pygame.RESIZABLE)

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self._win_size = self.win.get_size()
            self.win = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.win = pygame.display.set_mode(self._win_size, pygame.RESIZABLE)

    def begin(self, area, dst=None):
        if dst is None or not dst.contains(area):      # the picture covers the window: nothing to clear
            self.win.fill((0, 0, 0), area)

    def draw_main(self, vs, dst, s, area):
        win = self.win
        dw, dh = dst.size
        if s == 1:
            win.blit(vs, dst)
        elif dst.clip(area).size == dst.size:
            pygame.transform.scale(vs, (dw, dh), win.subsurface(dst))
        else:
            win.blit(pygame.transform.scale(vs, (dw, dh)), dst)

    def draw_image(self, im, rect, clip):
        key = rect.size
        if im.get('_sw_key') != key:
            surf = im['surf']
            im['_sw'] = surf if surf.get_size() == key else pygame.transform.smoothscale(surf, key)
            im['_sw_key'] = key
        old = self.win.get_clip()
        self.win.set_clip(clip)
        self.win.blit(im['_sw'], rect)
        self.win.set_clip(old)

    def post_window(self, post: Post, dst, s, dt):
        post.window(self.win, dst, s, dt)

    def draw_panel(self, surf, pos):
        self.win.blit(surf, pos)

    def panel_surface(self, rect):
        return self.win.subsurface(rect)

    def overlay(self):
        return self.win

    def finish(self):
        pygame.display.flip()

    def screenshot(self):
        return self.win.copy()

    def frame_surface(self):
        return self.win


class GPUPresenter:
    gpu = True

    def __init__(self, size, fullscreen=False, vsync=True):
        os.environ.setdefault('SDL_HINT_RENDER_SCALE_QUALITY', '0')
        try:
            pygame.display.set_hint('SDL_RENDER_SCALE_QUALITY', '0')  # pygame-ce
        except Exception:
            pass
        from pygame._sdl2 import video
        self.video = video
        self.window = video.Window('pyterm', size=size, resizable=True)
        if fullscreen:
            self.window.set_fullscreen(True)
        try:
            self.ren = video.Renderer(self.window, vsync=bool(vsync), accelerated=1)
        except Exception:
            self.ren = video.Renderer(self.window, vsync=bool(vsync))
        self.fullscreen = fullscreen
        self.vtex = None
        self.vtex_size = None
        self.mult_tex = None
        self.mult_key = None
        self.panel_tex = None
        self.panel_size = None
        self._panel = None
        self._overlay = None

    def size(self):
        return tuple(self.window.size)

    def set_caption(self, t):
        self.window.title = t

    def set_icon(self, s):
        try:
            self.window.set_icon(s)
        except Exception:
            pass

    def resized(self, w, h):
        pass

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.window.set_fullscreen(True)
        else:
            self.window.set_windowed()

    def begin(self, area, dst=None):
        self.ren.draw_color = (0, 0, 0, 255)
        self.ren.clear()

    def draw_main(self, vs, dst, s, area):
        if self.vtex is None or self.vtex_size != vs.get_size():
            self.vtex = self.video.Texture(self.ren, vs.get_size(), streaming=True)
            self.vtex_size = vs.get_size()
        self.vtex.update(vs)
        self.vtex.draw(dstrect=dst)

    def draw_image(self, im, rect, clip):
        tex = im.get('_tex')
        if tex is None or im.get('_tex_ren') is not self.ren:
            tex = self.video.Texture.from_surface(self.ren, im['surf'])
            im['_tex'] = tex
            im['_tex_ren'] = self.ren
        vis = rect.clip(clip)
        if not vis.width or not vis.height:
            return
        sw, sh = im['surf'].get_size()
        kx, ky = sw / rect.width, sh / rect.height
        src = pygame.Rect(int((vis.x - rect.x) * kx), int((vis.y - rect.y) * ky),
                          max(1, int(vis.width * kx)), max(1, int(vis.height * ky)))
        tex.draw(srcrect=src, dstrect=vis)

    def post_window(self, post: Post, dst, s, dt):
        sl, vg, lcd = post.v('scanlines'), post.v('vignette'), post.v('lcd')
        if sl > 0 or vg > 0 or lcd > 0:
            key = (dst.size, sl, vg, s, lcd)
            if key != self.mult_key:
                self.mult_key = key
                surf = post._build_mult(dst.size, sl, vg, s, lcd)
                self.mult_tex = self.video.Texture.from_surface(self.ren, surf)
                self.mult_tex.blend_mode = 4  # SDL_BLENDMODE_MOD
            self.mult_tex.draw(dstrect=dst)
        il = post.v('interlace')
        if il > 0 and s >= 2:
            key = (dst.size, s, il)
            if getattr(self, '_il_key', None) != key:
                self._il_key = key
                self._il_tex = []
                for f in (0, 1):
                    t = self.video.Texture.from_surface(self.ren, post._field_mask(dst.size, s, il, f))
                    t.blend_mode = 4
                    self._il_tex.append(t)
            self._il_tex[getattr(post, 'field', 0)].draw(dstrect=dst)
        fl = post.v('flicker')
        if fl > 0:
            k = int(255 * (1 - fl * random.random()))
            self.ren.draw_blend_mode = 4
            self.ren.draw_color = (k, k, k, 255)
            self.ren.fill_rect(dst)
        nz = post.v('noise')
        if nz > 0:
            self.ren.draw_blend_mode = 2  # add
            for _ in range(int(nz * 20)):
                c = random.randint(10, 40)
                self.ren.draw_color = (c, c, c, 255)
                self.ren.fill_rect((dst.x, random.randint(dst.top, dst.bottom - 1), dst.width, 1))
        self.ren.draw_blend_mode = 0

    def panel_surface(self, rect):
        if self._panel is None or self._panel.get_size() != rect.size:
            self._panel = pygame.Surface(rect.size)
        self._panel_pos = rect.topleft
        return self._panel

    def draw_panel(self, surf, pos):
        if self.panel_tex is None or self.panel_size != surf.get_size():
            self.panel_tex = self.video.Texture(self.ren, surf.get_size(), streaming=True)
            self.panel_size = surf.get_size()
        self.panel_tex.update(surf)
        self.panel_tex.draw(dstrect=pygame.Rect(pos, surf.get_size()))

    def overlay(self):
        size = self.size()
        if self._overlay is None or self._overlay.get_size() != size:
            self._overlay = pygame.Surface(size, pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, 0))
        return self._overlay

    def flush_overlay(self):
        if self._overlay is not None:
            t = self.video.Texture.from_surface(self.ren, self._overlay)
            t.blend_mode = 1
            t.draw()

    def finish(self):
        self.ren.present()

    def screenshot(self):
        return self.ren.to_surface()

    def frame_surface(self):
        return self.ren.to_surface()


def create_presenter(cfg, headless=False):
    mode = str(cfg.get('gpu', 'auto')).lower()
    size = (cfg['width'], cfg['height'])
    if mode in ('true', 'on', 'yes', '1') or (mode == 'auto' and not headless):
        try:
            p = GPUPresenter(size, bool(cfg['fullscreen']), cfg.get('vsync', True))
            return p
        except Exception as e:
            print('[pyterm] GPU presenter unavailable (%s) - using software' % e)
    return SoftwarePresenter(size, bool(cfg['fullscreen']))
