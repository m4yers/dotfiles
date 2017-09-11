#!/bin/bash

BIN="$HOME/bin:/usr/local/bin:/usr/local/sbin:/opt/local/bin"
LLVM="/usr/local/opt/llvm/bin"
export PATH=$BIN_HOME:$LLVM:$BIN:$OPT:$PATH

export EDITOR=vim

[ -z "$PS1" ] && return

if is_mac; then
  if command -v brew > /dev/null; then
    completion="$(brew --prefix)/etc/bash_completion"
    if [[ -f $completion ]]
    then
      source $completion
    fi
  fi
fi
