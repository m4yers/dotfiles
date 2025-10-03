#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

install_mac() {
  brew install python3
}

install_ubuntu() {
  sudo apt install python3
  sudo apt install python3-pip
}

install_centos() {
  sudo yum install python3
}

# depends-on: repos, bash
install() {
  brew install python

  if is_mac; then
    install_mac
  fi

  if is_ubuntu; then
    install_ubuntu
  fi

  if is_centos; then
    install_centos
  fi

  pip3 install pipenv --break-system-packages
  pip3 install tox --break-system-packages

  bash_init_config
  bash_section "Python configuration"
  bash_export_path "$(python3 -m site --user-base)/bin"
}

if ! is_sourced; then
  install
fi
