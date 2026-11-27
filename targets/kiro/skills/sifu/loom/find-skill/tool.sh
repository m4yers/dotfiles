#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task find-skill`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task find-skill "$1" "$2"
