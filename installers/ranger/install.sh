#!/usr/bin/env bash

#brew: ranger, xpdf, exiftool, libcaca --with-imlib2
install() {
  local DEST=~/.config/ranger

  if [[ ! -a $DEST ]]; then
    mkdir $DEST
  fi

  ln -s -f $THIS/commands.py $DEST/commands.py
  ln -s -f $THIS/rc.conf     $DEST/rc.conf
  ln -s -f $THIS/rifle.conf  $DEST/rifle.conf
  ln -s -f $THIS/scope.sh    $DEST/scope.sh

  bash_section "Ranger"
  bash_export_source "$THIS/bashrc.config.sh"
  bash_export_source "$THIS/bashrc.aliases.sh"
}
