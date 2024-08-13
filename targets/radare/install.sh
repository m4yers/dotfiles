#!/usr/bin/env bash

ROOT="$( cd "$( dirname "$0" )/../.." && pwd )"
source $ROOT/scripts/shared.sh

install_mac() {
  brew install radare2
}

install_linux() {
  # Not needed yet
  true
}

# depends-on: repos
install() {
  local this=$(get_source)

  if is_mac; then
    install_mac
  fi

  if is_linux; then
    install_linux
  fi

  log "Linking .radare2rc"
  ln -s -f "$this/radare2rc" "$HOME/.radare2rc"

  bash_init_config
  bash_section "Radare configuration"
  bash_export_source "$this/bashrc.aliases.sh"
}

if ! is_sourced; then
  install
fi
