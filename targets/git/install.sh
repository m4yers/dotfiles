# depends-on: bash, brew
install() {
  brew install git
  brew install git-lfs

  local global_gitignore=$HOME/.gitconfig
  if [[ ! -f $global_gitignore ]]; then
    echo "${global_gitignore} does not exist. Creating..."
    touch $global_gitignore
  fi

  ln -s -f $THIS/gitconfig $HOME/.config/git/config
  ln -s -f $THIS/gitignore $HOME/.gitignore

  bash_section "Git"
  bash_export_source "$THIS/bashrc.aliases.sh"
}
