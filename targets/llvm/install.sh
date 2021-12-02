#!/usr/bin/env bash

# depends-on: brew, bash
# satisfies: clang
install() {
  # Apache-2.0 + LLVM exceptions
  brew install llvm

  bash_init_config
  bash_export_path "$(brew --prefix llvm)/bin"
}
