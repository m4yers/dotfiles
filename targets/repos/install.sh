#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

install_linux() {
  true
}

install_mac() {
  # BREW
  if ! which -s brew; then
    /bin/bash -c "$(curl -fsSL \
      https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  else
    brew update
    brew upgrade
  fi

  eval "$(/opt/homebrew/bin/brew shellenv)"

  # NPM
  if ! brew ls --versions npm > /dev/null; then
    brew install npm
  fi
}

install() {
  if is_mac; then
    install_mac
  fi

  if is_linux; then
    install_linux
  fi
}

if ! is_sourced; then
  install
fi
