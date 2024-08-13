#!/usr/bin/env bash

ROOT="$( cd "$( dirname "$0" )/../.." && pwd )"
source $ROOT/scripts/shared.sh

install_mac() {
  # GPL3(!)
  brew install bash

  log "Bash completion"
  brew install bash-completion2
  bash_section "Bash completion"
  bash_export_source "$(brew --prefix bash-completion2)/etc/profile.d/bash_completion.sh"
}

install_linux() {
  sudo yum install bash

  log "Bash completion"
  sudo yum install bash-completion
  bash_section "Bash completion"
  bash_export_source "/usr/share/bash-completion/bash_completion"
}

# depends-on: repos
install() {
  local this=$(get_source)

  # Global configuration
  bash_init_config

  bash_section "Shared configuration"
  bash_export_source "$ROOT/scripts/shared.sh"

  bash_section "Dotfiles configuration"
  bash_export_source "$this/bashrc.config.sh"
  bash_export_source "$this/bashrc.aliases.sh"
  bash_export_source "$this/bashrc.functions.sh"
  bash_export_source "$this/bashrc.theme.sh"

  if is_mac; then
    install_mac
  fi

  if is_linux; then
    install_linux
  fi

  # Git prompt
  log "Git prompt"
  if [ -d $HOME/.bash-git-prompt ]; then
    pushd $HOME/.bash-git-prompt >& /dev/null
    git pull
    assert_prev "Updating bash-git-prompt"
    popd >& /dev/null
  else
    git clone https://github.com/magicmonty/bash-git-prompt.git \
      $HOME/.bash-git-prompt --depth=1
    assert_prev "Cloning bash-git-prompt"
  fi

  bash_section "Git prompt"
  bash_export_global GIT_PROMPT_ONLY_IN_REPO 1
  bash_export_source $HOME/.bash-git-prompt/gitprompt.sh

  bash_section "Source local bashrc if exists"
  bash_export_source_maybe $HOME/.bashrc.local
}

if ! is_sourced; then
  install
fi
