#!/bin/bash

export here="$( cd "$( dirname "$0" )" && pwd )"

if [[ ! -a ~/bin ]]
then
    ln -s $here/bin ~/bin
fi

source $here/bash/install.sh
source $here/vim/install.sh
source $here/tmux/install.sh
