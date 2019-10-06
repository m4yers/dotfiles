#!/usr/bin/env bash

# depends-on: bash, git, php
install() {
  local ARCANIST=$DEPENDENCIES/arcanist
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

  bash_init_config
  bash_export_path "$DEPENDENCIES/arcanist/arcanist/bin"
  bash_export_source "$THIS/bashrc.aliases.sh"
}
