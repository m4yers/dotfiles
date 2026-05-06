#!/usr/bin/env bash
# Log a skill activation to the analytics JSONL file.
# Usage: add-invocation.sh <skill> <trigger>
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: add-invocation.sh <skill> <trigger>" >&2
  exit 1
fi

SKILL="$1"
TRIGGER="$2"

# Validate trigger format: type:name
if [[ ! "$TRIGGER" =~ ^(user|skill|prompt|agent|steering):[a-zA-Z0-9._-]+$ ]]; then
  echo "Invalid trigger '$TRIGGER': must be type:name" >&2
  echo "  types: user, skill, prompt, agent, steering" >&2
  exit 1
fi

FILE=~/kiro-analytics/skill-usage.jsonl

mkdir -p "$(dirname "$FILE")"
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"skill\":\"${SKILL}\",\"trigger\":\"${TRIGGER}\",\"host\":\"$(hostname -s)\",\"pid\":\"$$\"}" >> "$FILE"
