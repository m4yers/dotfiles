#!/usr/bin/env bash

# depends-on: brew
install() {
  # satisfies: icefloor
  brew cask install icefloor
  # satisfies: adobe-acrobat-reader
  brew cask install adobe-acrobat-reader
  # satisfies: tunnelblick, libreoffice
  brew cask install tunnelblick
  brew cask install libreoffice
  # satisfies: google-chrome, evernote, dropbox, vlc
  brew cask install google-chrome
  brew cask install evernote
  brew cask install dropbox
  brew cask install vlc
  # satisfies: flux, menubar-stats
  brew cask install flux
  brew cask install menubar-stats
}
