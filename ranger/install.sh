#!/usr/bin/env bash

#brew: ranger, xpdf, exiftool, libcaca --with-imlib2
install() {
  local DEST=~/.config/ranger

  if [[ ! -a $DEST ]]; then
    mkdir $DEST
  fi

  ln -s -f $ROOT/ranger/commands.py $DEST/commands.py
  ln -s -f $ROOT/ranger/rc.conf     $DEST/rc.conf
  ln -s -f $ROOT/ranger/rifle.conf  $DEST/rifle.conf
  ln -s -f $ROOT/ranger/scope.sh    $DEST/scope.sh

  echo >> $BASHRC
  echo "# Ranger" >> $BASHRC
  echo "source $ROOT/ranger/bashrc.config.sh" >> $BASHRC
  echo "source $ROOT/ranger/bashrc.aliases.sh" >> $BASHRC
}
