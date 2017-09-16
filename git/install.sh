#brew: git, git-lfs
install() {
  local DEST=~/.config/git

  if [[ ! -a $DEST ]]; then
    mkdir $DEST
  fi

  ln -s -f $ROOT/git/gitconfig $DEST/.gitconfig
  ln -s -f $ROOT/git/gitignore $DEST/.gitignore

  echo >> $BASHRC
  echo "# Git" >> $BASHRC
  echo "source $ROOT/git/bashrc.config.sh" >> $BASHRC
}
