alias dot-git="cd $HOME/dotfiles/targets/git"
alias dot-git-install="vim $HOME/dotfiles/targets/git/install.sh"
alias dot-git-alises="vim $HOME/dotfiles/targets/git/bashrc.aliases.sh"

alias g="git "

alias gll="git log --graph --all --pretty --abbrev-commit --decorate"
alias gl1="git log --graph --all --pretty --decorate --stat --since='1 day ago'"
alias gl2="git log --graph --all --pretty --decorate --stat --since='2 days ago'"
alias gl3="git log --graph --all --pretty --decorate --stat --since='3 days ago'"
alias gl="git log --graph --all --oneline --decorate"

alias gs="git status "
alias ga="git add "
alias gc="git commit "
alias gm="git mergetool "
alias gcpc="git cherry-pick --continue"
alias gcpa="git cherry-pick --abort"
alias gco="git checkout "
alias gcob="git checkout -b "

alias wip="git commit -a -m 'Work In Progress...'"
alias squish="git status && git commit -a --amend -C HEAD"
