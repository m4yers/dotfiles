#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task audit-checks`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task audit-checks "$1" "$2"
