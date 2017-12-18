# depends-on: bash, brew
install() {
  brew install w3m

  local DEST=~/.w3m

  if [[ ! -a $DEST ]]; then
    mkdir $DEST
  fi

  ln -s -f $THIS/config $DEST/config
  ln -s -f $THIS/keymap $DEST/keymap

  bash_section "w3m"
  bash_export_source "$THIS/bashrc.aliases.sh"
}
