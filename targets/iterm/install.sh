#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

install_mac() {
  brew install iterm2
  # pip3 install iterm-theme-generator

}

# depends-on: brew, bash, python
install() {
  local this=$(get_source)

  if is_mac; then
    install_mac
  fi


  local dest="$HOME/Library/Application Support/iTerm2/DynamicProfiles"

  if [[ ! -a "$dest" ]]; then
    mkdir "$dest"
  fi

  ln -s -f "$this/profiles.json" "$dest/profiles.json"

  bash_init_config
  bash_export_path "$HOME/.iterm2"
}

if ! is_sourced; then
  install
fi
