#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task skill-fix-count`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task skill-fix-count "$1" "$2"
