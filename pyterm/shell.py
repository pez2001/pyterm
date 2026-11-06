"""Shell integration auto-injection (OSC 133 command blocks + OSC 7 cwd).
Only applied when the shell command is a bare shell name/path, so custom
commands are never touched. Disable with  shell_integration: false."""
from __future__ import annotations

import os
import shlex

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')   # bundled assets (themes, fonts, sounds, plugins, shell, config.yaml)
SHELL_DIR = os.path.join(ROOT, 'shell')


def integrate(cmd):
    if not cmd or not isinstance(cmd, str):
        return cmd
    try:
        parts = shlex.split(cmd, posix=os.name != 'nt')
    except ValueError:
        return cmd
    if len(parts) != 1:
        return cmd
    exe = os.path.basename(parts[0].strip('"')).lower()
    if exe in ('pwsh', 'pwsh.exe', 'powershell', 'powershell.exe'):
        ps1 = os.path.join(SHELL_DIR, 'pyterm.ps1')
        if os.path.exists(ps1):
            return '%s -NoLogo -NoExit -Command ". \'%s\'"' % (cmd, ps1.replace("'", "''"))
    elif exe in ('bash', 'bash.exe'):
        rc = os.path.join(SHELL_DIR, 'pyterm.bash')
        if os.path.exists(rc):
            return '%s --rcfile %s -i' % (cmd, shlex.quote(rc) if os.name != 'nt' else '"%s"' % rc)
    elif exe in ('cmd', 'cmd.exe'):
        return '%s /k "prompt $e]133;D$e\\$e]133;A$e\\$e]9;9;$P$e\\$P$G$e]133;B$e\\"' % cmd
    return cmd
