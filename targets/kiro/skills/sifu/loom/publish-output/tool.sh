#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task publish-output`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task publish-output "$1" "$2"
