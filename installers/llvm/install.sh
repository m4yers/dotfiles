#!/usr/bin/env bash

# depends-on: bash, brew
# satisfies: clang
install() {
  brew install llvm

  ln -s -f $THIS/scripts/llvm-dev-init.sh ~/bin/llvm_dev-init

  bash_section "LLVM"
  bash_export_path "$(brew --prefix llvm)/bin"
}
