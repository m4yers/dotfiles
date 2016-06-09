dest=~/.config/ranger

if [[ ! -a $dest ]]
then
    mkdir $dest
fi

ln -s -f $here/ranger/commands.py $dest/commands.py
ln -s -f $here/ranger/rc.conf     $dest/rc.conf
ln -s -f $here/ranger/rifle.conf  $dest/rifle.conf
ln -s -f $here/ranger/scope.sh    $dest/scope.sh
