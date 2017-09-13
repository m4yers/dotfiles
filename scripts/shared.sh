#!/usr/bin/env bash

is_mac() {
  local unamestr=`uname`
  test $unamestr == 'Darwin'
}

is_linux() {
  local unamestr=`uname`
  test $unamestr == 'Linux'
}

error() {
  local message=${1:-"Something went wrong"}
  local code=${2:-1}
  echo $message
  exit $code
}

assert_prev() {
  local message=${1:-"Something went wrong"}
  local code=${2:-1}
  [[ $? != 0 ]] && error $message $code
}

yesno() {
  local display=$1; shift
  local default=${1:-yes}; shift
  while true
  do
    echo "${display} Yes/No? (Default: $default)"
    read -r answer
    [[ -z "$answer" ]] && answer=$default

    answer=${answer,,}
    case $answer in
      yes)
        return 0
        ;;
      no)
        return 1
        ;;
      *)
        error "You must choose between \"yes\" or \"no\""
        ;;
    esac
  done
}
