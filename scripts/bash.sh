#!/usr/bin/env bash

export BASHRC="$HOME/.bashrc"
export BASHPROFILE="$HOME/.bash_profile"

bash_init() {
  cat $ROOT/installers/bash/bashrc > $BASHRC
  echo "export DOTFILES="$ROOT >> $BASHRC
  echo "source $BASHRC" > $BASHPROFILE
}
