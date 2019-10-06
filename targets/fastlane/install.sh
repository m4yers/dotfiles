#!/usr/bin/env bash

# depends-on: bash, brew
install() {
  brew cask install fastlane

  bash_init_config
  bash_export_path "$HOME/.fastlane/bin"
}
