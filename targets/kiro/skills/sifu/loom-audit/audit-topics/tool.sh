#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task audit-topics`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task audit-topics "$1" "$2"
