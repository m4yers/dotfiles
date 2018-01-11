#!/usr/bin/env bash

# depends-on: bash, brew
install() {
  brew install llvm

  ln -s -f $THIS/scripts/llvm-dev-init.sh ~/bin/llvm_dev-init

  bash_section "LLVM"
  bash_export_path "$(brew --prefix llvm)/bin"
}
