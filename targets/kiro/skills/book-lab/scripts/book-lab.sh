#!/usr/bin/env bash
# book-lab.sh — shim for the book-lab skill. Dispatches to the stdlib
# `book_lab.py` CLI (subcommands `init`, `status`, `scaffold`, `commit`).
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPTS_DIR/book_lab.py" "$@"
