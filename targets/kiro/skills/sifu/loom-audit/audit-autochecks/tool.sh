#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task audit-autochecks`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task audit-autochecks "$1" "$2"
