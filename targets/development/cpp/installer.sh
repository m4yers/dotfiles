#!/usr/bin/env bash

# depends-on: clang
install() {
  ln -s -f $THIS/clang-format $HOME/.clang-format
  ln -s -f $THIS/clang-tidy $HOME/.clang-tidy
}
