#!/usr/bin/env bash

# depends-on: bash, brew, pip
install() {
  # satisfies: coreutils, grep
  brew install coreutils
  brew install grep

  # satisfies: gnu-sed
  brew install gnu-sed
  bash_export_path "$(brew --prefix gnu-sed)/libexec/gnubin"

  # satisfies: binutils, valgrind
  brew install binutils
  brew install valgrind

  # satisfies: ctags, cppcheck, doxygen
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
  pip install sphinx

  # satisfies: frida
  pip install frida

  # satisfies: graphviz, xdot
  brew install graphviz
  brew install xdot

  # satisfies: libxml2
  # brew install libxml2
  # brew link --force libxml2
  # sudo ln -s /usr/local/include/libxml2/libxml /usr/local/include/libxml/

  # satisfies: ccache
  brew install ccache

  bash_section "Rest"
  bash_export_path "$(brew --prefix coreutils)/libexec/gnubin"
  bash_export_path "$(brwp --prefix ccache)/libexec"
  bash_export_source "$THIS/bashrc.aliases.sh"
  bash_export_source "$THIS/bashrc.config.sh"
}
