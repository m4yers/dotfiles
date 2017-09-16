#brew: w3m
install() {
  local DEST=~/.w3m

  if [[ ! -a $DEST ]]; then
    mkdir $DEST
  fi

  ln -s -f $ROOT/w3m/config $DEST/config
  ln -s -f $ROOT/w3m/keymap $DEST/keymap

  echo >> $BASHRC
  echo "# w3m" >> $BASHRC
  echo "source $ROOT/w3m/bashrc.aliases.sh" >> $BASHRC
}
