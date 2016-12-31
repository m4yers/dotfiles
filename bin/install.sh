if [[ ! -a ~/bin ]]
then
    mkdir ~/bin
fi

ln -s -f $here/bin/gpgdisk ~/bin/gpgdisk
ln -s -f $here/bin/workspace ~/bin/workspace
ln -s -f $here/bin/run-skype ~/bin/run-skype
ln -s -f $here/bin/ts ~/bin/ts

