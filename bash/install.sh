if [[ ! -a ~/.bashrc ]]
then
    ln -s $here/bash/bash_profile ~/.bash_profile
    ln -s $here/bash/bashrc ~/.bashrc
fi
