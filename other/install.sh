#!/usr/bin/env bash

#brew: coreutils, grep, gnu-sed --with-default-names
#brew: bash, bash-completion2
#brew: llvm, binutils, gdb, valgrind
#brew: ctags, cppcheck, doxygen
#brew: flex, bison
#brew: cmake, ninja
#brew: git, git-lfs
#brew: openssh, gnutls, gnupg, gpg-agent
#brew: gts, graphviz --with-gts
#brew: python, node
#brew: tree, htop, highlight
#brew: unrar, curl, wget --with-iri
#pip:  sphinx
#cask: iterm2, tunnelblick
#cask: google-chrome, evernote, vlc
install() {
  echo "source $ROOT/other/bashrc.config.sh" >> $BASHRC
}
