#!/usr/bin/env bash

ROOT="$( cd "$( dirname "$0" )/../.." && pwd )"
source $ROOT/scripts/shared.sh

install_mac() {
  brew install python3
}

install_linux() {
  sudo yum install python3
}

# depends-on: repos, bash
install() {
  brew install python

  if is_mac; then
    install_mac
  fi

  if is_linux; then
    install_linux
  fi

  pip3 install --user pipenv
  pip3 install --user tox

  bash_init_config
  bash_section "Python configuration"
  bash_export_path "$(python3 -m site --user-base)/bin"
}

if ! is_sourced; then
  install
fi
