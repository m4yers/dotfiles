#!/bin/bash

brew_init() {
  which -s brew
  if [[ $? != 0 ]] ; then
    ruby -e "$(curl -fsSL \
      https://raw.githubusercontent.com/Homebrew/install/master/install)"
  else
    brew update
    brew upgrade
  fi
}

brew_fini() {
  brew cleanup
  brew linkapps
}

is_installed() {
  brew ls --versions > /dev/null
}

install_brew_requirements() {
  prefix="\#brew\:"
  grep -e $prefix $1 |
  while read -r line; do
    IFS=',' read -r -a list <<< "${line/$prefix}"
    for item in "${list[@]}"; do
      if ! is_installed $item; then
        brew install $item
      fi
    done
  done
}

install_cask_requirements() {
  prefix="\#cask\:"
  grep -e $prefix $1 |
  while read -r line; do
    IFS=',' read -r -a list <<< "${line/$prefix}"
    for item in "${list[@]}"; do
      if ! is_installed $item; then
        brew cask install $item
      fi
    done
  done
}
