#!/bin/bash

llvm-dev-update-env() {
  source $LLVM_DEV_ENV
}

llvm-dev-clear() {
  rm -rf $LLVM_DEV_ENV
  rm -rf $LLVM_DEV_WORKSPACE
  rm -rf $LLVM_DEV_BUILD
  rm -rf $LLVM_DEV_INSTALL

  echo "Sector clear."
}

llvm-dev-build() {
  cmake --build $LLVM_DEV_BUILD
}

llvm-dev-install() {
  cmake --build $LLVM_DEV_BUILD --target install
}

# Run tests using just build llvm-lit
alias ldt='llvm-dev-test '
llvm-dev-test() {
  $LLVM_DEV_BUILD/bin/llvm-lit $1
}

alias lgs='llvm-dev-go-samples '
llvm-dev-go-samples() {
  cd $LLVM_DEV_WORKSPACE/Samples
}

alias lgr='llvm-dev-go-root '
llvm-dev-go-root() {
  cd $LLVM_DEV_ROOT
}

# Copy a file as dev sample. Each sample is contained in
# a separate directory named after sample or custom named
alias lsf='llvm-dev-sample-from '
llvm-dev-sample-from() {
  FILE=$(realpath $1)
  SAMPLE=${2:-$FILE}
  SAMPLE=${FILE##*/}
  SAMPLE=${SAMPLE%.*}
  SAMPLE=$LLVM_DEV_WORKSPACE/Samples/$SAMPLE

  if [[ -d $SAMPLE ]]; then
    echo "Sample already exists."
    return 1
  fi

  mkdir -p $SAMPLE
  pushd $SAMPLE &> /dev/null
  cp $FILE .
}

alias lsn='llvm-dev-sample-new '
llvm-dev-sample-new() {
  SAMPLE=${1%/}
  mkdir $TEST/$SAMPLE
  printf "int main() {\n  return 0;\n}" >  $TEST/$SAMPLE/$SAMPLE.c
}
