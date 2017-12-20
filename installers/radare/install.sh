#!/usr/bin/env bash

# depends-on: brew
install() {
  brew install radare2

  ln -s -f "$THIS/radare2rc" "$HOME/.radare2rc"
}
