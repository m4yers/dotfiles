#!/usr/bin/env bash
# curator.sh — CLI wrapper for the curator package. Resolves the
# scripts dir relative to itself so the wrapper works regardless of
# CWD, runs the package's own uv venv.
#
# Usage:
#   curator.sh ingest <url-or-path>
#   curator.sh next <workdir>
#   curator.sh complete <workdir> <task-id>
#   curator.sh status <workdir>
#   curator.sh source fetch <url-or-path>
#   curator.sh source convert <path> [--task-workdir <wd>]
#   curator.sh vault match [--keywords P] [--people P] [--models P]
#   curator.sh vault report <workdir>
#   curator.sh vault replica build|apply|prune|strip-dead-links <wd>
#
# Run `curator.sh --help` for the full subcommand tree.
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    CURATOR_SH="$0" \
    uv run --project "$SCRIPTS_DIR/curator" \
    python -m curator "$@"
