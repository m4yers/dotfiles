#!/usr/bin/env bash

# depends-on: brew, npm, bash
install() {
  # Vim
  brew install macvim

  # Search
  brew install ag

  # Linters
  # brew install swiftlint
  pip3 install pylint
  pip3 install bashate
  npm install -g jsonlint
  npm install -g eslint

  # Vimdeck dependencies
  # brew install imagemagick@6
  # PKG_CONFIG_PATH=$(brew --prefix imagemagick@6)/lib/pkgconfig gem install vimdeck

  # LLVM code coloring
  # TODO read the file from github
  # svn co http://llvm.org/svn/llvm-project/llvm/trunk/utils/vim $DEPENDENCIES/llvm.vim

  ln -s -f $THIS/vimrc ~/.vimrc
  ln -s -f $THIS/cvimrc ~/.cvimrc
  ln -s -f $THIS/ycm.py ~/.ycm.py

  bash_init_config
  bash_export_source "$THIS/bashrc.aliases.sh"
}
