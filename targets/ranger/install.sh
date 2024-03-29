#!/usr/bin/env bash

# depends-on: brew, bash, python
install() {
  # GPL3(!)
  brew install ranger

  local DEST=~/.config/ranger

  if [[ ! -a $DEST ]]; then
    mkdir $DEST
  fi

  ln -s -f $THIS/rc.conf     $DEST/rc.conf
  ln -s -f $THIS/rifle.conf  $DEST/rifle.conf
  ln -s -f $THIS/scope.sh    $DEST/scope.sh

  bash_init_config
  bash_export_source "$THIS/bashrc.config.sh"
  bash_export_source "$THIS/bashrc.aliases.sh"
}
