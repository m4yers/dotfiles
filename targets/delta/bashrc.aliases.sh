#!/usr/bin/env bash

alias dot-delta="cd $HOME/dotfiles/targets/delta"
alias dot-delta-install="vim $HOME/dotfiles/targets/delta/install.sh"
alias dot-delta-config="vim $HOME/dotfiles/targets/delta/gitconfig"
alias dot-delta-aliases="vim $HOME/dotfiles/targets/delta/bashrc.aliases.sh"

# Review a commit as one continuous side-by-side diff; -W expands each
# hunk to its enclosing function. Default: HEAD.
alias grv="git show -W --stat -p"

# Same, but changes only (no context).
alias grv0="git show -U0 --stat -p"

# Same, whole file around every change.
alias grvf="git show -U99999 --stat -p"
