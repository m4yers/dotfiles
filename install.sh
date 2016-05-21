#!/bin/bash

export here="$( cd "$( dirname "$0" )" && pwd )"

for install in $(ls $here/*/install.sh) ; do
    source $install
done
