#brew: git, git-lfs
install() {
  local DEST=~/.config/git

  if [[ ! -a $DEST ]]; then
    mkdir $DEST
  fi

  ln -s -f $THIS/gitconfig $DEST/.gitconfig
  ln -s -f $THIS/gitignore $DEST/.gitignore

  echo >> $BASHRC
  echo "# Git" >> $BASHRC
  echo "source $THIS/bashrc.aliases.sh" >> $BASHRC
}
