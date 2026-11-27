#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task audit-report`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task audit-report "$1" "$2"
