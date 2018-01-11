#!/usr/bin/env bash

# LLVM ROOT is a root directory containing LLVM source, build and install
# directories on the same level
HERE=$(pwd)
LLVM_DEV_ROOT=${1:-$HERE}
export LLVM_DEV_ROOT=$(realpath $LLVM_DEV_ROOT)
export LLVM_DEV_TARGET=${2:-all}
export LLVM_DEV_BUILD_TYPE=${3:-Debug}

if test -z $LLVM_DEV_ROOT; then
  echo "You have to provide an LLVM_DEV_ROOT source directory."
  exit 1
fi

if ! test -d $LLVM_DEV_ROOT; then
  echo "You have provided an invalid LLVM_DEV_ROOT source directory."
  exit 1
fi

pushd $LLVM_DEV_ROOT

export LLVM_DEV_ENV=$LLVM_DEV_ROOT/llvm-dev-env.sh
if [[ -f $LLVM_DEV_ENV ]]; then
  "LLVM Dev environment already exist. Run llvm-dev-clear first."
  exit 1
fi

export LLVM_DEV_SOURCE=$LLVM_DEV_ROOT/llvm
export LLVM_DEV_WORKSPACE=$LLVM_DEV_ROOT/dev-workspace
export LLVM_DEV_BUILD=$LLVM_DEV_ROOT/dev-build
export LLVM_DEV_INSTALL=$LLVM_DEV_ROOT/dev-install

export PATH=$LLVM_DEV_BUILD/bin:$PATH

mkdir -p $LLVM_DEV_WORKSPACE $LLVM_DEV_BUILD $LLVM_DEV_INSTALL

pushd $LLVM_DEV_BUILD
cmake \
  -DCMAKE_BUILD_TYPE=$LLVM_DEV_BUILD_TYPE  \
  -DCMAKE_INSTALL_PREFIX=$LLVM_DEV_INSTALL \
  -DLLVM_TARGETS_TO_BUILD=$LLVM_DEV_TARGET \
  -G Ninja $LLVM_DEV_SOURCE
popd

DIR=$(dirname $(realpath $0))
env | grep ^LLVM_DEV > $LLVM_DEV_ENV
echo >> $LLVM_DEV_ENV
echo 'export PATH=$LLVM_DEV_BUILD/bin:$PATH' >> $LLVM_DEV_ENV
echo >> $LLVM_DEV_ENV
echo "source $DIR/llvm-dev-support.sh" >> $LLVM_DEV_ENV
echo
echo "Now, source llvm-dev-env.sh"
