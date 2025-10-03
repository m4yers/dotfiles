#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

install() {
  local this=$(get_source)

  log "Linking scripts"
  bash_init_config
  bash_export_path "$this/export"
}

if ! is_sourced; then
  install
fi
