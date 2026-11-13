"""Optional MQTT + Home Assistant integration (off by default).

Enable in config.yaml (mqtt: {enabled: true, host: ...}) or with  --mqtt [mqtt://user:pass@host:1883].
Needs  pip install paho-mqtt . With Home Assistant's MQTT integration the terminal shows up as a
device automatically (MQTT discovery). See docs/HOMEASSISTANT.md.

What is exposed - deliberately small:

  to Home Assistant                         from Home Assistant
  -----------------                         -------------------
  event   terminal  (command_failed,        select  theme / background / letter effect /
          command_succeeded, long_command,          delete effect / cursor
          error_output, bell)               switch  zen mode, sound, emerald mine, sine scroller
  binary  last command failed, user active  number  background brightness, volume
  sensor  last exit code, last duration,    text    notification (shown on screen),
          output rate, theme                        scroller text
  sensor  last command / last error line    button  fireworks, screenshot, next theme
          (only with publish_text: true)
  binary  alarm active, sensor alarm        alarm   button per alarm type, stop alarm,
  event   alarm_started / _dismissed /              alarm message text, set/alarm topic
          _finished (someone pressed a key)         (name, "name message" or JSON)

Never exposed: typing into the terminal or running commands. Remote control is limited to looks.
"""
from __future__ import annotations

import json
import queue
import re
import socket
import time
from urllib.parse import unquote, urlparse

from . import __version__, signals

ANSI = re.compile(r'\x1b(\[[0-?]*[ -/]*[@-~]|\][^\x07]*(\x07|\x1b\\)|[@-Z\\-_])')

ALARM_KEYS = ('alarm', 'alarm_stop', 'alarm_message', 'alarm_duration')
SHOW_KEYS = ('show', 'show_stop')

DEFAULTS = {
    'enabled': False,
    'host': 'localhost',
    'port': 1883,
    'username': None,
    'password': None,
    'tls': False,
    'device_id': None,           # default: hostname
    'name': None,                # device name in HA, default "pyterm <host>"
    'base_topic': 'pyterm',
    'discovery': True,
    'discovery_prefix': 'homeassistant',
    'publish_text': False,       # also publish command lines and the last error line (privacy!)
    'allow_control': True,       # accept settings changes from Home Assistant
    'allow_alarms': True,        # accept alarms (set/alarm) - independent of allow_control
    'allow_shows': True,         # accept shows - fireworks, confetti, lightning ... (set/show) - independent of allow_control
    'long_command': 10,          # seconds: fire a long_command event
    'debug': False,              # print every message sent / received to the console
}


def parse_url(url, base):
    """mqtt://user:pass@host:port  or  mqtts://...  or just host[:port]"""
    cfg = dict(base)
    if not url or url is True:
        return cfg
    if '://' not in url:
        url = 'mqtt://' + url
    u = urlparse(url)
    if u.hostname:
        cfg['host'] = u.hostname
    if u.port:
        cfg['port'] = u.port
    if u.username:
        cfg['username'] = unquote(u.username)
    if u.password:
        cfg['password'] = unquote(u.password)
    if u.scheme == 'mqtts':
        cfg['tls'] = True
        if not u.port:
            cfg['port'] = 8883
    return cfg


def _slug(s):
    return re.sub(r'[^a-z0-9_]+', '_', str(s).lower()).strip('_') or 'pyterm'


class MqttBridge:
    def __init__(self, app, cfg):
        self.app = app
        self.cfg = dict(DEFAULTS, **(cfg or {}))
        host = socket.gethostname()
        self.dev = _slug(self.cfg['device_id'] or host)
        self.name = self.cfg['name'] or 'pyterm %s' % host
        self.base = '%s/%s' % (self.cfg['base_topic'].rstrip('/'), self.dev)
        self.inbox = queue.Queue()
        self.client = None
        self.connected = False
        self.last = {}             # retained state cache: key -> payload
        self.next_periodic = 0.0
        self.active = None
        self.cmds_seen = False
        self.last_bell = signals.bell
        self.last_err_t = 0.0
        self.error = None
        self.alarm_message = ''
        self.alarm_duration = 0.0

    # ------------------------------------------------------------------ lifecycle
    def start(self):
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            self.error = 'paho-mqtt not installed (pip install paho-mqtt)'
            print('[pyterm] mqtt: ' + self.error)
            return False
        c = self.cfg
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='pyterm-%s' % self.dev)
        except (AttributeError, TypeError):          # paho-mqtt 1.x
            self.client = mqtt.Client(client_id='pyterm-%s' % self.dev)
        cl = self.client
        if c.get('username'):
            cl.username_pw_set(c['username'], c.get('password'))
        if c.get('tls'):
            cl.tls_set()
        cl.will_set(self.base + '/status', 'offline', qos=1, retain=True)
        cl.on_connect = self._on_connect
        cl.on_disconnect = self._on_disconnect
        cl.on_message = self._on_message
        cl.reconnect_delay_set(2, 60)
        try:
            cl.connect_async(c['host'], int(c['port']), keepalive=30)
            cl.loop_start()
        except Exception as e:
            self.error = str(e)
            print('[pyterm] mqtt: %s' % e)
            return False
        print('[pyterm] mqtt: connecting to %s:%s as %s' % (c['host'], c['port'], self.base))
        return True

    def stop(self):
        if not self.client:
            return
        self.stopping = True
        try:
            self.client.publish(self.base + '/status', 'offline', qos=1, retain=True).wait_for_publish(1.0)
        except Exception:
            pass
        try:
            self.client.disconnect()
            self.client.loop_stop()
        except Exception:
            pass

    # ------------------------------------------------------------------ paho callbacks (network thread)
    def _on_connect(self, client, userdata, flags, rc, props=None):
        ok = (rc == 0) if isinstance(rc, int) else not getattr(rc, 'is_failure', False)
        if not ok:
            self.error = 'connect failed: %s' % rc
            print('[pyterm] mqtt: %s' % self.error)
            return
        self.connected = True
        self.error = None
        self.inbox.put(('_connected', None))
        self._wake()
        print('[pyterm] mqtt: connected to %s:%s, topics %s/#' % (self.cfg['host'], self.cfg['port'], self.base))
        if self.cfg['allow_control']:
            client.subscribe(self.base + '/set/#', qos=1)
        else:
            for flag, keys in (('allow_alarms', ALARM_KEYS), ('allow_shows', SHOW_KEYS)):
                if self.cfg[flag]:
                    for k in keys:
                        client.subscribe(self.base + '/set/' + k, qos=1)
        client.subscribe(self.cfg['discovery_prefix'] + '/status', qos=1)   # HA restart -> resend discovery

    def _on_disconnect(self, client, userdata, *args):
        if self.connected and not getattr(self, 'stopping', False):
            print('[pyterm] mqtt: disconnected (%s) - reconnecting' % (args[-2] if len(args) >= 2 else ''))
        self.connected = False

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8', 'replace')
        except Exception:
            return
        if self.cfg.get('debug'):
            print('[mqtt] <- %s  %s' % (msg.topic, payload[:120]))
        if msg.topic == self.cfg['discovery_prefix'] + '/status':
            if payload == 'online':
                self.inbox.put(('_connected', None))
            return
        key = msg.topic[len(self.base + '/set/'):]
        self.inbox.put((key, payload))
        self._wake()

    def _wake(self):
        """wake the app's main loop (it sleeps while nothing moves); SDL event posting is thread safe"""
        try:
            import pygame
            pygame.event.post(pygame.event.Event(pygame.USEREVENT, mqtt=True))
        except Exception:
            pass

    # ------------------------------------------------------------------ publishing
    def pub(self, key, value, retain=True, force=False):
        if not (self.client and self.connected):
            return
        payload = value if isinstance(value, str) else json.dumps(value)
        if retain and not force and self.last.get(key) == payload:
            return
        if retain:
            self.last[key] = payload
        info = self.client.publish('%s/%s' % (self.base, key), payload, qos=0, retain=retain)
        if self.cfg.get('debug'):
            print('[mqtt] -> %s/%s  %s%s' % (self.base, key, payload[:120], '' if info.rc == 0 else '  (FAILED rc=%s)' % info.rc))

    def event(self, kind, **data):
        data['event_type'] = kind
        self.pub('event', data, retain=False)

    # ------------------------------------------------------------------ discovery
    def _options(self):
        from . import backgrounds, cursors, effects, fonts, themes
        return {
            'theme': sorted(themes.list_themes()),
            'background': ['theme default'] + sorted(b for b in backgrounds.BACKGROUNDS),
            'letter_effect': ['theme default'] + list(effects.APPEAR),
            'delete_effect': ['theme default'] + list(effects.VANISH),
            'cursor': ['theme default'] + list(cursors.CURSORS),
            'font': ['theme default'] + [f for f in fonts.list_fonts() if not f.startswith('sys:')],
        }

    def discovery(self):
        if not self.cfg['discovery']:
            return
        pre = self.cfg['discovery_prefix']
        dev = {'identifiers': ['pyterm_' + self.dev], 'name': self.name, 'manufacturer': 'pyterm',
               'model': 'pixel art terminal', 'sw_version': __version__}
        avail = {'availability_topic': self.base + '/status'}
        b = self.base
        ents = []

        def add(comp, oid, name, **kw):
            conf = dict(name=name, unique_id='pyterm_%s_%s' % (self.dev, oid), device=dev, **avail)
            conf.update(kw)
            ents.append((comp, oid, conf))

        add('event', 'terminal', 'Terminal event', state_topic=b + '/event', icon='mdi:console',
            event_types=['command_failed', 'command_succeeded', 'long_command', 'error_output', 'bell',
                         'alarm_started', 'alarm_dismissed', 'alarm_finished', 'alarm_stopped', 'show_started'])
        add('binary_sensor', 'alarm_active', 'Alarm active', state_topic=b + '/alarm_active', device_class='safety',
            icon='mdi:alarm-light')
        add('sensor', 'alarm_state', 'Alarm', state_topic=b + '/alarm', icon='mdi:alarm-bell')
        if self.cfg['allow_alarms']:
            from . import alarms
            for name, cls in alarms.ALARMS.items():
                add('button', 'alarm_' + name, 'Alarm %s' % (cls.label or name), icon=cls.ha_icon,
                    command_topic=b + '/set/alarm', payload_press=name)
            add('button', 'alarm_stop', 'Stop alarm', command_topic=b + '/set/alarm_stop', icon='mdi:alarm-off')
            add('text', 'alarm_message', 'Alarm message', command_topic=b + '/set/alarm_message',
                state_topic=b + '/alarm_message', max=120, icon='mdi:message-alert')
            add('number', 'alarm_duration', 'Alarm duration', command_topic=b + '/set/alarm_duration',
                state_topic=b + '/alarm_duration', min=0, max=600, step=5, unit_of_measurement='s', mode='box',
                icon='mdi:timer-outline')
        if self.cfg['allow_shows']:
            from . import shows
            for name, cls in shows.SHOWS.items():
                add('button', 'show_' + name, 'Show %s' % (cls.label or name), icon=cls.ha_icon,
                    command_topic=b + '/set/show', payload_press=name)
            add('button', 'show_stop', 'Stop shows', command_topic=b + '/set/show_stop', icon='mdi:stop-circle-outline')
        add('binary_sensor', 'last_failed', 'Last command failed', state_topic=b + '/last_failed', device_class='problem')
        add('binary_sensor', 'active', 'User active', state_topic=b + '/active', icon='mdi:keyboard')
        add('sensor', 'last_exit', 'Last exit code', state_topic=b + '/last_exit', icon='mdi:numeric')
        add('sensor', 'last_duration', 'Last command duration', state_topic=b + '/last_duration',
            unit_of_measurement='s', device_class='duration', state_class='measurement')
        add('sensor', 'output_rate', 'Output rate', state_topic=b + '/output_rate', unit_of_measurement='chars/s',
            state_class='measurement', icon='mdi:speedometer')
        add('sensor', 'typing_speed', 'Typing speed', state_topic=b + '/typing_speed', unit_of_measurement='chars/min',
            state_class='measurement', icon='mdi:keyboard-outline')
        add('sensor', 'typing_wpm', 'Typing speed WPM', state_topic=b + '/typing_wpm', unit_of_measurement='WPM',
            state_class='measurement', icon='mdi:keyboard-variant')
        add('sensor', 'keystrokes', 'Keystrokes', state_topic=b + '/keystrokes', state_class='total_increasing',
            icon='mdi:counter')
        add('sensor', 'theme_state', 'Theme', state_topic=b + '/theme', icon='mdi:palette')
        add('binary_sensor', 'shell_integration', 'Shell integration', state_topic=b + '/shell_integration',
            entity_category='diagnostic', icon='mdi:console-network')
        if self.cfg['publish_text']:
            add('sensor', 'last_command', 'Last command', state_topic=b + '/last_command', icon='mdi:console-line')
            add('sensor', 'last_error', 'Last error', state_topic=b + '/last_error', icon='mdi:alert')
        if self.cfg['allow_control']:
            opts = self._options()
            for key, name, icon in (('theme', 'Theme select', 'mdi:palette'), ('background', 'Background', 'mdi:image'),
                                    ('letter_effect', 'Letter effect', 'mdi:creation'),
                                    ('delete_effect', 'Delete effect', 'mdi:eraser'),
                                    ('cursor', 'Cursor', 'mdi:cursor-text'), ('font', 'Font', 'mdi:format-font')):
                add('select', key, name, command_topic=b + '/set/' + key, state_topic=b + '/' + key,
                    options=opts[key], icon=icon)
            for key, name, icon in (('zen', 'Zen mode', 'mdi:meditation'), ('sound', 'Sound', 'mdi:volume-high'),
                                    ('mine', 'Emerald mine', 'mdi:pickaxe'), ('scroller', 'Sine scroller', 'mdi:text-shadow')):
                add('switch', key, name, command_topic=b + '/set/' + key, state_topic=b + '/' + key, icon=icon)
            add('number', 'bg_dim', 'Background brightness', command_topic=b + '/set/bg_dim', state_topic=b + '/bg_dim',
                min=0, max=1, step=0.05, mode='slider', icon='mdi:brightness-6')
            add('number', 'volume', 'Volume', command_topic=b + '/set/volume', state_topic=b + '/volume',
                min=0, max=1, step=0.05, mode='slider', icon='mdi:volume-medium')
            add('text', 'notify', 'Show message', command_topic=b + '/set/notify', max=200, icon='mdi:message-text')
            add('text', 'scroller_text', 'Scroller text', command_topic=b + '/set/scroller_text', max=255,
                icon='mdi:format-text')
            for key, name, icon in (('screenshot', 'Screenshot', 'mdi:camera'),
                                    ('next_theme', 'Next theme', 'mdi:skip-next')):
                add('button', key, name, command_topic=b + '/set/' + key, icon=icon)
        for comp, oid, conf in ents:
            self.client.publish('%s/%s/pyterm_%s/%s/config' % (pre, comp, self.dev, oid), json.dumps(conf), qos=1, retain=True)

    # ------------------------------------------------------------------ state
    def publish_state(self, force=False):
        app = self.app
        th = app.theme
        cfg = app.cfg
        self.pub('theme', th.get('name', ''), force=force)
        bg = cfg.get('background')
        self.pub('background', bg[0] if bg and len(bg) == 1 else 'theme default', force=force)
        self.pub('letter_effect', cfg.get('letter_effect') or 'theme default', force=force)
        self.pub('delete_effect', cfg.get('delete_effect') or 'theme default', force=force)
        self.pub('cursor', cfg.get('cursor_style') or 'theme default', force=force)
        self.pub('font', getattr(app, 'font_override', None) or 'theme default', force=force)
        self.pub('zen', 'ON' if app.zen is not None else 'OFF', force=force)
        self.pub('sound', 'ON' if app.sound.enabled else 'OFF', force=force)
        self.pub('mine', 'ON' if any(p.mine for p in app.all_panes()) else 'OFF', force=force)
        self.pub('scroller', 'ON' if self._scroller_on() else 'OFF', force=force)
        self.pub('bg_dim', '%.2f' % float(th.get('bg_dim', 0.4)), force=force)
        self.pub('volume', '%.2f' % float(app.sound.volume), force=force)

    def _scroller(self):
        plugins = getattr(self.app.plugins, 'plugins', {})       # keyed by file path
        p = next((p for p in plugins.values() if getattr(p, 'name', '') == 'sine_scroller'), None)
        return getattr(p, 'module', None)

    def _scroller_on(self):
        m = self._scroller()
        if not m:
            return False
        on = m.S.get('on')
        return bool(on if on is not None else (self.app.theme.get('plugins') or {}).get('sine_scroller', {}).get('enabled'))

    # ------------------------------------------------------------------ hooks called by the app (main thread)
    def command_done(self, exit_code, secs, cmdline='', cwd=None):
        if not self.cmds_seen:
            self.cmds_seen = True
            self.pub('shell_integration', 'ON')
        exit_code = int(exit_code or 0)
        failed = bool(exit_code)
        self.pub('last_exit', str(exit_code))
        self.pub('last_duration', '%.1f' % secs)
        self.pub('last_failed', 'ON' if failed else 'OFF')
        data = {'exit_code': exit_code, 'duration': round(secs, 2)}
        if self.cfg['publish_text']:
            cmd = (cmdline or '').strip()[:200]
            data['command'] = cmd
            if cwd:
                data['cwd'] = cwd
            self.pub('last_command', cmd or '-')
        self.event('command_failed' if failed else 'command_succeeded', **data)
        if secs >= float(self.cfg['long_command']):
            self.event('long_command', ok=not failed, **data)

    def error_output(self, text):
        now = time.time()
        if now - self.last_err_t < 5:          # at most one error event per 5 seconds
            return
        self.last_err_t = now
        data = {}
        if self.cfg['publish_text']:
            line = ''
            for ln in ANSI.sub('', text).splitlines():
                if re.search(r'error|exception|traceback|fatal|failed', ln, re.I):
                    line = ln.strip()
            line = line[:120]
            data['line'] = line
            self.pub('last_error', line or '-')
        self.event('error_output', **data)

    def publish_typing(self, force=False):
        cpm = signals.typing_speed()
        self.pub('typing_speed', str(int(round(cpm))), force=force)
        self.pub('typing_wpm', str(int(round(cpm / 5))), force=force)       # 5 characters = 1 word
        self.pub('keystrokes', str(signals.keys_total), force=force)

    def initial_state(self):
        """everything Home Assistant shows, so no entity stays 'unknown' after connecting"""
        self.publish_state(force=True)
        self.pub('active', 'ON' if self.active else 'OFF', force=True)
        self.pub('last_failed', self.last.get('last_failed', 'OFF'), force=True)
        self.pub('last_exit', self.last.get('last_exit', '0'), force=True)
        self.pub('last_duration', self.last.get('last_duration', '0'), force=True)
        self.pub('output_rate', self.last.get('output_rate', '0'), force=True)
        self.pub('shell_integration', 'ON' if self.cmds_seen else 'OFF', force=True)
        self.publish_typing(force=True)
        a = self.app.alarm
        self.pub('alarm_active', 'ON' if a else 'OFF', force=True)
        self.pub('alarm', getattr(a, 'kind', 'none') if a else 'none', force=True)
        self.pub('alarm_message', self.alarm_message, force=True)
        self.pub('alarm_duration', '%g' % self.alarm_duration, force=True)
        if self.cfg['publish_text']:
            self.pub('last_command', self.last.get('last_command', '-'), force=True)
            self.pub('last_error', self.last.get('last_error', '-'), force=True)

    def frame(self, dt):
        """called by the app every frame - and also while it sleeps (eco mode), so timers use the clock"""
        app = self.app
        changed = False
        while True:
            try:
                key, val = self.inbox.get_nowait()
            except queue.Empty:
                break
            if key == '_connected':
                self.client.publish(self.base + '/status', 'online', qos=1, retain=True)
                self.discovery()
                self.initial_state()
                continue
            try:
                self.handle(key, val)
            except Exception as e:
                app.plugins.log('mqtt: bad command %s=%r: %s' % (key, val, e))
                print('[pyterm] mqtt: bad command %s=%r: %s' % (key, val, e))
            changed = True
        if changed:
            self.publish_state()
            app.anim_until = max(getattr(app, 'anim_until', 0), app.t + 1.0)    # render the change right away
        if signals.bell != self.last_bell:
            self.last_bell = signals.bell
            self.event('bell')
        active = signals.recent(signals.typing, 120)
        if active != self.active:
            self.active = active
            self.pub('active', 'ON' if active else 'OFF')
        now = time.time()
        if now >= self.next_periodic:
            self.next_periodic = now + 5.0
            rate = max((p.rate for p in app.tab.panes()), default=0.0)
            self.pub('output_rate', str(int(rate)))
            self.publish_typing()
            self.publish_state()

    def rediscover(self):
        """a plugin registered a new alarm -> publish its button"""
        if self.connected:
            self.inbox.put(('_connected', None))
            self._wake()

    def show_started(self, name):
        self.event('show_started', show=name)

    def alarm_changed(self, alarm, old=None):
        """called by the app when an alarm starts (alarm) or ends (alarm=None, old=the finished one)"""
        if alarm:
            self.pub('alarm_active', 'ON')
            self.pub('alarm', alarm.kind)
            self.event('alarm_started', alarm=alarm.kind, message=alarm.message)
        else:
            self.pub('alarm_active', 'OFF')
            self.pub('alarm', 'none')
            if old is not None:
                kind = 'alarm_dismissed' if old.dismissed else \
                    'alarm_stopped' if getattr(old, 'remote_stop', False) else 'alarm_finished'
                self.event(kind, alarm=getattr(old, 'kind', old.name),
                           seconds=round(old.t, 1))

    # ------------------------------------------------------------------ remote control (main thread)
    def handle(self, key, val):
        from . import themes
        app = self.app
        cfg = app.cfg
        v = val.strip()
        if key in ALARM_KEYS:
            if not self.cfg['allow_alarms']:
                return
            if key == 'alarm':
                from . import alarms
                name, msg, dur, snd = alarms.parse(v)
                app.trigger_alarm(name, msg or self.alarm_message, dur or self.alarm_duration or None, snd)
            elif key == 'alarm_stop':
                if app.alarm:
                    app.alarm.remote_stop = True
                app.stop_alarm()
            elif key == 'alarm_message':
                self.alarm_message = v[:120]
                self.pub('alarm_message', self.alarm_message)
            elif key == 'alarm_duration':
                self.alarm_duration = max(0.0, float(v or 0))
                self.pub('alarm_duration', '%g' % self.alarm_duration)
            return
        if key in SHOW_KEYS:
            if not self.cfg['allow_shows']:
                return
            if key == 'show':
                from . import shows
                name, opts = shows.parse(v)
                app.trigger_show(name, **opts)
            else:
                app.stop_shows()
            return
        if not self.cfg['allow_control']:
            return
        on = v.upper() in ('ON', '1', 'TRUE')
        default = v.lower() in ('theme default', 'default', '')
        if key == 'theme':
            if v in themes.list_themes():
                for k in ('background', 'letter_effect', 'delete_effect', 'cursor_style', 'cursor_effects'):
                    cfg[k] = None
                app.apply_theme(themes.load_theme(v))
                app.notify('theme: %s  (Home Assistant)' % v)
        elif key == 'next_theme':
            names = list(themes.list_themes())
            n = app.cycle(names, app.theme['name'])
            for k in ('background', 'letter_effect', 'delete_effect', 'cursor_style', 'cursor_effects'):
                cfg[k] = None
            app.apply_theme(themes.load_theme(n))
        elif key == 'background':
            cfg['background'] = None if default else [v]
            app.apply_theme(app.theme)
        elif key in ('letter_effect', 'delete_effect'):
            cfg[key] = None if default else v
        elif key == 'cursor':
            cfg['cursor_style'] = None if default else v
            for p in app.all_panes():
                p.reset_cursor()
        elif key == 'font':
            app.font_override = None if default else v
            app.set_font(app._load_font_for(app.theme))
        elif key == 'zen':
            if on != (app.zen is not None):
                app.toggle_zen()
        elif key == 'sound':
            app.sound.enabled = on
        elif key == 'mine':
            cfg['miner'] = on
            app.apply_theme(app.theme)
        elif key == 'scroller':
            m = self._scroller()
            if m:
                m.S['on'] = on
            else:
                app.notify('sine scroller plugin not loaded (plugins off or disabled?)', 6)
        elif key == 'scroller_text':
            m = self._scroller()
            if m:
                pl = app.theme.setdefault('plugins', {})
                pl.setdefault('sine_scroller', {})['text'] = '      ' + v.upper() + '   ***   '
                m.S['on'] = True
        elif key == 'bg_dim':
            app.theme['bg_dim'] = max(0.0, min(1.0, float(v)))
            app._bg_t = 99            # redraw the background now
        elif key == 'volume':
            app.sound.volume = max(0.0, min(1.0, float(v)))
        elif key == 'notify':
            if v:
                app.notify(v[:200], 8)
        elif key == 'fireworks':
            app.trigger_show('fireworks')
        elif key == 'screenshot':
            app.screenshot()
