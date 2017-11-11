#brew: w3m
install() {
  local DEST=~/.w3m

  if [[ ! -a $DEST ]]; then
    mkdir $DEST
  fi

  ln -s -f $THIS/config $DEST/config
  ln -s -f $THIS/keymap $DEST/keymap

  echo >> $BASHRC
  echo "# w3m" >> $BASHRC
  echo "source $THIS/bashrc.aliases.sh" >> $BASHRC
}
