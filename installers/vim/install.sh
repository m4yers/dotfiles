#!/usr/bin/env bash

#brew: curl, ag, swiftlint
#cask: macvim --with-override-system-vim
#pip:  pylint, bashate
#npm:  jsonlint, eslint
install() {
  ln -s -f $THIS/vimrc ~/.vimrc
  ln -s -f $THIS/cvimrc ~/.cvimrc
  ln -s -f $THIS/vimrc ~/.ideavimrc
  ln -s -f $THIS/ycm.py ~/.ycm.py

  if [ ! -f ~/.vim/autoload/plug.vim ]; then
    curl -fLo ~/.vim/autoload/plug.vim --create-dirs \
      https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
    vim +PlugInstall +qall
  fi

  echo >> $BASHRC
  echo "# Vim" >> $BASHRC
  echo "source $THIS/bashrc.aliases.sh" >> $BASHRC
}
