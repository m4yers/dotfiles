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
  source $ROOT/scripts/brew.sh
  source $ROOT/scripts/pip.sh
  source $ROOT/scripts/npm.sh

  bash_init
  brew_init
  pip_init

  for installer in $(ls $ROOT/*/install.sh); do
    install_brew_requirements $installer
    install_cask_requirements $installer
    install_pip_requirements $installer
    install_npm_requirements $installer

    # If this setup to be moved to other systems each installer must provide
    # setup_system specific setup_home routine
    source $installer
    install
  done

  pip_fini
  brew_fini
}

print_help() {
  echo "Home, Sweet Home installer"
  echo "Usage:"
  echo "  all         Run all features"
  echo "  system      Run system setup"
  echo "  home        Run home directory setup"
  echo "  help        Print help"
}

main() {
  check_system

  local option_system=false
  local option_install=false

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
        option_system=true
        option_install=true
        ;;
      system)
        option_system=true
        ;;
      home)
        option_install=true
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

  if $option_system; then
    setup_system
  fi

  if $option_install; then
    setup_home
  fi
}

main "$@"
