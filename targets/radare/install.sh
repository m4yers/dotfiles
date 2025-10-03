#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

install_mac() {
  brew install radare2
}

install_ubuntu() {
  # Not needed yet
  true
}

install_centos() {
  # Not needed yet
  true
}

# depends-on: repos
install() {
  local this=$(get_source)

  if is_mac; then
    install_mac
  fi

  if is_ubuntu; then
    install_ubuntu
  fi

  if is_centos; then
    install_centos
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
