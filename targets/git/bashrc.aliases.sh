alias g='git '

alias gll='git log --graph --all --pretty --abbrev-commit --decorate'
alias gl1='git log --graph --all --pretty --decorate --stat --since="1 day ago"'
alias gl2='git log --graph --all --pretty --decorate --stat --since="2 days ago"'
alias gl3='git log --graph --all --pretty --decorate --stat --since="3 days ago"'
alias gl='git log --graph --all --oneline --decorate'

alias gs='git status '
alias ga='git add '
alias gc='git commit '

alias wip='git commit -a -m "Work In Progress..."'
alias squish='git status && git commit -a --amend -C HEAD'
