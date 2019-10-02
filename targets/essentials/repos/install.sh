#!/usr/bin/env bash

# satisfies: brew
install() {
  # BREW
  if ! which -s brew; then
    ruby -e "$(curl -fsSL \
      https://raw.githubusercontent.com/Homebrew/install/master/install)"
  else
    brew update
    brew upgrade
  fi
}
