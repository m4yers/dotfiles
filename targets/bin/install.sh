#!/usr/bin/env bash

install() {
  if [[ ! -a ~/bin ]]
  then
    mkdir ~/bin
  fi

  ln -s -f $THIS/gpgdisk ~/bin/gpgdisk
  ln -s -f $THIS/workspace ~/bin/workspace
  ln -s -f $THIS/run-skype ~/bin/run-skype
  ln -s -f $THIS/ts ~/bin/ts
}
