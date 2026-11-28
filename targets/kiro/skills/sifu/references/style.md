# Skill Style

**Code:** STY
**Applies:** always

How skill prose is written: style, handles, instruction freedom and
effectiveness. Supplements `authoring.md`.

## Contents

- [1. Style Guide](#1-style-guide)
- [2. Handle Policy](#2-handle-policy)
- [3. Degrees of Freedom](#3-degrees-of-freedom)
- [4. Instruction Effectiveness](#4-instruction-effectiveness)

## 1. Style Guide

01. (rule: STY-1-1, severity: 45) Reference data SHOULD use tables, not prose,
    because tables are denser for scannable lookup.

02. (rule: STY-1-2, severity: 80) Aliases and primary commands MUST appear up
    front in SKILL.md.

03. (rule: STY-1-3, severity: 75) Skills MUST NOT have a README.md, because
    SKILL.md is the single source of truth. (check:
    `autochecks/authoring.py:rule_5_3_no_readme`)

04. (rule: STY-1-4, severity: 80) Constraints MUST use RFC 2119 keywords (MUST,
    SHOULD, MAY, MUST NOT) and negative constraints MUST carry a "because
    \[reason\]" clause. (check:
    `autochecks/authoring.py:rule_5_4_constraints_form`)

05. (rule: STY-1-5, severity: 65) SQL queries MUST live in `references/`,
    because keeping them out of SKILL.md preserves scannability.

06. (rule: STY-1-6, severity: 65) Tables MUST be whitespace-aligned for
    readability.

07. (rule: STY-1-7, severity: 65) Prose lines MUST fill to at least 75 chars
    before wrapping at 80; tables MAY extend to 100 chars. (check:
    `autochecks/authoring.py:rule_5_7_line_widths`)

08. (rule: STY-1-8, severity: 60) Constraints SHOULD be written in positive
    form; MUST NOT is reserved for hard safety boundaries, because reserving
    the keyword preserves its weight when authors reach for it on a genuine
    boundary.

09. (rule: STY-1-9, severity: 80) RFC 2119 keywords MUST stand alone; authors
    MUST NOT prefix them with "CRITICAL", "IMPORTANT", "ALWAYS", or exclamation
    marks, because the model overtriggers on amplified language. (check:
    `autochecks/authoring.py:rule_5_9_emphasis_stacking`)

10. (rule: STY-1-10, severity: 70) Authors MUST challenge every token before
    adding it: ask whether the model already knows what is being explained.

11. (rule: STY-1-11, severity: 80) When multiple approaches exist, skills MUST
    recommend a single default with an escape hatch for edge cases.

12. (rule: STY-1-12, severity: 70) Every file under `references/` MUST be
    reachable from SKILL.md through the markdown link graph; chained references
    are allowed. (check:
    `autochecks/authoring.py:rule_5_12_references_reachable`)

13. (rule: STY-1-13, severity: 45) Reference files over 100 lines SHOULD start
    with a table of contents. (check:
    `autochecks/authoring.py:rule_5_13_toc_long_files`)

14. (rule: STY-1-14, severity: 75) Sub-step prose MUST NOT re-narrate what a
    script does internally (algorithm, edge cases, return values), because
    re-narration drifts from the script over time and bloats SKILL.md.
    Exception: inline bash glue inside a fenced block is the implementation
    itself, not narration, and is exempt; the surrounding prose still MUST NOT
    duplicate what the snippet already states, because duplication drifts from
    the snippet over time and bloats SKILL.md.

15. (rule: STY-1-15, severity: 70) Files under `scripts/`, `schemas/`, and
    `templates/` MUST be referenced by SKILL.md, other scripts, prompts, or plan
    code; orphan files MUST be deleted, because they signal incomplete refactors
    or dead code that confuses reviewers. (check:
    `autochecks/authoring.py:rule_5_15_no_orphans`)

## 2. Handle Policy

1. (rule: STY-2-1, severity: 100) Skill files (SKILL.md, references, examples)
   MUST NOT contain other people's aliases, because that exposes PII. (check:
   `autochecks/authoring.py:rule_7_1_no_other_aliases`)

2. (rule: STY-2-2, severity: 95) When a handle is needed in an example, authors
   MUST use their own handle or a generic placeholder (e.g., `userA`, `userB`).

## 3. Degrees of Freedom

1. (rule: STY-3-1, severity: 80) Skills MUST match instruction specificity to
   task fragility per the table below.
2. (rule: STY-3-2, severity: 95) Tasks where errors cause data loss or
   embarrassment MUST use low-freedom instructions: exact commands and
   pre-execution validation.
3. (rule: STY-3-3, severity: 60) Tasks where errors only produce a suboptimal
   draft SHOULD use high-freedom instructions: goals and quality criteria, not
   steps.

| Task type                       | Freedom | Skill pattern                             |
| ------------------------------- | ------- | ----------------------------------------- |
| Fragile (vault write, git push) | Low     | Exact commands, validate before execution |
| Structured (RCA, tests)         | Medium  | SOP with constraints, allow adaptation    |
| Creative (research, review)     | High    | Goals and quality criteria, not steps     |

## 4. Instruction Effectiveness

1. (rule: STY-4-1, severity: 50) When the agent ignores a skill's instructions,
   authors SHOULD shorten the skill rather than adding more text, because
   verbosity dilutes signal.
2. (rule: STY-4-2, severity: 80) Constraints essential to correctness MUST
   appear above the step list of SKILL.md, in `## Rules` (workflow, tool) or
   `## Invariants` (flow), not buried in later steps, because deeper steps are
   read less reliably.
3. (rule: STY-4-3, severity: 80) Deterministic validations (file format,
   schema) MUST be enforced by a script, not a natural-language instruction,
   because code is deterministic and language interpretation is not.
