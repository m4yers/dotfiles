#!/usr/bin/env bash

# depends-on: bash, brew 
install() {
  # vim
  brew cask install macvim
  brew install macvim
  brew link --overwrite macvim

  # search
  brew install ag

  ln -s -f $THIS/vimrc ~/.vimrc

  bash_section "Vim"
  bash_export_source "$THIS/bashrc.aliases.sh"
  bash_export_path "$(brew --prefix macvim)/bin"
}
