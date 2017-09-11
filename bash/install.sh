#!/bin/bash

install() {
  echo "source $ROOT/scripts/shared.sh" >> $BASHRC
  echo "source $ROOT/bash/bashrc.config.sh" >> $BASHRC
  echo "source $ROOT/bash/bashrc.aliases.sh" >> $BASHRC
  echo "source $ROOT/bash/bashrc.theme.sh" >> $BASHRC
}
