#!/usr/bin/env bash

#brew: ranger
install() {
  local DEST=~/.config/ranger

  if [[ ! -a $DEST ]]; then
    mkdir $DEST
  fi

  ln -s -f $ROOT/ranger/commands.py $DEST/commands.py
  ln -s -f $ROOT/ranger/rc.conf     $DEST/rc.conf
  ln -s -f $ROOT/ranger/rifle.conf  $DEST/rifle.conf
  ln -s -f $ROOT/ranger/scope.sh    $DEST/scope.sh

  echo "source $ROOT/ranger/bashrc.config.sh" >> $BASHRC
  echo "source $ROOT/ranger/bashrc.aliases.sh" >> $BASHRC
}
