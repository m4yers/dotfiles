#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task audit-aggregate`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task audit-aggregate "$1" "$2"
