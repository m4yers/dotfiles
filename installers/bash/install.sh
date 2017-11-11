#!/usr/bin/env bash

#npm: pygmentize
install() {
  echo >> $BASHRC
  echo "# Bash" >> $BASHRC
  echo "source $THIS/bashrc.config.sh" >> $BASHRC
  echo "source $THIS/bashrc.aliases.sh" >> $BASHRC
  echo "source $THIS/bashrc.functions.sh" >> $BASHRC
  echo "source $THIS/bashrc.theme.sh" >> $BASHRC
  echo "source $(brew --prefix)/etc/bash_completion" >> $BASHRC
}
