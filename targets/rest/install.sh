#!/usr/bin/env bash

# depends-on: brew, bash
install() {
  bash_init_config

  # satisfies: grep
  # GPL3(!)
  brew install grep

  # satisfies: gnu-sed
  # GPL3(!)
  brew install gnu-sed
  bash_export_path "$(brew --prefix gnu-sed)/libexec/gnubin"

  # satisfies: ctags, cppcheck, doxygen
  # GPL2
  brew install ctags
  brew install cppcheck
  brew install doxygen

  # satisfies: flex, bison
  brew install flex
  brew install bison

  # satisfies: cmake, ninja, swig
  brew install cmake
  brew install ninja

  # satisfies: openssh, openssl, gnutls, gnupg, gpg-agent
  brew install openssh
  brew install openssl
  brew install gnutls
  brew install gnupg

  # satisfies: tree, htop, highlight
  brew install tree
  brew install htop
  brew install highlight

  # satisfies: unrar, wget
  brew install unrar
  brew install wget

  # satisfies: svn
  brew install svn

  # satisfies: imagemagick
  brew install imagemagick

  # satisfies: pandoc
  brew install pandoc

  # satisfies: sphinx
  pip3 install sphinx

  # satisfies: frida
  pip3 install frida

  # satisfies: graphviz, xdot
  brew install graphviz
  brew install xdot

  # satisfies: libxml2
  # brew install libxml2

  # satisfies: ccache
  brew install ccache

  bash_export_path "$(brew --prefix coreutils)/libexec/gnubin"
  bash_export_path "$(brwp --prefix ccache)/libexec"
  bash_export_source "$THIS/bashrc.aliases.sh"
  bash_export_source "$THIS/bashrc.config.sh"
}
