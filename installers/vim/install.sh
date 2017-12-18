#!/usr/bin/env bash

# depends-on: bash, brew, npm, svn
install() {
  brew cask install macvim
  brew install macvim --with-override-system-vim
  brew link --overwrite macvim
  brew install ag
  brew install swiftlint
  pip install pylint
  pip install bashate
  npm install -g jsonlint
  npm install -g eslint

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
