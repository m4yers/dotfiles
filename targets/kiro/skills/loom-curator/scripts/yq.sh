#!/usr/bin/env bash
# yq.sh — read YAML/JSON from stdin, print value at KEY.
#
# Thin wrapper around `yq` (kislyuk variant) provisioned via `uv`.
# `uv tool run` installs yq into a managed cache on first call and
# reuses it thereafter, so callers never need a global yq install.
#
# Usage:
#     curator.sh ingest "$URL" | yq.sh .workdir
#     yq.sh '.ready[0].id' < /tmp/next.yaml
#
# All flags are passed through to yq, so callers can use jq syntax
# directly:
#     yq.sh -r '.ready | length' < /tmp/next.yaml
set -euo pipefail
exec uv tool run --quiet yq -r "$@"
