#!/usr/bin/env bash
# vault.sh — CLI wrapper for the vault package. Resolves the
# scripts dir relative to itself so the wrapper works regardless of
# CWD, runs the package's own uv venv.
#
# Usage:
#   vault.sh agents <folder>...
#   vault.sh agents <folder>...
#   vault.sh source fetch <url-or-path>
#   vault.sh source convert <path> --task-workdir <wd>
#   vault.sh vault match [--keywords P] [--people P] [--models P]
#   vault.sh vault read <vault-path>
#   vault.sh vault write <vault-path> [--frontmatter JSON]
#                                     [--body-file P] [--dry-run]
#   vault.sh vault list <folder>
#   vault.sh vault search <query> [--folder F]...
#   vault.sh vault diff-fm <vault-path> [--baseline JSON]
#   vault.sh vault obsidian move|rename|delete <src> [<dst-or-name>]
#
# Run `vault.sh --help` for the full subcommand tree.
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    VAULT_SH="$0" \
    uv run --project "$SCRIPTS_DIR/vault" \
    python -m vault "$@"
