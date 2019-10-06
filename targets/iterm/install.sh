#!/usr/bin/env bash

# depends-on: bash, brew, python
install() {
  brew cask install iterm2
  pip install iterm-theme-generator

  local DEST="$HOME/Library/Application Support/iTerm2/DynamicProfiles"

  if [[ ! -a "$DEST" ]]; then
    mkdir "$DEST"
  fi

  ln -s -f "$THIS/profiles.json" "$DEST/profiles.json"

  bash_init_config
  bash_export_path "$HOME/.iterm2"
}
