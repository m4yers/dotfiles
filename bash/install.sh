#!/bin/bash

install() {
  ln -s -f $ROOT/bash/bash_profile ~/.bash_profile
  ln -s -f $ROOT/bash/bashrc ~/.bashrc
}

install
