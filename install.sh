#!/usr/bin/env bash

export ROOT="$( cd "$( dirname "$0" )" && pwd )"

source $ROOT/scripts/shared.sh
source $ROOT/scripts/bash.sh
source $ROOT/scripts/brew.sh
source $ROOT/scripts/pip.sh
source $ROOT/scripts/npm.sh

if ! is_mac; then
  echo "Mac only installer is available"
  exit 1
fi

install() {
  for installer in $(ls $ROOT/*/install.sh); do
    install_brew_requirements $installer
    install_cask_requirements $installer
    install_pip_requirements $installer
    install_npm_requirements $installer

    # If this setup to be moved to other systems each installer must provide
    # system specific install routine
    source $installer
    install
  done
}

main() {
  bash_init
  brew_init
  pip_init

  install

  pip_fini
  brew_fini
}

main
