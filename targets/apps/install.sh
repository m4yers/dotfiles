#!/usr/bin/env bash

# depends-on: brew
install() {
  # satisfies: adobe-acrobat-reader
  brew install adobe-acrobat-reader

  # satisfies: tunnelblick, flux, spectacle
  brew install tunnelblick
  brew install spectacle

  # satisfies: google-chrome, evernote, dropbox, vlc
  brew install google-chrome
  brew install vlc

  # satisfies: slack, dash
  brew install slack
  brew install dash
}
