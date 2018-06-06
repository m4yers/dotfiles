#!/usr/bin/env bash

# depends-on: git, wget
install_voltron() {
  VOLTRON=$PROJECTS/voltron
  if test -d $VOLTRON; then
    rm -rf $VOLTRON
  fi
  mkdir -p $VOLTRON
  pushd $VOLTRON

  # Voltron requires system python to be used with system lldb
  export PATH=/usr/bin:$PATH

  # Get pip for the system python
  wget https://bootstrap.pypa.io/get-pip.py
  sudo /usr/bin/python get-pip.py

  # Install voltron
  git clone https://github.com/snare/voltron
  pushd voltron
  sh install.sh
}

install() {
  install_voltron

  ln -s -f "$THIS/lldbinit" "$HOME/.lldbinit"

  bash_section "LLDB"
  bash_export_source "$THIS/bashrc.aliases.sh"
}
