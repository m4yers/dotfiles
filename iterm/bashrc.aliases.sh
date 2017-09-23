#!/usr/bin/env bash

iterm_theme() {
  local IMAGEPATH=$(readlink -f "$@")

  # Generate iTerm colors and create theme.json
  $DOTFILES/iterm/scripts/iterm_generate_theme.py "$IMAGEPATH"

  # Patch theme.json with the image path
  local THEME="$HOME/Library/Application Support/iTerm2/DynamicProfiles/theme.json"
  local FIELD_NAME="Background Image Location"
  local PATTERN="s|$FIELD_NAME.*|$FIELD_NAME\": \"$IMAGEPATH\",|"
  sed -i "$PATTERN" "$THEME"

  # Change the running instance wallpaper
  $DOTFILES/iterm/scripts/iterm_set_image.applescript $IMAGEPATH
}
