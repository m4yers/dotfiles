#!/usr/bin/env bash

# Exit on any error
set -e

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

source $ROOT/scripts/shared.sh

check_system() {
  if ! is_mac && ! is_linux; then
    error "Only Mac and Linux installers are available"
    exit 1
  fi
}

bash_init() {
  # TODO backup the existing bashrc
  # FIXME: too hacky
  local targets=$ROOT/targets
  cat $targets/bash/bashrc > $BASHRC
  echo "source $BASHRC" > $BASHPROFILE
  rm -rf $TARGET_CONFIGS
  mkdir -p $TARGET_CONFIGS
}

bootstrap () {
  bash_init
}

setup_system() {
  log "Skipping system"
  # source $ROOT/scripts/macos.sh
}

setup_home() {
  log "SETUP HOME"

  bootstrap

  if is_linux; then
    declare -a targets=("repos" "bash" "git" "tmux" "vim" "ranger" "scripts")
  fi

  if is_mac; then
    declare -a targets=("repos" "bash" "git" "tmux" "vim" "ranger" "iterm" "scripts")
  fi

  log "TARGETS: ${targets[*]}"
  for target in ${targets[*]}; do
    log "INSTALLING $target..."
    $ROOT/targets/$target/install.sh
    log "DONE $target"
  done
}

print_help() {
  echo "Sweet Home Installer"
  echo "Usage:"
  echo "... all    Run all features"
  echo "... system Run system setup"
  echo "... home   Run home directory setup"
  echo "... help   Print help"
}

export OPTION_SYSTEM=false
export OPTION_INSTALL=false

main() {
  check_system

  if [[ $# -eq 0 ]]; then
    print_help
    exit 1
  fi

  while [[ $# -ne 0 ]]
  do
    option="$1"
    shift

    case $option in
      all)
        OPTION_SYSTEM=true
        OPTION_INSTALL=true
        ;;
      system)
        OPTION_SYSTEM=true
        ;;
      home)
        OPTION_INSTALL=true
        ;;
      help)
        print_help
        exit 0
        ;;
      *)
        print_help
        exit 1
        ;;
    esac
  done

  if ! yesno "Do you really want this?" "no"; then
    exit 0
  fi

  if $OPTION_SYSTEM; then
    setup_system
  fi

  if $OPTION_INSTALL; then
    setup_home
  fi
}

main "$@"
