#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task design-render`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task design-render "$1" "$2"
