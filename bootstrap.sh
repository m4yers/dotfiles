#!/usr/bin/env bash

export ROOT="$( cd "$( dirname "$0" )" && pwd )"
export SCRIPTS="$ROOT/scripts"
export TARGETS="$ROOT/targets"
export DEPENDENCIES="$ROOT/dependencies"

source $SCRIPTS/shared.sh

check_system() {
  if ! is_mac; then
    echo "Mac only installer is available"
    exit 1
  fi
}

setup_dependencies() {
  rm -rf $DEPENDENCIES
  mkdir -p $DEPENDENCIES
}

bootstrap_bash() {
  echo "BOOTSTRAP USER BASH"
  echo

  source $ROOT/scripts/bash.sh

  cat $ROOT/targets/essentials/bash/bashrc > $BASHRC
  echo "source $BASHRC" > $BASHPROFILE

  bash_export_global PROJECTS $PROJECTS
  bash_export_global DOTFILES $ROOT

  echo DONE
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
  echo "Not implemented"
}

setup_essentials() {
  echo "SETUP ESSENTIALS"
  echo

  check_system

  bootstrap

  targets=$(python $SCRIPTS/topology.py $TARGETS/essentials)

  echo "TARGETS: $targets"
  echo

  for target in $targets; do
    echo "INSTALLING $target..."
    echo
    path=$TARGETS/essentials/$target
    export THIS=$path
    source $BASHRC
    source "$path/install.sh"
    install
    echo "DONE $target"
    echo
  done

  echo "DONE ESSENTIALS"
  echo
}

setup_development() {
  echo "Not implemented"
}

setup_reversing() {
  echo "Not implemented"
}

setup_all() {
  echo "Not implemented"
}

print_help() {
  echo "Sweet Home Installer"
  echo "Usage:"
  echo "... sytem                 Install operating system features"
  echo "... essentials            Install essentials setup"
  echo "... development           Install development setup"
  echo "... reversing             Install reverse-engineering setup"
  echo "... all                   Install all features"
  echo "... help                  Print help"
}

are_you_sure() {
  if ! yesno "Do you really want this?" "no"; then exit 0; fi
}

main() {
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
        are_you_sure
        setup_all
        ;;
      essentials)
        are_you_sure
        setup_essentials
        ;;
      development)
        are_you_sure
        setup_development
        ;;
      reversing)
        are_you_sure
        setup_reversing
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
}

main "$@"
