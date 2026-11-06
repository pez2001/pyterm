# MQTT & Home Assistant

Completely optional and **off by default**. Nothing is imported or sent unless you enable it.

```bash
pip install paho-mqtt
python -m pyterm --mqtt mqtt://user:password@homeassistant.local:1883     # just this run
python -m pyterm --mqtt                                                    # use the mqtt: block of config.yaml
python -m pyterm --no-mqtt                                                 # off, even if config.yaml enables it
```

or permanently in `config.yaml`:

```yaml
mqtt:
  enabled: true
  host: homeassistant.local
  port: 1883            # mqtts://... or tls: true -> 8883
  username: pyterm
  password: secret
  publish_text: false   # true = also send command lines and the last error line
  allow_control: true   # false = Home Assistant can only watch, not change anything
  allow_alarms: true    # alarms work even with allow_control: false; false = no alarms
  long_command: 10      # seconds -> long_command event
```

With Home Assistant's MQTT integration (Mosquitto add-on) the terminal appears by itself under
**Settings → Devices → "pyterm <hostname>"** (MQTT discovery). Each computer is its own device
(`device_id` defaults to the hostname).

## What Home Assistant gets

| entity | |
|---|---|
| `event.…_terminal_event` | `command_failed`, `command_succeeded`, `long_command`, `error_output`, `bell` – attributes `exit_code`, `duration` (+ `command`, `cwd`, `line` with `publish_text`) |
| `binary_sensor.…_last_command_failed` | on while the last command's exit code ≠ 0 (device class *problem*) |
| `binary_sensor.…_user_active` | typed something in the last 2 minutes |
| `sensor.…_last_exit_code`, `…_last_command_duration` | |
| `sensor.…_output_rate` | characters per second (every 5 s) |
| `sensor.…_typing_speed`, `…_typing_speed_wpm` | your typing speed in characters per minute / words per minute (last 20 s, every 5 s) |
| `sensor.…_keystrokes` | keys typed since pyterm started (total, for daily statistics) |
| `sensor.…_theme` | current theme |
| `sensor.…_last_command`, `…_last_error` | **only with `publish_text: true`** – e.g. for a text display or printer |

`error_output` fires when error-looking output appears (Traceback, error:, FATAL …), at most every 5 s.
Exit codes need shell integration (on by default for PowerShell, bash, cmd; zsh see docs/SHELL.md).

`binary_sensor.…_shell_integration` (diagnostic) turns on with the first finished command. If it stays off,
the shell doesn't report command results (exit codes, durations, failed/succeeded events need it - see
docs/SHELL.md); output rate, user active, theme, error output and bell work without it.

## Troubleshooting

```bash
python -m pyterm --mqtt mqtt://user:pass@homeassistant.local --mqtt-debug
```

prints every message sent (`[mqtt] -> pyterm/mypc/last_exit 1`) and received (`[mqtt] <- …/set/theme c64`).
If messages go out but Home Assistant shows nothing: check the MQTT integration has discovery enabled
(prefix `homeassistant`), or look at the topics with MQTT Explorer / `mosquitto_sub -t 'pyterm/#' -v`.

## What Home Assistant can change (`allow_control: true`)

| entity | |
|---|---|
| `select` theme, background, letter effect, delete effect, cursor, font | `theme default` restores the theme's own choice |
| `switch` zen mode, sound, emerald mine, sine scroller | |
| `number` background brightness, volume | 0 … 1 |
| `text` show message | shown on screen for 8 s |
| `text` scroller text | runs through the big Amiga sine scroller |
| `button` fireworks, screenshot, next theme | |

Deliberately **not** possible: typing into the terminal or running commands. Remote control is limited to looks.

## Alarms

Full-window alarm with sound, until someone presses a key or clicks (the key is swallowed, it never reaches
the program), or until the duration runs out. Alarms ring even when the theme's key sounds are switched off.

| alarm | looks / sounds like | default duration |
|---|---|---|
| `redalert` | screen turns red and pulses, rotating beacon light, klaxon | 30 s |
| `warning` | crawling yellow/black hazard tape, flashing corner lamps, beep-beep | 20 s |
| `doorbell` | card bounces in with a swinging bell, ding-dong (once) | 8 s |
| `timer` | shaking, ringing alarm clock showing the real time | 30 s |
| `calm` | soft blue breathing glow, gentle chime – reminders, wake-up | 20 s |
| *plugins* | e.g. `party` from `plugins/party_alarm.py` – write your own, see docs/PLUGINS.md | |

Entities:

| entity | |
|---|---|
| `button` Alarm red alert / warning / doorbell / timer / calm reminder (+ plugin alarms) | starts it with the current *Alarm message* |
| `button` Stop alarm | |
| `text` Alarm message, `number` Alarm duration | used by the buttons (duration 0 = the alarm's default) |
| `binary_sensor` Alarm active, `sensor` Alarm | which alarm is running (`none`) |
| events on `event.…_terminal_event` | `alarm_started`, `alarm_dismissed` (someone pressed a key – attribute `seconds` = reaction time), `alarm_finished` (ran out, nobody there), `alarm_stopped` (stopped from Home Assistant) |

Raw topic `pyterm/<device_id>/set/alarm` takes `doorbell`, `redalert Water in the basement!` or JSON
`{"type": "timer", "message": "Pizza", "duration": 60, "sound": false}`.

```yaml
# water leak sensor -> red alert on the terminal; if nobody acknowledges within 30 s, call the phone
automation:
  - alias: Leak alarm on the terminal
    triggers:
      - trigger: state
        entity_id: binary_sensor.basement_leak
        to: "on"
    actions:
      - action: mqtt.publish
        data:
          topic: pyterm/mypc/set/alarm
          payload: '{"type": "redalert", "message": "Water in the basement!", "duration": 120}'
      - wait_for_trigger:
          - trigger: state
            entity_id: event.pyterm_mypc_terminal_event
            attribute: event_type
            to: alarm_dismissed
        timeout: "00:00:30"
      - if: "{{ not wait.trigger }}"
        then:
          - action: notify.mobile_app_phone
            data: {message: "Water in the basement! (nobody at the PC)"}

# doorbell button -> doorbell alarm with a message
  - alias: Doorbell on the terminal
    triggers:
      - trigger: state
        entity_id: binary_sensor.front_doorbell
        to: "on"
    actions:
      - action: text.set_value
        target: {entity_id: text.pyterm_mypc_alarm_message}
        data: {value: "Someone is at the front door"}
      - action: button.press
        target: {entity_id: button.pyterm_mypc_alarm_doorbell}
```

## Example automations

**Living room lights flash red when a command fails**

```yaml
- alias: Terminal error -> lights flash red
  triggers:
    - trigger: state
      entity_id: event.pyterm_mypc_terminal_event
  conditions:
    - "{{ trigger.to_state.attributes.event_type == 'command_failed' }}"
  actions:
    - action: scene.create
      data: {scene_id: before_terminal_error, snapshot_entities: [light.living_room]}
    - repeat:
        count: 3
        sequence:
          - action: light.turn_on
            target: {entity_id: light.living_room}
            data: {rgb_color: [255, 0, 0], brightness: 255, transition: 0}
          - delay: {milliseconds: 300}
          - action: light.turn_off
            target: {entity_id: light.living_room}
            data: {transition: 0}
          - delay: {milliseconds: 300}
    - action: scene.turn_on
      target: {entity_id: scene.before_terminal_error}
```

**Show the error on a text display** (needs `publish_text: true`)

```yaml
- alias: Terminal error -> text display
  triggers:
    - trigger: state
      entity_id: event.pyterm_mypc_terminal_event
  conditions:
    - "{{ trigger.to_state.attributes.event_type in ['command_failed', 'error_output'] }}"
  actions:
    - action: text.set_value            # or notify.<your_display>, depending on the display integration
      target: {entity_id: text.my_text_display}
      data:
        value: >-
          {{ trigger.to_state.attributes.line
             or (trigger.to_state.attributes.command ~ ' -> exit ' ~ trigger.to_state.attributes.exit_code) }}
```

**Print a receipt when a long build finishes** (POS printer, needs `publish_text: true` for the command)

```yaml
- alias: Long terminal job -> receipt
  triggers:
    - trigger: state
      entity_id: event.pyterm_mypc_terminal_event
  conditions:
    - "{{ trigger.to_state.attributes.event_type == 'long_command' }}"
  actions:
    - action: notify.pos_printer        # your printer's notify service
      data:
        message: |
          ======== PYTERM ========
          {{ trigger.to_state.attributes.command }}
          {{ 'OK' if trigger.to_state.attributes.ok else 'FAILED (exit ' ~ trigger.to_state.attributes.exit_code ~ ')' }}
          took {{ trigger.to_state.attributes.duration | round(0) }} s
          {{ now().strftime('%d.%m.%Y %H:%M') }}
```

**Home Assistant → terminal**

```yaml
- alias: Doorbell -> terminal message
  triggers: [{trigger: state, entity_id: binary_sensor.doorbell, to: 'on'}]
  actions:
    - action: text.set_value
      target: {entity_id: text.pyterm_mypc_show_message}
      data: {value: "Someone is at the door!"}

- alias: Sunset -> cozy terminal
  triggers: [{trigger: sun, event: sunset}]
  actions:
    - action: select.select_option
      target: {entity_id: select.pyterm_mypc_theme_select}
      data: {option: neonsigns}

- alias: Dinner -> scroller
  triggers: [{trigger: state, entity_id: input_boolean.dinner_ready, to: 'on'}]
  actions:
    - action: text.set_value
      target: {entity_id: text.pyterm_mypc_scroller_text}
      data: {value: "dinner is ready - come downstairs"}
```

Entity ids follow the device name; check them under the device page in Home Assistant.

## Raw MQTT (Node-RED, scripts …)

Base topic `pyterm/<device_id>/`:

| topic | |
|---|---|
| `status` | `online` / `offline` (last will) |
| `event` | JSON `{"event_type": "command_failed", "exit_code": 1, "duration": 0.4, ...}` (not retained) |
| `last_exit`, `last_failed`, `last_duration`, `last_command`, `last_error`, `active`, `output_rate` | retained states |
| `theme`, `background`, `letter_effect`, `delete_effect`, `cursor`, `font`, `zen`, `sound`, `mine`, `scroller`, `bg_dim`, `volume` | retained states |
| `set/<name>` | commands: same names as above + `notify`, `scroller_text`, `fireworks`, `screenshot`, `next_theme` |
| `alarm`, `alarm_active`, `alarm_message`, `alarm_duration` / `set/alarm`, `set/alarm_stop` | alarms (see above) |

```bash
mosquitto_pub -h homeassistant.local -t pyterm/mypc/set/theme -m c64
mosquitto_pub -h homeassistant.local -t pyterm/mypc/set/notify -m "coffee is ready"
mosquitto_sub -h homeassistant.local -t 'pyterm/+/event' -v
```
