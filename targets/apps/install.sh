#!/usr/bin/env bash

# depends-on: brew
install() {
  # satisfies: icefloor
  brew cask install icefloor

  # satisfies: adobe-acrobat-reader
  brew cask install adobe-acrobat-reader

  # satisfies: tunnelblick, flux, spectacle
  brew cask install tunnelblick
  brew cask install flux
  brew cask install spectacle

  # satisfies: google-chrome, evernote, dropbox, vlc
  brew cask install google-chrome
  brew cask install evernote
  brew cask install spotify
  brew cask install dropbox
  brew cask install vlc

  # satisfies: slack, dash
  brew cask install slack
  brew cask install dash
}
