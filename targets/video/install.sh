#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

install_mac() {
  brew install yt-dlp ffmpeg mkvtoolnix jq
}

install() {
  local this=$(get_source)

  if is_mac; then
    install_mac
  fi

  log "Linking scripts"
  bash_init_config
  bash_export_path "$this/scripts"
}

if ! is_sourced; then
  install
fi
