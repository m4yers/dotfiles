#!/usr/bin/env bash

# depends-on: brew
install() {
  brew install bash
  brew install bash-completion2
  brew install bash-git-prompt

  bash_section "Bash"

  # global configuration
  bash_export_source "$THIS/bashrc.config.sh"
  bash_export_source "$THIS/bashrc.aliases.sh"
  bash_export_source "$THIS/bashrc.functions.sh"
  bash_export_source "$THIS/bashrc.theme.sh"
  bash_export_source "/usr/local/share/bash-completion/bash_completion"

  bash_export_global GIT_PROMPT_ONLY_IN_REPO 1
  bash_export_global __GIT_PROMPT_DIR "$(brew --prefix bash-git-prompt)/share"
  bash_export_source "$(brew --prefix bash-git-prompt)/share/gitprompt.sh"

  # local configuration
  local lbashrc=$HOME/.bashrc.local
  touch $lbashrc
  bash_export_source $lbashrc
}
