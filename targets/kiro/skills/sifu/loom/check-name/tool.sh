#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task check-name`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task check-name "$1" "$2"
