#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

install() {
  log "Linking .clang-format"
  ln -s -f $THIS/clang-format $HOME/.clang-format

  log "Linking .clang-tidy"
  ln -s -f $THIS/clang-tidy $HOME/.clang-tidy
}

if ! is_sourced; then
  install
fi
