#!/usr/bin/env bash

#cask: iterm2
#pip: colorz
install() {
  local HERE=$ROOT/iterm
  local DEST="$HOME/Library/Application Support/iTerm2/DynamicProfiles"

  if [[ ! -a "$DEST" ]]; then
    mkdir "$DEST"
  fi

  ln -s -f "$HERE/profiles.json" "$DEST/profiles.json"

  echo >> $BASHRC
  echo "# iTerm" >> $BASHRC
  echo "source $HERE/bashrc.aliases.sh" >> $BASHRC
}
