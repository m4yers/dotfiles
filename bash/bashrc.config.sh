#!/usr/bin/env bash

# Set up $PATH
BIN="$HOME/bin:/usr/local/bin:/usr/local/sbin:/opt/local/bin"
LLVM="/usr/local/opt/llvm/bin"
export PATH=$BIN_HOME:$LLVM:$BIN:$OPT:$PATH

# The usual
export EDITOR=vim
export PAGER=less

# Locale
export LANG='en_US.UTF-8';
export LC_ALL='en_US.UTF-8';

# Add colors to less
export LESSOPEN="| pygmentize -f terminal -O style=native -g %s"
export LESS='-R'

# Less Colors for Man Pages
export LESS_TERMCAP_mb=$'\e[01;31m'       # begin blinking
export LESS_TERMCAP_md=$'\e[01;38;5;74m'  # begin bold
export LESS_TERMCAP_me=$'\e[0m'           # end mode
export LESS_TERMCAP_se=$'\e[0m'           # end standout-mode
export LESS_TERMCAP_so=$'\e[38;5;246m'    # begin standout-mode - info box
export LESS_TERMCAP_ue=$'\e[0m'           # end underline
export LESS_TERMCAP_us=$'\e[04;38;5;146m' # begin underline]]]

# Increase Bash history size. Allow 32³ entries; the default is 500.
export HISTSIZE='32768';
export HISTFILESIZE="${HISTSIZE}";

# Omit duplicates and commands that begin with a space from history.
export HISTCONTROL='ignoreboth';
