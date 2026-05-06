# Reference Skill Conventions

Conventions specific to skills with `type: reference`. These
supplement the general conventions in `conventions.md`.

## What a Reference Skill Is

A passive rule set loaded as context when a condition is met. It
has no invocation, no API, no commands, no phases, no steps. The
agent reads it and follows the rules — it does not call it.

## Required Sections

### 1. Trigger Condition

The description MUST state when the skill is loaded using "MUST
load whenever" phrasing. This is the only "invocation" a reference
has.

Example:
```
MUST load whenever writing, modifying, or reviewing C++ code.
```

### 2. Rules

The body contains rules organized by topic. Rules use RFC2119
keywords (MUST, SHOULD, MAY) like all skills. Keep rules
actionable — each rule should tell the agent what to do or not do,
not explain background.

### 3. References (when needed)

Detailed material (full style guides, examples, specs) MUST live
in `references/` files, not inline. The SKILL.md contains the
essential rules; reference files contain the exhaustive detail.

## Section Order

```
(trigger condition + essential rules)
## Completion
```

Reference skills are typically short. If the skill needs section
headers, organize by topic (e.g., "Before Writing Code", "Writing
Code", "After Writing Code"). There is no prescribed set of
headers — use whatever fits the domain.

## What Does NOT Belong

- Procedures or workflows — use `tool` or `workflow`
- Script APIs — use `interface`
- Invocation or API sections — references are not called

## Principles

- Brevity over completeness. The SKILL.md should be scannable in
  seconds. Move detail to `references/`.
- Rules over explanations. "MUST use braces for all if blocks" not
  "braces help prevent bugs when..."
- One domain per skill. Don't combine C++ rules and Python rules
  in one reference skill.
