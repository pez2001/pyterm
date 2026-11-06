# pyterm shell integration for zsh - add to ~/.zshrc:
#   [[ "$TERM_PROGRAM" == pyterm ]] && source /path/to/pyterm/shell/pyterm.zsh
autoload -Uz add-zsh-hook
typeset -g __pyterm_first=1
__pyterm_precmd() {
  local ec=$?
  [[ -z $__pyterm_first ]] && print -Pn "\e]133;D;${ec}\a"
  __pyterm_first=
  print -Pn "\e]7;file://${HOST}${PWD}\a"
  print -Pn "\e]133;A\a"
}
__pyterm_preexec() { print -Pn "\e]133;C\a" }
add-zsh-hook precmd __pyterm_precmd
add-zsh-hook preexec __pyterm_preexec
[[ $PS1 == *133\;B* ]] || PS1="$PS1%{$(print -n '\e]133;B\a')%}"
