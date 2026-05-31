---
name: skill-analytics
type: interface
description: Skill usage analytics — format, storage, and querying. Use when the user says "skill analytics", "skill usage", "which skills", "prune skills", or wants to see how skills are used. Do NOT use for creating or reviewing skills — use dojo instead.
---

# Skill Analytics

Track skill activations across all dev desktops and
sessions.

## Storage

Single append-only JSONL file shared across all hosts:

```
~/shared/kiro-analytics/skill-usage.jsonl
```

## Record Format

Each activation appends one JSON line:

```json
{"ts":"2026-03-31T12:48:54Z","skill":"cr-review","trigger":"user","host":"dev1","pid":"12345"}
```

| Field     | Description                          |
|-----------|--------------------------------------|
| `ts`      | UTC ISO 8601 timestamp               |
| `skill`   | Skill name (kebab-case)              |
| `trigger` | What caused activation (see below)   |
| `host`    | Short hostname (`hostname -s`)       |
| `pid`     | Shell PID, groups a session          |

### Trigger Values

Format: `type:name` where name is the file name without
directory or extension.

| Value               | Example              | Meaning                  |
|---------------------|----------------------|--------------------------|
| `user:<login>`      | `user:artyomgo`      | User requested the skill |
| `skill:<name>`      | `skill:cr-review`    | Another skill chained in |
| `prompt:<name>`     | `prompt:daily`       | A prompt triggered it    |
| `agent:<name>`      | `agent:trusted`      | A subagent invoked it    |
| `steering:<name>`   | `steering:no-rush`   | A steering rule triggered it |

## Logging

Every skill MUST include this at the start of its first
workflow step:

```bash
~/.kiro/skills/home/skill-analytics/scripts/add-invocation.sh \
  SKILL_NAME TRIGGER_TYPE:TRIGGER_NAME
```

Replace `SKILL_NAME` with the skill's name and
`TRIGGER_TYPE:TRIGGER_NAME` with the appropriate trigger
value (see Trigger Values above). The script validates
the format.

## Querying

```bash
# Most used skills
jq -r .skill ~/shared/kiro-analytics/skill-usage.jsonl \
  | sort | uniq -c | sort -rn

# Trigger breakdown
jq -r .trigger ~/shared/kiro-analytics/skill-usage.jsonl \
  | sort | uniq -c | sort -rn

# Per-host usage
jq -r '[.host,.skill]|@tsv' \
  ~/shared/kiro-analytics/skill-usage.jsonl \
  | sort | uniq -c | sort -rn

# Usage by day
jq -r '.ts[:10]+" "+.skill' \
  ~/shared/kiro-analytics/skill-usage.jsonl \
  | sort | uniq -c

# Skills not used in last 30 days
comm -23 \
  <(ls ~/.kiro/skills/**/SKILL.md \
    | xargs grep -l '^name:' \
    | xargs grep 'name:' \
    | sed 's/.*name: //' | sort) \
  <(jq -r .skill ~/shared/kiro-analytics/skill-usage.jsonl \
    | sort -u)
```

## Completion

| Status               | Criteria                        |
|----------------------|---------------------------------|
| `DONE`               | Query results shown to user     |
| `DONE_WITH_CONCERNS` | JSONL file missing or empty     |
| `BLOCKED`            | ~/shared not accessible         |
| `NEEDS_CONTEXT`      | User query unclear              |
