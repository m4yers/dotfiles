#!/usr/bin/env bash

# Set up $PATH
export PATH="$HOME/bin:/usr/local/bin:/usr/local/sbin:/opt/local/bin:/usr/bin:/usr/sbin:/bin:/sbin:"

# The usual
export EDITOR=vim
export PAGER=less

# Locale
export LANG='en_US.UTF-8';
export LC_ALL='en_US.UTF-8';

# Add colors to less
export LESSOPEN="| pygmentize -f terminal -O style=native -g %s"
export LESS='-R'

# Increase Bash history size. Allow 32³ entries; the default is 500.
export HISTSIZE='32768';
export HISTFILESIZE="${HISTSIZE}";

# Omit duplicates and commands that begin with a space from history.
export HISTCONTROL='ignoreboth';
