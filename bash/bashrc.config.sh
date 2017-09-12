#!/usr/bin/env bash

BIN="$HOME/bin:/usr/local/bin:/usr/local/sbin:/opt/local/bin"
LLVM="/usr/local/opt/llvm/bin"
export PATH=$BIN_HOME:$LLVM:$BIN:$OPT:$PATH

export EDITOR=vim

export LANG='en_US.UTF-8';
export LC_ALL='en_US.UTF-8';

# Increase Bash history size. Allow 32³ entries; the default is 500.
export HISTSIZE='32768';
export HISTFILESIZE="${HISTSIZE}";

# Omit duplicates and commands that begin with a space from history.
export HISTCONTROL='ignoreboth';
