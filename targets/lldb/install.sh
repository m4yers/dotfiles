#!/usr/bin/env bash

# depends-on: git
install_voltron() {
  VOLTRON=$DEPENDENCIES/voltron
  if test -d $VOLTRON; then
    rm -rf $VOLTRON
  fi
  mkdir -p $VOLTRON
  pushd $VOLTRON

  # Voltron requires system python to be used with system lldb
  # System PIP is already provided by the main installer
  export PATH=/usr/bin:$PATH

  # Install voltron
  git clone https://github.com/snare/voltron
  pushd voltron
  sh install.sh
}

install() {
  # install_voltron

  ln -s -f "$THIS/lldbinit" "$HOME/.lldbinit"

  bash_init_config
  bash_export_source "$THIS/bashrc.aliases.sh"
}
