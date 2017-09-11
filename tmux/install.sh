#!/bin/bash

#brew: git, tmux, reattach-to-user-namespace
install() {
  ln -s -f $ROOT/tmux/tmux.conf ~/.tmux.conf
  if [[ ! -d ~/.tmux/plugins/tpm ]]; then
    git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
  fi
  tmux source ~/.tmux.conf
}
