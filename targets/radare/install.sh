#!/usr/bin/env bash

# depends-on: brew
install() {
  brew install radare2

  ln -s -f "$THIS/radare2rc" "$HOME/.radare2rc"

  bash_init_config
  bash_export_source "$THIS/bashrc.aliases.sh"
}
