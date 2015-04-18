if [[ ! -a ~/.vimrc ]]
then
    ln -s $here/vim/vimrc ~/.vimrc
    ln -s $here/vim/vimrc ~/.ideavimrc
fi

