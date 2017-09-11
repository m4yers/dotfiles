#!/bin/bash

if command -v brew > /dev/null; then
  completion="$(brew --prefix)/etc/bash_completion"
  if [[ -f $completion ]]
  then
    source $completion
  fi
fi
