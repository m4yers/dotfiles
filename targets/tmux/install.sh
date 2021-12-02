#!/usr/bin/env bash

# depends-on: brew, git
install() {
  brew install tmux

  ln -s -f $THIS/tmux.conf ~/.tmux.conf

  if [[ ! -d ~/.tmux/plugins/tpm ]]; then
    git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
  fi

  # tmux source ~/.tmux.conf
}
