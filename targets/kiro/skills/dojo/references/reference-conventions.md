# Reference Skill Conventions

Conventions specific to skills with `type: reference`. These supplement the
general authoring rules in `authoring.md`.

## Contents

- [1. Definition](#1-definition)
- [2. Required Sections](#2-required-sections)
- [3. Section Order](#3-section-order)
- [4. Topic Focus](#4-topic-focus)
- [5. Forbidden Shapes](#5-forbidden-shapes)

## 1. Definition

1. A reference skill MUST be a passive rule set loaded as context when a
   condition is met.
2. A reference skill MUST NOT have an invocation, API, commands, phases, or
   steps, because the agent reads it and follows the rules — it does not call
   it.
3. Reference skills SHOULD favour brevity over completeness; the SKILL.md MUST
   be scannable in seconds and detail MUST be moved to `references/` files.
4. A reference skill MUST cover one domain; rules from unrelated domains MUST
   live in separate skills.

## 2. Required Sections

1. The frontmatter `description` MUST state when the skill is loaded using "MUST
   load whenever" phrasing — this is the only invocation a reference has (e.g.,
   "MUST load whenever writing, modifying, or reviewing C++ code"). (check:
   `autochecks/reference_conventions.py:85`)
2. The body MUST contain rules organised by topic, using RFC 2119 keywords
   (MUST, SHOULD, MAY).
3. Rules MUST be actionable — each rule tells the agent what to do or not do,
   not explain background.
4. Detailed material (full style guides, examples, specs) MUST live in
   `references/*.md` files, not inline; SKILL.md contains the essential rules
   and references hold exhaustive detail.

## 3. Section Order

```
(trigger condition + essential rules)
## Completion
```

Reference skills are typically short. When section headers are needed, organise
by topic (e.g., "Before Writing Code", "Writing Code", "After Writing Code").
There is no prescribed set of headers — use whatever fits the domain.

## 4. Topic Focus

1. Each `references/*.md` file MUST cover exactly one topic, because a file
   mixing unrelated topics is harder to search, forces the agent to skim past
   irrelevant material on every load, and grows without bound.

2. A file containing two unrelated topic groups MUST be split along the topic
   boundary.

3. Files over 100 lines SHOULD include a table of contents within the first 30
   lines.

4. Files over 300 lines SHOULD be split unless the single topic genuinely needs
   that depth. (check: `autochecks/reference_conventions.py:10`)

5. Every `references/*.md` MUST be reachable from SKILL.md via the markdown link
   graph (chains allowed); orphan files signal a missing link or a file that no
   longer belongs.

## 5. Forbidden Shapes

1. Reference skills MUST NOT contain procedures or workflows, because those
   belong in `tool` or `workflow` skills. (check:
   `autochecks/reference_conventions.py:28`)
2. Reference skills MUST NOT contain script APIs, because those belong in
   `interface` skills. (check: `autochecks/reference_conventions.py:47`)
3. Reference skills MUST NOT contain Invocation or API sections, because
   references are not called. (check: `autochecks/reference_conventions.py:66`)
