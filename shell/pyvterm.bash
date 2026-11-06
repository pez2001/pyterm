# pyvterm shell integration for bash (4.4+): OSC 133 command blocks + OSC 7 cwd.
# pyvterm starts bash with  --rcfile <this file>  automatically. Manual use in ~/.bashrc:
#   [ "$TERM_PROGRAM" = pyvterm ] && . /path/to/pyvterm/shell/pyvterm.bash
if [ -z "$__PYVTERM_RC" ]; then
  __PYVTERM_RC=1
  [ -f /etc/bash.bashrc ] && . /etc/bash.bashrc
  [ -f ~/.bashrc ] && . ~/.bashrc
fi
__pyvterm_first=1
__pyvterm_prompt() {
  local ec=$?
  [ -z "$__pyvterm_first" ] && printf '\e]133;D;%s\a' "$ec"
  __pyvterm_first=
  printf '\e]7;file://%s%s\a' "${HOSTNAME:-localhost}" "$PWD"
  return $ec
}
case "$PROMPT_COMMAND" in *__pyvterm_prompt*) ;; *) PROMPT_COMMAND="__pyvterm_prompt${PROMPT_COMMAND:+;$PROMPT_COMMAND}";; esac
case "$PS1" in *133\;A*) ;; *) PS1='\[\e]133;A\a\]'"$PS1"'\[\e]133;B\a\]';; esac
PS0='\e]133;C\a'
