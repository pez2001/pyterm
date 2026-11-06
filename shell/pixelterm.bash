# pixelterm shell integration for bash (4.4+): OSC 133 command blocks + OSC 7 cwd.
# pixelterm starts bash with  --rcfile <this file>  automatically. Manual use in ~/.bashrc:
#   [ "$TERM_PROGRAM" = pixelterm ] && . /path/to/pixelterm/shell/pixelterm.bash
if [ -z "$__PIXELTERM_RC" ]; then
  __PIXELTERM_RC=1
  [ -f /etc/bash.bashrc ] && . /etc/bash.bashrc
  [ -f ~/.bashrc ] && . ~/.bashrc
fi
__pixelterm_first=1
__pixelterm_prompt() {
  local ec=$?
  [ -z "$__pixelterm_first" ] && printf '\e]133;D;%s\a' "$ec"
  __pixelterm_first=
  printf '\e]7;file://%s%s\a' "${HOSTNAME:-localhost}" "$PWD"
  return $ec
}
case "$PROMPT_COMMAND" in *__pixelterm_prompt*) ;; *) PROMPT_COMMAND="__pixelterm_prompt${PROMPT_COMMAND:+;$PROMPT_COMMAND}";; esac
case "$PS1" in *133\;A*) ;; *) PS1='\[\e]133;A\a\]'"$PS1"'\[\e]133;B\a\]';; esac
PS0='\e]133;C\a'
