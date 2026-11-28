#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task show-report`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task show-report "$1" "$2"
