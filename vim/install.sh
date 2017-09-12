#!/usr/bin/env bash

#brew: curl, ag
#brew: macvim --with-override-system-vim
#pip:  pylint, bashate
#npm:  jsonlint, eslint
install() {
  ln -s -f $ROOT/vim/vimrc ~/.vimrc
  ln -s -f $ROOT/vim/cvimrc ~/.cvimrc
  ln -s -f $ROOT/vim/vimrc ~/.ideavimrc

  if [ ! -f ~/.vim/autoload/plug.vim ]; then
    curl -fLo ~/.vim/autoload/plug.vim --create-dirs \
      https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
    vim +PlugInstall +qall
  fi
}
