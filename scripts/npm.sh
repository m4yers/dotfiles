#!/usr/bin/env bash

npm_init() {
  if ! brew ls --versions npm > /dev/null; then
    brew install npm
  fi
}

npm_fini() {
  true
}

install_npm_requirements() {
  prefix="\#npm\:"
  grep -e $prefix $1 |
  while read -r line; do
    IFS=',' read -r -a list <<< "${line/$prefix}"
    for item in "${list[@]}"; do
      npm install -g $item
    done
  done
}
