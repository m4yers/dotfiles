#!/usr/bin/env bash

# depends-on: bash, brew, pip
install() {
  # satisfies: coreutils, grep, gnu-sed
  brew install coreutils
  brew install grep
  brew install gnu-sed --with-default-names
  # satisfies: llvm, binutils, gdb, valgrind
  brew install llvm
  brew install binutils
  brew install gdb
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
  brew install swig
  # satisfies: openssh, openssl, gnutls, gnupg, gpg-agent
  brew install openssh
  brew install openssl
  brew install gnutls
  brew install gnupg
  brew install gpg-agent
  # satisfies: gts, graphviz
  brew install gts
  brew install graphviz --with-gts
  # satisfies: node
  brew install node
  # satisfies: tree, htop, highlight
  brew install tree
  brew install htop
  brew install highlight
  # satisfies: unrar, wget
  brew install unrar
  brew install wget --with-iri
  # satisfies: svn
  brew install svn
  # satisfies: imagemagick
  brew install imagemagick
  # satisfies: pandoc
  brew install pandoc

  # satisfies: xquartz
  brew cask install xquartz

  # satisfies: sphinx
  pip install sphinx
  # satisfies: frida
  pip install frida

  # satisfies: libxml2
  brew install libxml2
  brew link --force libxml2
  sudo ln -s /usr/local/include/libxml2/libxml /usr/local/include/libxml/

  bash_section "Other"
  bash_export_path "$(brew --prefix llvm)/bin"
  bash_export_path "$(brew --prefix python)/libexec/bin"
  bash_export_path "$(brew --prefix coreutils)/libexec/gnubin"
  bash_export_source "$THIS/bashrc.aliases.sh"
  bash_export_source "$THIS/bashrc.config.sh"
}
