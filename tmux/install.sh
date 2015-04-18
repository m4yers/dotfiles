if [[ ! -a ~/.tmux.conf ]]
then
    ln -s $here/tmux/tmux.conf ~/.tmux.conf
fi
