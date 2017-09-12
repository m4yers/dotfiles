#brew: git, git-lfs
install() {
  local DEST=~/.config/ranger

  if [[ ! -a $DEST ]]; then
    mkdir $DEST
  fi

  ln -s -f $ROOT/git/gitconfig $DEST/.gitconfig
  ln -s -f $ROOT/git/gitignore $DEST/.gitignore

  echo "source $ROOT/git/bashrc.config.sh" >> $BASHRC
}