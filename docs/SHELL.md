# Shell integration (command blocks)

pyterm understands the FinalTerm / VS Code / Windows Terminal escape codes:

| sequence | meaning |
|---|---|
| `OSC 133 ; A` | prompt starts |
| `OSC 133 ; B` | command input starts (after the prompt) |
| `OSC 133 ; C` | command executed, output starts |
| `OSC 133 ; D ; <exit>` | command finished |
| `OSC 7 ; file://host/path`, `OSC 9 ; 9 ; path` | current directory |

With them you get:

* a gutter bar per command: **blue** = running, **green** = exit 0, **red** = failed; hover it for exit code,
  duration and the command line
* a faint separator above every prompt
* **Ctrl+Shift+Up/Down** jumps between prompts in the scrollback
* **Ctrl+Shift+A** copies the output of the last finished command
* a notification (+ sound, + flash when pyterm is in the background) when a command took longer than
  `notify_after` seconds; plugins get a `command_done(exit_code, seconds, cmdline)` event
  (the fireworks plugin celebrates successful long builds)
* new tabs / splits open in the directory of the focused pane

## Setup

pyterm injects it automatically when the shell is started by its bare name (`shell_integration: true`):

* **PowerShell 5.1 / 7** — dot-sources `shell/pyterm.ps1` (wraps your existing prompt; uses PSReadLine for the
  "command executed" mark)
* **bash** — starts with `--rcfile shell/pyterm.bash`, which sources your `~/.bashrc` first
* **cmd.exe** — sets a `PROMPT` with the marks (no exit codes in cmd)
* **zsh** — add to `~/.zshrc`:  `[[ "$TERM_PROGRAM" == pyterm ]] && source /path/to/pyterm/shell/pyterm.zsh`

Your own prompt themes (oh-my-posh, starship …) keep working: the scripts wrap whatever prompt is defined.
The demo shell (`--demo`) emits the marks too, so you can try it without setup (`error`, `sleep 9`).
