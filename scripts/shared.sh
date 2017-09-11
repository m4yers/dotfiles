#!/bin/sh

is_mac() {
  unamestr=`uname`
  test $unamestr == 'Darwin'
}

is_linux() {
  unamestr=`uname`
  test $unamestr == 'Linux'
}
