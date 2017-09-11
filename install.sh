#!/bin/bash

export ROOT="$( cd "$( dirname "$0" )" && pwd )"

source $ROOT/scripts/shared.sh
source $ROOT/scripts/brew.sh

if ! is_mac; then
  echo "Mac only installer is available"
  exit 1
fi

install() {
  for installer in $(ls $ROOT/*/install.sh); do
    install_brew_requirements $installer
    install_cask_requirements $installer
    source $installer
  done
}

main() {
  brew_init
  install
  brew_fini
}

main
