alias dot-bash="cd $HOME/dotfiles/targets/bash"
alias dot-bash-install="vim $HOME/dotfiles/targets/bash/install.sh"
alias dot-bash-aliases="vim $HOME/dotfiles/targets/bash/bashrc.aliases.sh"
alias dot-bash-config="vim $HOME/dotfiles/targets/bash/bashrc.config.sh"
alias dot-bash-functions="vim $HOME/dotfiles/targets/bash/bashrc.functions.sh"
alias dot-bash-theme="vim $HOME/dotfiles/targets/bash/bashrc.theme.sh"

alias bashrc="source $HOME/.bashrc; log 'Reloaded .bashrc'"

alias sudo="sudo "

# Fix after binary cat
alias fixme="echo -e "\033c""
alias space="echo;echo;echo;echo;echo;echo;echo"

# Easier navigation
alias u="cd .."
alias uu="cd ../.."
alias uuu="cd ../../.."
alias uuuu="cd ../../../.."
alias b="cd -"

# Shortcuts
alias grep="grep --color=auto"
alias fgrep="fgrep --color=auto"
alias egrep="egrep --color=auto"

alias ls="ls -G"
alias ll="ls -G -lah"
