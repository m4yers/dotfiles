#!/usr/bin/env bash

ROOT="$( cd "$( dirname "$0" )/../.." && pwd )"
source $ROOT/scripts/shared.sh

install_mac() {
  brew install macvim
  brew install ag
}

install_linux() {
  sudo yum install vim
  # sudo yum install ag
}

# TODO ditch UltiSnips in favour of just loading files
# depends-on: repos, bash
install() {
  local this=$(get_source)
  if is_mac; then
    install_mac
  fi

  if is_linux; then
    install_linux
  fi

  # Linters
  log "Python linters"
  pip3 install pylint
  pip3 install bashate

  if [ which npm]; then
    log "JS linters"
    npm install -g jsonlint
    npm install -g eslint
  fi

  log "Linking .vimrc"
  ln -s -f $this/vimrc ~/.vimrc

  bash_init_config
  bash_section "Vim configuration"
  bash_export_source "$this/bashrc.aliases.sh"
}

if ! is_sourced; then
  install
fi
