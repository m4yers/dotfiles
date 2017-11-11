#!/usr/bin/env bash

# TODO add topology deps and make it a dependency
install_php() {
  brew tap homebrew/php
  brew install php72
}

#brew: git
install() {
  install_php

  local ARCANIST=$PROJECTS/arcanist
  if ! [[ -d $ARCANIST ]]; then
    echo "Cloning arcanist repos into $ARCANIST ..."
    mkdir $ARCANIST
    pushd $ARCANIST > /dev/null
    git clone https://github.com/phacility/libphutil.git
    git clone https://github.com/phacility/arcanist.git
    popd
    echo "Done."
  else
    echo "Using existing arcanist repos at $ARCANIST"
  fi

  echo >> $BASHRC
  echo "# Arcanist" >> $BASHRC
  echo "export PATH=\"$PROJECTS/arcanist/arcanist/bin:$PATH\"" >> $BASHRC
}
