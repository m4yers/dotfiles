#!/usr/bin/env bash

export ROOT="$( cd "$( dirname "$0" )" && pwd )"
export PROJECTS=$(dirname $ROOT)
export SCRIPTS="$ROOT/scripts"
export TARGETS="$ROOT/targets"
export DEPENDENCIES="$ROOT/dependencies"

source $ROOT/scripts/shared.sh

check_system() {
  if ! is_mac; then
    echo "Mac only installer is available"
    exit 1
  fi
}

bootstrap_bash() {
  echo "BOOTSTRAP USER BASH"
  echo

  source $ROOT/scripts/bash.sh

  cat $TARGETS/bash/bashrc > $BASHRC
  echo "source $BASHRC" > $BASHPROFILE

  bash_export_global PROJECTS $PROJECTS
  bash_export_global DOTFILES $ROOT

  echo "DONE"
  echo
}

bootstrap_python() {
  echo "BOOTSTRAP SYSTEM PYTHON"
  echo

  local dep_dir="$DEPENDENCIES/pip"

  mkdir -p $dep_dir

  curl https://bootstrap_python.pypa.io/get-pip.py -o $dep_dir/get-pip.py
  ls $dep_dir
  sudo /usr/bin/python $dep_dir/get-pip.py

  local dep_dir="$DEPENDENCIES/requirements"
  /usr/local/bin/pip install --target $dep_dir -r $ROOT/requirements.txt

  echo "DONE"
  echo
}

bootstrap () {
  rm -rf $DEPENDENCIES
  mkdir -p $DEPENDENCIES
  bootstrap_bash
  bootstrap_python
}

setup_system() {
  echo "Skipping system"
  # source $ROOT/scripts/macos.sh
}

setup_home() {
  echo "SETUP HOME"
  echo

  bootstrap

  targets=
  if [[ -z $OPTION_ONLY ]]; then
    targets=$(python $SCRIPTS/topology.py $TARGETS)
  else
    targets=$(python $SCRIPTS/topology.py $TARGETS --for $OPTION_ONLY)
  fi

  if [[ $? != 0 ]]; then
    echo $targets
    exit 1
  fi

  # If this setup to be moved to other systems each installer must provide
  # setup_system specific setup_home routine

  echo "TARGETS: $targets"
  for target in $targets; do
    echo "INSTALLING $target..."
    echo

    path=$TARGETS/$target
    export THIS=$path
    source "$path/install.sh"
    install

    echo "DONE $target"
  done
}

print_help() {
  echo "Sweet Home Installer"
  echo "Usage:"
  echo "... all                   Run all features"
  echo "... system                Run system setup"
  echo "... home   --only TARGET  Run home directory setup"
  echo "... help                  Print help"
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
