#!/usr/bin/env bash

install() {
  if [[ ! -a ~/bin ]]
  then
    mkdir ~/bin
  fi

  local HERE=$ROOT/bin
  ln -s -f $HERE/gpgdisk ~/bin/gpgdisk
  ln -s -f $HERE/workspace ~/bin/workspace
  ln -s -f $HERE/run-skype ~/bin/run-skype
  ln -s -f $HERE/ts ~/bin/ts
}
