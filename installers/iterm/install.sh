#!/usr/bin/env bash

#cask: iterm2
#pip: iterm-theme-generator
install() {
  local DEST="$HOME/Library/Application Support/iTerm2/DynamicProfiles"

  if [[ ! -a "$DEST" ]]; then
    mkdir "$DEST"
  fi

  ln -s -f "$THIS/profiles.json" "$DEST/profiles.json"

  bash_section "iTerm"
  bash_export_path "$HOME/.iterm2"
}
