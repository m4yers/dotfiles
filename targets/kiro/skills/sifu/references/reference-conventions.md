# Reference Skill Conventions

**Code:** REF
**Applies:** type:reference, references

Conventions specific to skills with `type: reference`. These supplement the
general authoring rules in `authoring.md`.

## Contents

- [1. Definition](#1-definition)
- [2. Required Sections](#2-required-sections)
- [3. Section Order](#3-section-order)
- [4. Topic Focus](#4-topic-focus)
- [5. Forbidden Shapes](#5-forbidden-shapes)

## 1. Definition

1. (rule: REF-1-1, severity: 80) A reference skill MUST be a passive rule set
   loaded as context when a condition is met.
2. (rule: REF-1-2, severity: 85) A reference skill MUST NOT have an invocation,
   API, commands, phases, or steps, because the agent reads it and follows the
   rules — it does not call it.
3. (rule: REF-1-3, severity: 70) A reference skill MUST cover one domain; rules
   from unrelated domains MUST live in separate skills.

## 2. Required Sections

1. (rule: REF-2-1, severity: 90) The frontmatter `description` MUST state when
   the skill is loaded using "MUST load whenever" phrasing — this is the only
   invocation a reference has (e.g., "MUST load whenever writing, modifying, or
   reviewing C++ code"). (check:
   `autochecks/reference_conventions.py:rule_2_1_must_load_when`)
2. (rule: REF-2-2, severity: 80) The body MUST contain rules organised by topic,
   using RFC 2119 keywords (MUST, SHOULD, MAY).
3. (rule: REF-2-3, severity: 80) Rules MUST be actionable — each rule tells the
   agent what to do or not do, not explain background.

## 3. Section Order

```
(trigger condition + essential rules)
## Completion
```

Reference skills are typically short. When section headers are needed, organise
by topic (e.g., "Before Writing Code", "Writing Code", "After Writing Code").
There is no prescribed set of headers — use whatever fits the domain.

## 4. Topic Focus

1. (rule: REF-4-1, severity: 70) Each file under `references/` MUST cover
   exactly one topic, because a file mixing unrelated topics is harder to
   search, forces the agent to skim past irrelevant material on every load, and
   grows without bound.

2. (rule: REF-4-2, severity: 70) A file containing two unrelated topic groups
   MUST be split along the topic boundary.

3. (rule: REF-4-3, severity: 50) Files over 300 lines SHOULD be split unless the
   single topic genuinely needs that depth. (check:
   `autochecks/reference_conventions.py:rule_4_3_file_length`)

## 5. Forbidden Shapes

1. (rule: REF-5-1, severity: 85) Reference skills MUST NOT contain procedures or
   workflows, because those belong in `tool` or `workflow` skills. (check:
   `autochecks/reference_conventions.py:rule_5_1_no_procedures`)
2. (rule: REF-5-2, severity: 85) Reference skills MUST NOT contain script APIs,
   because those belong in `interface` skills. (check:
   `autochecks/reference_conventions.py:rule_5_2_no_script_apis`)
3. (rule: REF-5-3, severity: 85) Reference skills MUST NOT contain Invocation or
   API sections, because references are not called. (check:
   `autochecks/reference_conventions.py:rule_5_3_no_invocation_api`)
