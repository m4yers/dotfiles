#!/usr/bin/env bash

export ROOT="$( cd "$( dirname "$0" )" && pwd )"
export PROJECTS=$(dirname $ROOT)
export SCRIPTS="$ROOT/scripts"
export INSTALLERS="$ROOT/installers"
export DEPENDENCIES="$ROOT/dependencies"

source $ROOT/scripts/shared.sh

check_system() {
  if ! is_mac; then
    echo "Mac only installer is available"
    exit 1
  fi
}

setup_system() {
  echo "Skipping system"
  # source $ROOT/scripts/macos.sh
}

setup_home() {
  source $ROOT/scripts/bash.sh
  bash_init
  bash_export_global PROJECTS $PROJECTS
  bash_export_global DOTFILES $ROOT

  pip install -r $ROOT/requirements.txt
  result=
  if [[ -z $OPTION_ONLY ]]; then
    result=$(python $SCRIPTS/topology.py $INSTALLERS)
  else
    result=$(python $SCRIPTS/topology.py $INSTALLERS --for $OPTION_ONLY)
  fi
  echo "DEPENDENCIES:"
  echo $result
  exit 0
  if [[ $? != 0 ]]; then
    echo $result
    exit 1
  fi

  # If this setup to be moved to other systems each installer must provide
  # setup_system specific setup_home routine
  for dependency in $result; do
    echo "-- Install $dependency"
    path=$INSTALLERS/$dependency
    export THIS=$path
    source "$path/install.sh"
    install
  done
}

print_help() {
  echo "Sweet Home Installer"
  echo "Usage:"
  echo "  all                   Run all features"
  echo "  system                Run system setup"
  echo "  home   --only TARGET  Run home directory setup"
  echo "  help                  Print help"
}

export OPTION_SYSTEM=false
export OPTION_INSTALL=false
export OPTION_ONLY=

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
      --only)
        OPTION_ONLY=$1
        shift
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
