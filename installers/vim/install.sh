#!/usr/bin/env bash

#brew: svn, curl, ag, swiftlint
#cask: macvim --with-override-system-vim
#pip:  pylint, bashate
#npm:  jsonlint, eslint
install() {
  ln -s -f $THIS/vimrc ~/.vimrc
  ln -s -f $THIS/cvimrc ~/.cvimrc
  ln -s -f $THIS/vimrc ~/.ideavimrc
  ln -s -f $THIS/ycm.py ~/.ycm.py

  svn co http://llvm.org/svn/llvm-project/llvm/trunk/utils/vim $DEPENDENCIES/llvm.vim

  if [ ! -f ~/.vim/autoload/plug.vim ]; then
    curl -fLo ~/.vim/autoload/plug.vim --create-dirs \
      https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
    vim +PlugInstall +qall
  fi

  bash_section "Vim"
  bash_export_source "$THIS/bashrc.aliases.sh"
}
