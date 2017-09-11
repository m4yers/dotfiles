#!/usr/bin/env bash

pip_init() {
  true
}

pip_fini() {
  true
}

is_installed() {
  pip2 show $1 > /dev/null
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
