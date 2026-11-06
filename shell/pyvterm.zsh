# pyvterm shell integration for zsh - add to ~/.zshrc:
#   [[ "$TERM_PROGRAM" == pyvterm ]] && source /path/to/pyvterm/shell/pyvterm.zsh
autoload -Uz add-zsh-hook
typeset -g __pyvterm_first=1
__pyvterm_precmd() {
  local ec=$?
  [[ -z $__pyvterm_first ]] && print -Pn "\e]133;D;${ec}\a"
  __pyvterm_first=
  print -Pn "\e]7;file://${HOST}${PWD}\a"
  print -Pn "\e]133;A\a"
}
__pyvterm_preexec() { print -Pn "\e]133;C\a" }
add-zsh-hook precmd __pyvterm_precmd
add-zsh-hook preexec __pyvterm_preexec
[[ $PS1 == *133\;B* ]] || PS1="$PS1%{$(print -n '\e]133;B\a')%}"
