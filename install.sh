#!/usr/bin/env bash

export ROOT="$( cd "$( dirname "$0" )" && pwd )"

source $ROOT/scripts/shared.sh

check_system() {
  if ! is_mac; then
    echo "Mac only installer is available"
    exit 1
  fi
}

setup_system() {
  source $ROOT/scripts/macos.sh
}

setup_home() {
  source $ROOT/scripts/bash.sh
  bash_init

  if $OPTION_DEPS; then
    source $ROOT/scripts/brew.sh
    source $ROOT/scripts/pip.sh
    source $ROOT/scripts/npm.sh

    brew_init
    pip_init
    npm_init
  fi

  for installer in $(ls $ROOT/*/install.sh); do
    if $OPTION_DEPS; then
      install_brew_requirements $installer
      install_cask_requirements $installer
      install_pip_requirements $installer
      install_npm_requirements $installer
    fi

    # If this setup to be moved to other systems each installer must provide
    # setup_system specific setup_home routine
    source $installer
    install
  done

  if $OPTION_DEPS; then
    pip_fini
    brew_fini
    npm_fini
  fi
}

print_help() {
  echo "Home, Sweet Home installer"
  echo "Usage:"
  echo "  all  [--no-deps] Run all features"
  echo "  system           Run system setup"
  echo "  home [--no-deps] Run home directory setup"
  echo "  help             Print help"
}

OPTION_SYSTEM=false
OPTION_INSTALL=false
OPTION_DEPS=true

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
      --no-deps)
        OPTION_DEPS=false
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
