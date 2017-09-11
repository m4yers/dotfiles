#!/usr/bin/env bash

install() {
  if [[ ! -a ~/bin ]]
  then
    mkdir ~/bin
  fi

  ln -s -f $ROOT/bin/gpgdisk ~/bin/gpgdisk
  ln -s -f $ROOT/bin/workspace ~/bin/workspace
  ln -s -f $ROOT/bin/run-skype ~/bin/run-skype
  ln -s -f $ROOT/bin/ts ~/bin/ts
}
