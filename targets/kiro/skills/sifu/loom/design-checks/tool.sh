#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task design-checks`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task design-checks "$1" "$2"
