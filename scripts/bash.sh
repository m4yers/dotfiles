#!/usr/bin/env bash

export BASHRC="$HOME/.bashrc"
export BASHPROFILE="$HOME/.bash_profile"

bash_init() {
  cat $ROOT/bash/bashrc > $BASHRC
  echo "export DOTFILES="$ROOT >> $BASHRC
  echo "source $BASHRC" > $BASHPROFILE
}
