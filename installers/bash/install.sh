#!/usr/bin/env bash

# depends-on: brew, npm
install() {
  brew install bash
  brew install bash-completion2

  npm install -g pygmentize

  bash_section "Bash"
  bash_export_source "$THIS/bashrc.config.sh"
  bash_export_source "$THIS/bashrc.aliases.sh"
  bash_export_source "$THIS/bashrc.functions.sh"
  bash_export_source "$THIS/bashrc.theme.sh"

  bash_export_source "/usr/local/share/bash-completion/bash_completion"
}
