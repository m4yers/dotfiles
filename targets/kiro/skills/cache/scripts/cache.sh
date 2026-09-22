#!/usr/bin/env bash
# cache.sh — thin shim that dispatches every argument to cache.py.
# All logic (arg parsing, mode gating, key resolution, gc, selftest)
# lives in cache.py; this shim exists so callers can shell out via a single
# stable path without knowing python invocation details.
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPTS_DIR/cache.py" "$@"
