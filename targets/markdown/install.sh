#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." \
  &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

PACKAGES=(
  mdformat
  mdformat-tables
  'mdformat-frontmatter<1'
  mdformat-config
  mdformat-web
  mdformat-beautysh
  mdformat-black
)

install() {
  local this=$(get_source)

  echo "Installing mdformat and plugins..."
  pip3 install --user --quiet "${PACKAGES[@]}"

  bash_init_config
  bash_section "markdown formatting"
  bash_export_source "$this/bashrc.aliases.sh"
}

if ! is_sourced; then
  install
fi
