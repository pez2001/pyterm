"""Procedural sound - every sample is synthesized at startup with numpy, no
audio files needed. Packs: chime, typewriter, 8bit, glass, off.
Custom packs: put WAV/OGG files in sounds/<pack>/ named key.wav, delete.wav,
newline.wav, bell.wav, ... and they override the synthesized ones."""
from __future__ import annotations

import os
import random
import time

import numpy as np
import pygame

SR = 22050
PENTA = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21]
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')   # bundled assets (themes, fonts, sounds, plugins, shell, config.yaml)


def _env(n, attack=0.004, decay=6.0):
    t = np.arange(n) / SR
    a = np.minimum(1, t / max(attack, 1e-4))
    return a * np.exp(-t * decay)


def _sine(f, dur, decay=6.0, harm=((1, 1.0),)):
    n = int(SR * dur)
    t = np.arange(n) / SR
    s = sum(a * np.sin(2 * np.pi * f * h * t) for h, a in harm)
    return s * _env(n, decay=decay)


def _square(f, dur, decay=10.0, duty=0.5):
    n = int(SR * dur)
    t = np.arange(n) / SR
    s = np.where((t * f) % 1 < duty, 1.0, -1.0)
    return s * _env(n, 0.001, decay) * 0.5


def _noise(dur, decay=30.0, lp=0.5):
    n = int(SR * dur)
    s = np.random.uniform(-1, 1, n)
    if lp < 1:
        for i in range(1, n):
            s[i] = s[i - 1] * lp + s[i] * (1 - lp)
    return s * _env(n, 0.0005, decay)


def _sweep(f0, f1, dur, decay=8.0, square=False):
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = np.linspace(f0, f1, n)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sign(np.sin(ph)) * 0.5 if square else np.sin(ph)
    return s * _env(n, 0.002, decay)


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


class Sound:
    def __init__(self, pack='chime', volume=0.4, enabled=True):
        self.ok = False
        self.enabled = enabled
        self.volume = volume
        self.pack = 'off' if pack is False else pack
        self.last = {}
        self.sounds = {}
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(SR, -16, 2, 512)
                pygame.mixer.init()
            pygame.mixer.set_num_channels(32)
            self.channels = pygame.mixer.get_init()[2]
            self.ok = True
        except Exception as e:  # no audio device
            print('[pyterm] sound disabled: %s' % e)
            return
        self.build(pack)

    def _mk(self, data, vol=1.0):
        data = np.asarray(data, np.float64)
        peak = np.max(np.abs(data)) or 1
        a = (data / peak * 32767 * 0.8 * vol).astype(np.int16)
        if self.channels == 2:
            a = np.repeat(a[:, None], 2, axis=1)
        return pygame.sndarray.make_sound(np.ascontiguousarray(a))

    def build(self, pack):
        if pack is False or pack is None:
            pack = 'off'  # YAML reads a bare  off  as false
        pack = str(pack)
        self.pack = pack
        self.sounds = {}
        if not self.ok or pack == 'off':
            return
        S = {}
        base = 523.25
        if pack == 'typewriter':
            S['key'] = [self._mk(mix(_noise(0.05, 70, 0.3), 0.3 * _sine(1800 + random.random() * 400, 0.03, 90)), 0.5)
                        for _ in range(6)]
            S['delete'] = [self._mk(_noise(0.04, 80, 0.6), 0.4)]
            S['newline'] = [self._mk(mix(_sine(2093, 0.9, 4, ((1, 1), (2.76, 0.4), (5.4, 0.2))) * 0.6,
                                         _noise(0.25, 12, 0.85)), 0.6)]
        elif pack == '8bit':
            S['key'] = [self._mk(_square(base * 2 ** (p / 12), 0.06, 30), 0.35) for p in PENTA]
            S['delete'] = [self._mk(_sweep(900, 200, 0.08, 20, True), 0.35)]
            S['newline'] = [self._mk(np.concatenate([_square(base * 2, 0.04, 20), _square(base * 3, 0.06, 20)]), 0.3)]
        elif pack == 'glass':
            S['key'] = [self._mk(_sine(base * 2 * 2 ** (p / 12), 0.5, 7, ((1, 1), (2.32, 0.5), (4.25, 0.25))), 0.3)
                        for p in PENTA]
            S['delete'] = [self._mk(_sweep(2400, 1200, 0.2, 14), 0.25)]
            S['newline'] = [self._mk(_sine(base, 0.8, 4, ((1, 1), (1.5, 0.5), (2, 0.4))), 0.35)]
        else:  # chime
            S['key'] = [self._mk(_sine(base * 2 ** (p / 12), 0.35, 9, ((1, 1), (2, 0.3), (3, 0.08))), 0.35)
                        for p in PENTA]
            S['delete'] = [self._mk(_sweep(1200, 300, 0.12, 18), 0.3)]
            S['newline'] = [self._mk(_sine(base / 2, 0.5, 6, ((1, 1), (2, 0.5))), 0.3)]
        S['bell'] = [self._mk(mix(_sine(880, 0.6, 5, ((1, 1), (2.4, 0.4))), _sine(1320, 0.6, 5) * 0.5), 0.6)]
        S['pick'] = [self._mk(mix(_sine(2900 + random.random() * 500, 0.12, 30, ((1, 1), (1.47, 0.6), (2.9, 0.3))),
                                  _noise(0.12, 40, 0.2) * 0.5), 0.35) for _ in range(4)]
        S['break'] = [self._mk(_noise(0.18, 18, 0.8), 0.45)]
        S['gem'] = [self._mk(np.concatenate([_sine(base * 2 ** (p / 12) * 2, 0.07, 20) for p in (0, 4, 7, 12, 16)]), 0.35)]
        S['boom'] = [self._mk(mix(_noise(1.2, 3.5, 0.95), _sweep(120, 30, 1.2, 3) * 0.8), 0.9)]
        S['whoosh'] = [self._mk(_noise(0.6, 4, 0.9) * np.sin(np.linspace(0, np.pi, int(SR * 0.6))), 0.4)]
        S['boot'] = [self._mk(np.concatenate([_square(base * 2 ** (p / 12), 0.09, 8, 0.25) for p in
                                              (0, 7, 12, 16, 19, 24, 19, 24, 28, 31)]), 0.35)]
        self.sounds = S
        self._load_custom(pack)

    def _load_custom(self, pack):
        d = os.path.join(ROOT, 'sounds', pack)
        if not os.path.isdir(d):
            return
        custom = {}
        for fn in sorted(os.listdir(d)):
            k, ext = os.path.splitext(fn)
            if ext.lower() in ('.wav', '.ogg', '.mp3'):
                try:
                    custom.setdefault(k.rstrip('0123456789_'), []).append(pygame.mixer.Sound(os.path.join(d, fn)))
                except Exception as e:
                    print('[pyterm] sound %s: %s' % (fn, e))
        self.sounds.update(custom)

    def play(self, kind, pitch=None, min_gap=0.03, vol=1.0):
        if not (self.ok and self.enabled) or kind not in self.sounds:
            return
        now = time.perf_counter()
        if now - self.last.get(kind, 0) < min_gap:
            return
        self.last[kind] = now
        lst = self.sounds[kind]
        s = lst[pitch % len(lst)] if pitch is not None else random.choice(lst)
        ch = s.play()
        if ch:
            ch.set_volume(self.volume * vol)

    def on_frame(self, stats):
        if stats['bell']:
            self.play('bell', min_gap=0.2)
        if stats['nl'] and stats['nl'] < 4:
            self.play('newline', min_gap=0.08)
        if stats['puts']:
            self.play('key', pitch=ord(stats['last'][0]) if stats['last'] else 0, min_gap=0.035,
                      vol=1.0 if stats['puts'] < 20 else 0.5)
        elif stats['dels']:
            self.play('delete', min_gap=0.05)
