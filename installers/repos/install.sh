#!/usr/bin/env bash

# satisfies: brew, python, pip, npm
install() {

  # BREW
  if ! which -s brew; then
    ruby -e "$(curl -fsSL \
      https://raw.githubusercontent.com/Homebrew/install/master/install)"
  else
    brew update
    brew upgrade
  fi

  # PIP
  if ! brew ls --versions python > /dev/null; then
    brew install python
  fi

  # NPM
  if ! brew ls --versions npm > /dev/null; then
    brew install npm
  fi
}
