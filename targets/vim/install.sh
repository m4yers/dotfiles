#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

install_mac() {
  brew install macvim
  brew install ag
}

install_ubuntu() {
  sudo apt install vim
  sudo apt install silversearcher-ag
}

install_centos() {
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

  if is_ubuntu; then
    install_ubuntu
  fi

  if is_centos; then
    install_centos
  fi

  log "Downloading Plug"
  curl -fLo ~/.vim/autoload/plug.vim --create-dirs \
    https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim

  log "Python linters"
  pip3 install pylint --break-system-packages
  pip3 install flake8 --break-system-packages
  pip3 install bashate --break-system-packages

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
