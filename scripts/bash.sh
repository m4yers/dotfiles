#!/usr/bin/env bash

export BASHRC="$HOME/.bashrc"
export BASHPROFILE="$HOME/.bash_profile"

bash_init() {
  echo "#!/bin/bash" > $BASHRC
  echo "source $BASHRC" > $BASHPROFILE
}
