#!/usr/bin/env bash


is_mac() {
  unamestr=`uname`
  test $unamestr == 'Darwin'
}

is_linux() {
  unamestr=`uname`
  test $unamestr == 'Linux'
}

yesno() {
  local display=$1; shift
  local default=${1,,}; shift
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
        echo "You must choose between \"yes\" or \"no\""
        exit 1
        ;;
    esac
  done
}
