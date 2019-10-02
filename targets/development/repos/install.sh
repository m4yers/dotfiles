#!/usr/bin/env bash

# satisfies: brew, npm
install() {
  # BREW
  if ! which -s brew; then
    ruby -e "$(curl -fsSL \
      https://raw.githubusercontent.com/Homebrew/install/master/install)"
  else
    brew update
    brew upgrade
  fi

  # NPM
  if ! brew ls --versions npm > /dev/null; then
    brew install npm
  fi
}
