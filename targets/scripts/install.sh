#!/usr/bin/env bash

ROOT="$( cd "$( dirname "$0" )/../.." && pwd )"
source $ROOT/scripts/shared.sh

install() {
  local this=$(get_source)

  bash_init_config
  bash_export_path "$this/export"
}

if ! is_sourced; then
  install
fi
