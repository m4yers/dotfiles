#!/usr/bin/env bash
# banner-sh — canonical `tool.sh` reference for the hello-graph. Reads
# `greeting` from the materialised input.yaml at $1 and writes
# `banner: "*** <greeting> ***"` to the output.yaml path at $2. The
# argv contract is documented in ../../../guide.md §2:
#   tool.sh <input.yaml> <output.yaml>   (cwd = task workdir)
# YAML I/O goes through stdlib-only `python3 -c` snippets so the
# reference skill picks up no third-party dep; packaged shell tools
# (e.g. via a uv project under `tool/`) plug in exactly the same
# argv contract.
set -euo pipefail

INPUT="$1"
OUTPUT="$2"

greeting=$(python3 -c '
import sys, yaml
with open(sys.argv[1]) as fh:
    doc = yaml.safe_load(fh) or {}
sys.stdout.write(doc["greeting"])
' "$INPUT")

python3 -c '
import sys, yaml
banner = f"*** {sys.argv[1]} ***"
with open(sys.argv[2], "w") as fh:
    yaml.safe_dump({"banner": banner}, fh, sort_keys=False)
' "$greeting" "$OUTPUT"
