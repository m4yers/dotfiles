#!/usr/bin/env bash

#brew: bash, bash-completion2
#npm: pygmentize
install() {
  echo >> $BASHRC
  echo "# Bash" >> $BASHRC
  echo "source $THIS/bashrc.config.sh" >> $BASHRC
  echo "source $THIS/bashrc.aliases.sh" >> $BASHRC
  echo "source $THIS/bashrc.functions.sh" >> $BASHRC
  echo "source $THIS/bashrc.theme.sh" >> $BASHRC
  echo "source /usr/local/share/bash-completion/bash_completion" >> $BASHRC
}
