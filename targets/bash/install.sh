#!/usr/bin/env bash

# depends-on: brew
install() {
  # GPL3(!)
  brew install bash
  brew install bash-completion2
  brew install bash-git-prompt

  # Implicitly initialised
  # bash_init_config

  # global configuration
  bash_init_config

  bash_export_source "$THIS/bashrc.config.sh"
  bash_export_source "$THIS/bashrc.aliases.sh"
  bash_export_source "$THIS/bashrc.functions.sh"
  bash_export_source "$THIS/bashrc.theme.sh"

  # TODO This should be in 'repositories' but it would create a cycle
  bash_init_config
  bash_export 'eval "$(/opt/homebrew/bin/brew shellenv)"'
  bash_export_path "/opt/homebrew/bin"

  # bash_export_global BASH_COMPLETION_COMPAT_DIR "$(brew --prefix bash-completion2)/etc/bash_completion.d"
  bash_export_source "$(brew --prefix bash-completion2)/etc/profile.d/bash_completion.sh"

  bash_export_global GIT_PROMPT_ONLY_IN_REPO 1
  bash_export_global __GIT_PROMPT_DIR "$(brew --prefix bash-git-prompt)/share"
  bash_export_source "$(brew --prefix bash-git-prompt)/share/gitprompt.sh"

  # local configuration
  local lbashrc=$HOME/.bashrc.local
  touch $lbashrc
  bash_export_source $lbashrc
}
