#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

# depends-on: repos, bash
install() {
  pip3 install ranger-fm

  local this=$(get_source)
  local dest=~/.config/ranger

  log "Linking configuration"
  if [[ ! -a $dest ]]; then
    mkdir $dest
  fi

  ln -s -f $this/rc.conf     $dest/rc.conf
  ln -s -f $this/rifle.conf  $dest/rifle.conf
  ln -s -f $this/scope.sh    $dest/scope.sh

  bash_init_config
  bash_section "Ranger configuration"
  bash_export_source "$this/bashrc.config.sh"
  bash_export_source "$this/bashrc.aliases.sh"
}

if ! is_sourced; then
  install
fi
