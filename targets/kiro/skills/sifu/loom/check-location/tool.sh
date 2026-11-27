#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task check-location`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task check-location "$1" "$2"
