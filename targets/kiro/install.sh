#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

link_config_dir() {
  log "Linking $1"
  local directory=~/.kiro/$1
  [ -d "$directory" ] && rm -rf "$directory"
  [ -L "$directory" ] && rm -f "$directory"
  ln -s -f "$this/$1" "$directory"
}

install() {
  local this=$(get_source)

  log "Creating ~/.kiro"
  mkdir -p ~/.kiro

  link_config_dir settings
  link_config_dir agents
  link_config_dir skills
  link_config_dir steering

  bash_init_config
  bash_section "Kiro configuration"
  bash_export_source "$this/bashrc.aliases.sh"
}

if ! is_sourced; then
  install
fi
