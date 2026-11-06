"""Example: a custom alarm. Shows up in Home Assistant as the button "Alarm party" and works with
mqtt  pyvterm/<device>/set/alarm  "party Dinner is ready"  and the demo shell:  alarm party hello

An alarm = sound() returning (pygame Sound, repeat seconds) + draw(surf, app) on top of everything.
"""
import math
import random

import numpy as np

from pyvterm.alarms import Alarm

NAME = 'party_alarm'


class Party(Alarm):
    duration = 15.0
    label = 'party'
    ha_icon = 'mdi:party-popper'

    def start(self):
        self.bits = []

    def sound(self, snd):
        sr = 44100
        notes = [523, 659, 784, 1047, 784, 1047]            # a little fanfare
        out = []
        for i, f in enumerate(notes):
            n = int(sr * (0.28 if i == len(notes) - 1 else 0.12))
            t = np.arange(n) / sr
            out.append(np.sign(np.sin(2 * np.pi * f * t)) * 0.4 * np.exp(-t * 6))
        return snd._mk(np.concatenate(out + [np.zeros(sr)]), 0.5), 2.5

    def update(self, dt):
        super().update(dt)
        W, H = self.app.vw, self.app.vh
        for _ in range(6):
            self.bits.append([random.uniform(0, W), -4, random.uniform(-20, 20), random.uniform(40, 120),
                              random.choice(((255, 80, 80), (80, 255, 120), (90, 160, 255), (255, 220, 60), (255, 90, 230)))])
        for b in self.bits:
            b[0] += b[2] * dt + math.sin(self.t * 4 + b[1] * 0.05) * 0.6
            b[1] += b[3] * dt
        self.bits = [b for b in self.bits if b[1] < H][-500:]

    def draw(self, surf, app):
        W, H = surf.get_size()
        hue = self.t * 2
        self.edge(surf, (255, 255, 255), max(10, min(W, H) // 8), 0.15)
        col = (int(127 + 127 * math.sin(hue)), int(127 + 127 * math.sin(hue + 2.1)), int(127 + 127 * math.sin(hue + 4.2)))
        for x, y, _, _, c in self.bits:
            surf.fill(c, (int(x), int(y), 3, 2))
        self.card(surf, app, 'PARTY TIME', col)


def register(api):
    api.register_alarm('party', Party)
