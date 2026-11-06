# pixelterm shell integration for zsh - add to ~/.zshrc:
#   [[ "$TERM_PROGRAM" == pixelterm ]] && source /path/to/pixelterm/shell/pixelterm.zsh
autoload -Uz add-zsh-hook
typeset -g __pixelterm_first=1
__pixelterm_precmd() {
  local ec=$?
  [[ -z $__pixelterm_first ]] && print -Pn "\e]133;D;${ec}\a"
  __pixelterm_first=
  print -Pn "\e]7;file://${HOST}${PWD}\a"
  print -Pn "\e]133;A\a"
}
__pixelterm_preexec() { print -Pn "\e]133;C\a" }
add-zsh-hook precmd __pixelterm_precmd
add-zsh-hook preexec __pixelterm_preexec
[[ $PS1 == *133\;B* ]] || PS1="$PS1%{$(print -n '\e]133;B\a')%}"
