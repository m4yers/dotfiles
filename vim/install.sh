#!/usr/bin/env bash

#brew: curl, ag, swiftlint
#cask: macvim --with-override-system-vim
#pip:  pylint, bashate
#npm:  jsonlint, eslint
install() {
  ln -s -f $ROOT/vim/vimrc ~/.vimrc
  ln -s -f $ROOT/vim/cvimrc ~/.cvimrc
  ln -s -f $ROOT/vim/vimrc ~/.ideavimrc
  ln -s -f $ROOT/vim/ycm.py ~/.ycm.py

  if [ ! -f ~/.vim/autoload/plug.vim ]; then
    curl -fLo ~/.vim/autoload/plug.vim --create-dirs \
      https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
    vim +PlugInstall +qall
  fi

  echo >> $BASHRC
  echo "# Vim" >> $BASHRC
  echo "source $ROOT/vim/bashrc.aliases.sh" >> $BASHRC
}
