#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task design-render-update`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task design-render-update "$1" "$2"
