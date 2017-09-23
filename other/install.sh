#!/usr/bin/env bash

#brew: coreutils, grep, gnu-sed --with-default-names
#brew: bash, bash-completion2
#brew: llvm, binutils, gdb, valgrind
#brew: ctags, cppcheck, doxygen
#brew: flex, bison
#brew: cmake, ninja
#brew: openssh, gnutls, gnupg, gpg-agent
#brew: gts, graphviz --with-gts
#brew: python, node
#brew: tree, htop, highlight
#brew: unrar, curl, wget --with-iri
#brew: imagemagick
#pip:  sphinx
#cask: icefloor
#cask: adobe-acrobat-reader
#cask: tunnelblick, libreoffice
#cask: google-chrome, evernote, vlc
install() {
  echo >> $BASHRC
  echo "# Other" >> $BASHRC
  echo "source $ROOT/other/bashrc.aliases.sh" >> $BASHRC
  echo "source $ROOT/other/bashrc.config.sh" >> $BASHRC
  echo "export PATH=\"$(brew --prefix llvm)/bin:\$PATH\"" >> $BASHRC
  echo "export PATH=\"$(brew --prefix python)/libexec/bin:\$PATH\"" >> $BASHRC
  echo "export PATH=\"$(brew --prefix coreutils)/libexec/gnubin:\$PATH\"" >> $BASHRC
}
