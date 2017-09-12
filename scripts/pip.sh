#!/usr/bin/env bash

pip_init() {
  if ! brew ls --versions python > /dev/null; then
    brew install python
  fi
}

pip_fini() {
  true
}

install_pip_requirements() {
  prefix="\#pip\:"
  grep -e $prefix $1 |
  while read -r line; do
    IFS=',' read -r -a list <<< "${line/$prefix}"
    for item in "${list[@]}"; do
      if ! pip2 show $item > /dev/null; then
        pip2 install $item
      fi
    done
  done
}
