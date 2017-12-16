#!/usr/bin/env bash

export BASHRC="$HOME/.bashrc"
export BASHPROFILE="$HOME/.bash_profile"

bash_init() {
  cat $ROOT/installers/bash/bashrc > $BASHRC
  echo "source $BASHRC" > $BASHPROFILE
}

bash_section() {
  echo >> $BASHRC
  echo "# $1" >> $BASHRC
}

bash_export_path() {
  echo "export PATH=\"$1:\$PATH\"" >> $BASHRC
}

bash_export_source() {
  echo "source $1" >> $BASHRC
}

bash_export_global() {
  echo "export $1="$2 >> $BASHRC
}
