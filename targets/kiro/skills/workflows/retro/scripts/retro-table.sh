#!/bin/bash
# Print pending retro items as a colored formatted table, sorted by severity then area.
DIR="$HOME/.kiro/retro/pending"
if [ ! -d "$DIR" ] || [ -z "$(ls "$DIR"/*.json 2>/dev/null)" ]; then
  echo "No pending retro items."
  exit 0
fi

RED=$'\033[31m'
YEL=$'\033[33m'
DIM=$'\033[2m'
BOLD=$'\033[1m'
RST=$'\033[0m'

ROWS=""
for f in "$DIR"/*.json; do
  ROW=$(python3 -c "
import json, os
d = json.load(open('$f'))
sev = d['severity']
sk = {'high':1,'medium':2,'low':3}.get(sev, 9)
area = d.get('area', 'unknown')
action = d.get('action', '?')
target = d.get('target') or '—'
# Extract just the name from a path
if target != '—':
    parts = target.replace('~/.kiro/', '').rstrip('/').split('/')
    if 'SKILL.md' in parts:
        parts.remove('SKILL.md')
    if parts and parts[0] in ('skills', 'steering', 'prompts'):
        parts = parts[1:]
    if parts and parts[0] in ('tools', 'workflows'):
        parts = parts[1:]
    target = '/'.join(parts) if parts else os.path.basename(target)
    if target.endswith('.md'):
        target = target[:-3]
title = d['title']
print(f'{sk}\t{sev}\t{area}\t{action}\t{target}\t{title}')
")
  ROWS="${ROWS}${ROW}
"
done

SORTED=$(echo "$ROWS" | grep -v '^$' | sort -t$'\t' -k1,1n -k3,3 -k4,4)

printf "${BOLD}%-4s %-2s %-10s %-8s %-20s %s${RST}\n" "#" "" "Area" "Action" "Target" "Finding"
i=1
echo "$SORTED" | while IFS=$'\t' read -r _ sev area action target title; do
  case "$sev" in
    high)   color="$RED";  icon="●" ;;
    medium) color="$YEL";  icon="◐" ;;
    low)    color="$DIM";  icon="○" ;;
    *)      color="$RST";  icon="?" ;;
  esac
  printf "${color}%-4s %s  %-10s %-8s %-20s %s${RST}\n" "$i" "$icon" "$area" "$action" "$target" "$title"
  i=$((i + 1))
done
