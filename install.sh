#!/bin/bash

export here="$( cd "$( dirname "$0" )" && pwd )"

for install in $(ls $here/*/install.sh) ; do
    source $install
done

# Vim
# install everything only it is a fresh install
vundle=~/.vim/bundle/Vundle.vim
if [ ! -f $vundle ]; then
    git clone https://github.com/VundleVim/Vundle.vim.git $vundle
    vim +PluginInstall +qall
fi
