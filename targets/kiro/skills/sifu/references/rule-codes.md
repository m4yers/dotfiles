# Rule Codes and Severity

**Code:** RUL
**Applies:** rule-refs

How conventions references turn into review checks: every rule carries a code
and a 0-100 severity, parsed by `scripts/sifu/sifu/rules.py`, filtered by topic
in `audit-checks`, and judged three at a time by `audit-shard`.

## 1. Codes

1. (rule: RUL-1-1, severity: 90) A conventions reference MUST declare
   `**Code:** XXX` (three uppercase letters, unique across `references/`) on
   the second non-blank line, because the parser derives every rule id from
   it. (check: `autochecks/rule_codes.py:rule_1_1_file_code`)
2. (rule: RUL-1-2, severity: 90) Every numbered rule under a numbered `## N.`
   heading MUST begin with `(rule: XXX-<section>-<rule>, severity: <n>)`
   matching the rule's position, because a drifted code mislabels findings.
   (check: `autochecks/rule_codes.py:rule_1_2_code_matches_position`)
3. (rule: RUL-1-3, severity: 70) A conventions reference MUST declare
   `**Applies:** <topic>[, <topic>]` on the line after the code, `always` for
   unconditional files. (check: `autochecks/rule_codes.py:rule_1_3_applies_header`)

| Reference                    | Code | Applies                     |
| ---------------------------- | ---- | --------------------------- |
| `authoring.md`               | AUT  | always                      |
| `style.md`                   | STY  | always                      |
| `completion.md`              | CMP  | always                      |
| `triggers.md`                | TRG  | always                      |
| `model-awareness.md`         | MOD  | always                      |
| `script-conventions.md`      | SCR  | scripts, loom               |
| `secure-llm-conventions.md`  | SEC  | prompts, subagents          |
| `workflow-conventions.md`    | WFL  | type:workflow               |
| `interface-conventions.md`   | IFC  | type:interface              |
| `tool-conventions.md`        | TOL  | type:tool                   |
| `reference-conventions.md`   | REF  | type:reference, references  |
| `flow-conventions.md`        | FLW  | type:flow                   |
| `rule-codes.md`              | RUL  | rule-refs                   |

`design-*.md` and `plan-topology.md` hold no rules and carry no code.

## 2. Severity

1. (rule: RUL-2-1, severity: 80) Severity MUST be `base(keyword) +
   impact(class)`, clamped to 0-100, where the keyword is the first RFC 2119
   keyword in the rule text outside backticks and parentheses and the author
   picks the impact class from the table below.
2. (rule: RUL-2-2, severity: 80) The annotated severity MUST lie in the
   keyword's reachable range (base to base + 30), because a number outside it
   means the formula was not applied. (check:
   `autochecks/rule_codes.py:rule_2_2_severity_in_range`)

Keyword bases: MUST NOT 70, MUST 65, SHOULD and SHOULD NOT 45, MAY and NOT
REQUIRED 20, no keyword 10. A ban scores highest because it marks a boundary the
author would not negotiate; guidance without a keyword is advice.

| Impact class | What breaks when the rule is violated              | Add |
| ------------ | -------------------------------------------------- | --- |
| safety       | security frame, destructive action, PII, data loss | +30 |
| run breaks   | graph invalid, script contract mismatch, no output | +25 |
| wrong output | guessing, silent drift, misrouting, overtriggering | +15 |
| maintenance  | duplication, orphans, drift risk                   | +5  |
| style        | wrapping, tables, wording                          | +0  |

Examples: SEC-2-2 (frame MUST be injected) 65 + 30 = 95; WFL-3-4 (graphs MUST
validate) 65 + 25 = 90; SCR-2-1 (oracle MUST be deterministic) 65 + 15 = 80;
SCR-1-5 (MUST handle errors) 65 + 15 = 80; STY-1-7 (prose MUST fill) 65 + 0 =
65; STY-1-1 (tables SHOULD) 45 + 0 = 45.

## 3. Review Bands

| Band    | Range  | Review                                  | Create / update |
| ------- | ------ | --------------------------------------- | --------------- |
| Error   | 90-100 | sharded; `skill-modify` applies the fix | included        |
| Warning | 70-89  | sharded; `skill-modify` applies the fix | included        |
| Info    | 50-69  | sharded; applied only when one-line     | included        |
| below   | 0-49   | not sharded                             | included        |

References are included whole into `design-author` and `skill-materialize`, so
rules below 50 still shape new skills; review only judges the bands. Rules with
a `(check: ...)` back-pointer are never sharded: `audit-autochecks` emits them
with the rule's severity and confidence 100.

## 4. Topics

`audit-topics` probes the skill directory and emits every matching topic:
`always`; `type:<interface|tool|workflow|reference|flow>` from the
frontmatter; `scripts` (`scripts/` exists); `python` (`*.py`); `bash` (`*.sh`);
`loom` (any `loom*/` directory); `prompts` (`*.md.j2` under
`loom*/`); `templates`; `schemas`; `references`; `subagents` (SKILL.md
mentions `subagent` or `sub-agent`); `rule-refs` (a reference declares
`**Code:**`). A reference is selected when any of its `Applies` topics is
detected; rules inside a selected file are filtered by severity only.

## 5. Finding Confidence

Each shard finding carries `confidence` 70-100, as in code-review: 90-100 proven
from the cited text and file; 80-89 one cross-file fact assumed; 70-79 depends
on an unread file or runtime behaviour; below 70 is discarded. The report sorts
by severity, then confidence. Design-drift findings from
`audit-design` and `audit-design-update` use fixed codes: DSN-1-1 planned file
missing or not implementing its summary (95), DSN-1-2 deleted file still
referenced (90), DSN-1-3 change outside the plan (75).
