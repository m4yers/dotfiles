#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task check-overlaps`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task check-overlaps "$1" "$2"
