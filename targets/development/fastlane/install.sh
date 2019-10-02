#!/usr/bin/env bash

# depends-on: bash, brew
install() {
  brew cask install fastlane

  bash_section "Fastlane"
  bash_export_path "$HOME/.fastlane/bin"
}
