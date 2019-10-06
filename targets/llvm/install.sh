#!/usr/bin/env bash

# depends-on: bash, brew
# satisfies: clang
install() {
  brew install llvm@8

  bash_init_config
  bash_export_path "$(brew --prefix llvm@8)/bin"
}
