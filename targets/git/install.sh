#!/usr/bin/env bash

ROOT="$( cd "$( dirname "$0" )/../.." && pwd )"
source $ROOT/scripts/shared.sh

install_mac() {
  brew install git
  brew install git-lfs
}

install_linux() {
  sudo yum install git
  sudo yum install git-lfs
  sudo yum install git-clang-format
}

# depends-on: repos, bash
install() {
  local this=$(get_source)

  if is_mac; then
    install_mac
  fi

  if is_linux; then
    install_linux
  fi

  if [ -f $HOME/.gitconfig ]; then
    log ".gitconfig exists, using git-config"
    git config --global apply.whitespace fix
    git config --global core.autocrlf input
    git config --global core.safecrlf true
    git config --global color.ui auto
    git config --global diff.tool vimdiff
    git config --global merge.tool vimdiff
    git config --global merge.conflictstyle diff3
    git config --global mergetool.keepBackup false
    git config --global alias.co 'checkout'
    git config --global alias.st 'status'
    git config --global alias.br 'branch'
  else
    log ".gitconfig does not exist, linking from dotfiles"
    ln -s -f $this/gitconfig $HOME/.gitconfig
  fi

  if [ -f $HOME/.gitignore ]; then
    log ".gitignore exists, skipping linking"
  else
    log "Linking .gitignore"
    ln -s -f $this/gitignore $HOME/.gitignore
  fi

  bash_init_config
  bash_section "Git configuration"
  bash_export_source "$this/bashrc.aliases.sh"
}

if ! is_sourced; then
  install
fi
