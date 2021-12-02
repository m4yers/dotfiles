#!/usr/bin/env bash

# satisfies: brew, npm
install() {
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
