#brew: git, git-lfs
install() {
  local global_gitignore=$HOME/.gitconfig
  if [[ ! -f $global_gitignore ]]; then
    echo "${global_gitignore} does not exist. Creating..."
    touch $global_gitignore
  fi

  ln -s -f $THIS/gitconfig $HOME/.config/git/config
  ln -s -f $THIS/gitignore $HOME/.gitignore

  echo >> $BASHRC
  echo "# Git" >> $BASHRC
  echo "source $THIS/bashrc.aliases.sh" >> $BASHRC
}
