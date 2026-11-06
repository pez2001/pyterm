# pyterm shell integration for bash (4.4+): OSC 133 command blocks + OSC 7 cwd.
# pyterm starts bash with  --rcfile <this file>  automatically. Manual use in ~/.bashrc:
#   [ "$TERM_PROGRAM" = pyterm ] && . /path/to/pyterm/shell/pyterm.bash
if [ -z "$__PYTERM_RC" ]; then
  __PYTERM_RC=1
  [ -f /etc/bash.bashrc ] && . /etc/bash.bashrc
  [ -f ~/.bashrc ] && . ~/.bashrc
fi
__pyterm_first=1
__pyterm_prompt() {
  local ec=$?
  [ -z "$__pyterm_first" ] && printf '\e]133;D;%s\a' "$ec"
  __pyterm_first=
  printf '\e]7;file://%s%s\a' "${HOSTNAME:-localhost}" "$PWD"
  return $ec
}
case "$PROMPT_COMMAND" in *__pyterm_prompt*) ;; *) PROMPT_COMMAND="__pyterm_prompt${PROMPT_COMMAND:+;$PROMPT_COMMAND}";; esac
case "$PS1" in *133\;A*) ;; *) PS1='\[\e]133;A\a\]'"$PS1"'\[\e]133;B\a\]';; esac
PS0='\e]133;C\a'
