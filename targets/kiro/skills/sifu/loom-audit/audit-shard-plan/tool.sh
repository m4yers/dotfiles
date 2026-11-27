#!/usr/bin/env bash
# loom argv (input.yaml output.yaml) -> `sifu.sh task audit-shard-plan`.
exec "$(dirname "$(readlink -f "$0")")/../../scripts/sifu.sh" task audit-shard-plan "$1" "$2"
