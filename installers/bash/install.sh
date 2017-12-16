#!/usr/bin/env bash

#brew: bash, bash-completion2
#npm: pygmentize
install() {
  bash_section "Bash"
  bash_export_source "$THIS/bashrc.config.sh"
  bash_export_source "$THIS/bashrc.aliases.sh"
  bash_export_source "$THIS/bashrc.functions.sh"
  bash_export_source "$THIS/bashrc.theme.sh"
  bash_export_source "/usr/local/share/bash-completion/bash_completion"
}
