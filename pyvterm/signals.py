"""Tiny shared blackboard so background scenes can react to the terminal
(typing, command results, bell, output energy) without knowing the app."""
import collections
import time

typing = 0.0      # time.time() of the last letters printed in the focused pane
puts = 0          # total letters printed (focused pane)
enter = 0.0       # last newline in the focused pane
cmd = None        # (exit_code, seconds, time.time()) of the last finished command
bell = 0.0
energy = 0.0


def recent(ts, secs):
    return time.time() - ts < secs

# keys the scenes may react to (timestamps of the last press, set by the app before the key goes to the shell)
left = 0.0
right = 0.0
boost = 0.0

# focused cursor position in virtual window pixels (for backgrounds that react to it)
cursor_x = None
cursor_y = None

# letters printed in the focused pane: (seq, char, x, y, typed) in virtual window pixels (cell centre);
# typed = True when it is the echo of a key the user just pressed.
# Scenes remember the last seq they consumed. Capped per frame so floods stay cheap.
letters = collections.deque(maxlen=256)
letter_seq = 0

# a scene may ask for a screen shake (0..1); the app consumes it
shake = 0.0


def take_letters(last_seq):
    """letters newer than last_seq -> (list, new_last_seq)"""
    if not letters or letters[-1][0] <= last_seq:
        return [], last_seq
    out = [l for l in letters if l[0] > last_seq]
    return out, letters[-1][0]

# keys the user typed (printable characters sent to the program): timestamps for the typing speed
key_times = collections.deque(maxlen=2000)
keys_total = 0


def typing_speed(window=20.0):
    """characters per minute over the last `window` seconds"""
    now = time.time()
    while key_times and now - key_times[0] > window:
        key_times.popleft()
    if not key_times:
        return 0.0
    span = max(5.0, now - key_times[0])          # a short burst counts at its real pace, not spread over 20 s
    return len(key_times) * 60.0 / span
