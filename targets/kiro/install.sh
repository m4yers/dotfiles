#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/../.." &> /dev/null && pwd )
source $ROOT/scripts/shared.sh

install() {
  local this=$(get_source)

  log "Installing kiro-cli"
  brew install kiro-cli

  log "Installing uv (Python package manager)"
  curl -LsSf https://astral.sh/uv/install.sh | sh

  log "Creating ~/.kiro"
  mkdir -p ~/.kiro

  log "Linking skills (namespace: home)"
  kiro_link_namespace ~/.kiro/skills home "$this/skills"

  log "Linking steering (namespace: home)"
  kiro_link_namespace ~/.kiro/steering home "$this/steering"

  log "Linking agents (per-file symlinks)"
  kiro_link_files_flat ~/.kiro/agents "$this/agents"

  log "Linking settings (per-file symlinks)"
  kiro_link_files_flat ~/.kiro/settings "$this/settings"

  bash_init_config
  bash_section "Kiro configuration"
  bash_export_source "$this/bashrc.aliases.sh"
}

if ! is_sourced; then
  install
fi
