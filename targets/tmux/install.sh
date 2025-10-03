#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

install_mac() {
  brew install tmux
}

install_ubuntu() {
  sudo apt install tmux
}

install_centos() {
  # TODO build from sources
  true
}

# depends-on: repos, git
install() {
  local this=$(get_source)

  if is_mac; then
    install_mac
  fi

  if is_ubuntu; then
    install_centos
  fi

  if is_centos; then
    install_centos
  fi

  log "Linking config"
  ln -s -f $this/tmux.conf $HOME/.tmux.conf

  if [[ ! -d $HOME/.tmux/plugins/tpm ]]; then
    log "Installing TPM"
    git clone https://github.com/tmux-plugins/tpm $HOME/.tmux/plugins/tpm
  else
    log "TPM is already installed"
  fi

  bash_init_config
  bash_section "Tmux configuration"
  bash_export_source "$this/bashrc.aliases.sh"
}

if ! is_sourced; then
  install
fi
