alias sudo='sudo '

if is_mac; then
  alias ls='ls -G'
elif is_linux; then
  alias ls='ls --color'
fi

alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'
alias ll='ls -lah'
alias ggl='git log --graph --all --pretty --abbrev-commit --decorate'
