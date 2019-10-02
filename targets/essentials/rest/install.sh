#!/usr/bin/env bash

# depends-on: brew
install() {
  # satisfies: coreutils, grep, gnu-sed
  brew install coreutils
  brew install grep
  brew install gnu-sed
  
  bash_export_path "$(brew --prefix gnu-sed)/libexec/gnubin"

  # satisfies: openssh, openssl, gnutls, gnupg, gpg-agent
  brew install openssh
  brew install openssl
  brew install gnutls
  brew install gnupg

  # satisfies: tree, htop, unrar, wget
  brew install tree
  brew install htop
  brew install unrar
  brew install wget
}
