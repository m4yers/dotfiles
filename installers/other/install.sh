#!/usr/bin/env bash

#brew: coreutils, grep, gnu-sed --with-default-names
#brew: swift, llvm, binutils, gdb, valgrind
#brew: ctags, cppcheck, doxygen
#brew: flex, bison
#brew: cmake, ninja, swig
#brew: openssh, gnutls, gnupg, gpg-agent
#brew: gts, graphviz --with-gts
#brew: python, node
#brew: tree, htop, highlight
#brew: unrar, curl, wget --with-iri
#brew: svn
#brew: imagemagick
#pip:  frida
#pip:  sphinx
#cask: icefloor
#cask: adobe-acrobat-reader
#cask: tunnelblick, libreoffice
#cask: google-chrome, evernote, vlc
#cask: flux, menubar-stats
install() {
  bash_section "Other"
  bash_export_path "$(brew --prefix llvm)/bin"
  bash_export_path "$(brew --prefix python)/libexec/bin"
  bash_export_path "$(brew --prefix coreutils)/libexec/gnubin"
  bash_export_source "$THIS/bashrc.aliases.sh"
  bash_export_source "$THIS/bashrc.config.sh"
}
