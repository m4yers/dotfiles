#!/usr/bin/env bash

#npm: pygmentize
install() {
  echo >> $BASHRC
  echo "# Bash" >> $BASHRC
  echo "source $ROOT/bash/bashrc.config.sh" >> $BASHRC
  echo "source $ROOT/bash/bashrc.aliases.sh" >> $BASHRC
  echo "source $ROOT/bash/bashrc.theme.sh" >> $BASHRC
  echo "source $(brew --prefix)/etc/bash_completion" >> $BASHRC
}
