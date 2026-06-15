# Skill Authoring

Rules for skill authors. Read when creating or updating skills.

## Contents

- [1. Directory Structure](#1-directory-structure)
- [2. Categories](#2-categories)
- [3. Frontmatter](#3-frontmatter)
- [4. Skill Types](#4-skill-types)
- [5. Style Guide](#5-style-guide)
- [6. Completion Status](#6-completion-status)
- [7. Handle Policy](#7-handle-policy)
- [8. Degrees of Freedom](#8-degrees-of-freedom)
- [9. Trigger Phrase Hygiene](#9-trigger-phrase-hygiene)
- [10. Instruction Effectiveness](#10-instruction-effectiveness)
- [11. See Also](#11-see-also)

## 1. Directory Structure

1. Each skill MUST live under `~/.kiro/skills/{category}/{skill-name}/`.
2. `SKILL.md` MUST exist at the skill root.
3. Reference docs SHOULD live in `references/`. (check:
   `autochecks/authoring.py:rule_1_3_md_under_references`)
4. JSON schemas MUST live in top-level `schemas/`, not under `references/`,
   because producer and consumer code MUST resolve them without crossing
   directories. (check: `autochecks/authoring.py:rule_1_4_schemas_top_level`)
5. Files with placeholders or used as starting points (artifact templates,
   example outputs, stage templates) MUST live under `templates/`.
6. Executable scripts MUST live under `scripts/`. (check:
   `autochecks/authoring.py:rule_1_6_scripts_directory`)

```
~/.kiro/skills/
├── dev/           # Build, test, and development workflows
├── diagnostics/   # Cluster diagnostics, log tools, and RCA
└── util/          # Meta-skills, vault, retro, utilities
```

```
~/.kiro/skills/{category}/{skill-name}/
├── SKILL.md              # Required — main skill definition
├── references/           # Optional — reference docs, guides
├── schemas/              # Optional — JSON schemas for outputs
├── templates/            # Optional — fill-in templates
└── scripts/              # Optional — executable scripts
```

## 2. Categories

1. Skills MUST be placed in one of three categories: `dev/`, `diagnostics/`,
   `util/`.
2. `dev/` is for build, test, and development workflows.
3. `diagnostics/` is for cluster diagnostics, log tools, and root-cause
   analysis.
4. `util/` is for meta-skills, vault, retro, and other utilities.

Decision guide:

- Builds or tests code → `dev/`
- Connects to a live cluster, fetches logs, investigates issues → `diagnostics/`
- Manages the Kiro setup → `util/`

## 3. Frontmatter

1. Frontmatter MUST include `name`, `type`, and `description`.

2. `name` MUST be 1-64 chars using only lowercase letters, digits, and hyphens.
   (check: `autochecks/authoring.py:rule_3_2_name_format`)

3. `type` MUST be one of `interface`, `tool`, `workflow`, `reference`. (check:
   `autochecks/authoring.py:rule_3_3_type_values`)

4. `description` MUST be ≤1024 chars and MUST include trigger keywords for
   routing. (check: `autochecks/authoring.py:rule_3_4_description_length`)

5. `description` MUST be written in third person ("Extracts text from PDFs"),
   not first or second person. (check: `autochecks/authoring.py:rule_3_5_description_person`)

6. `name` and `description` MUST each stay on a single line, regardless of
   length.

```yaml
---
name: skill-name
type: interface
description: What it does. Use when [trigger phrases].
---
```

## 4. Skill Types

1. `interface` skills MUST provide an API consumed by other skills and MUST NOT
   have user-facing steps, because they are libraries, not workflows.
2. `tool` skills MUST be a fixed sequence of indivisible steps with no iteration
   or user interaction mid-execution.
3. `workflow` skills MUST be multi-step, often interactive; their steps MAY
   contain sub-steps and MAY loop.
4. `reference` skills MUST be passive rule sets loaded as context when
   triggered, with no invocation, API, or steps.
5. Only `workflow` skills SHALL contain numbered steps; a step contains
   sub-steps that are single indivisible actions.

| Type        | Examples                 |
| ----------- | ------------------------ |
| `interface` | tiling, editor, template |
| `tool`      | cr-tree, cr-push         |
| `workflow`  | cr-review, make, rca     |
| `reference` | writing-cpp, obsidian    |

## 5. Style Guide

01. Reference data SHOULD use tables, not prose, because tables are denser for
    scannable lookup.

02. Aliases and primary commands MUST appear up front in SKILL.md.

03. Skills MUST NOT have a README.md, because SKILL.md is the single source of
    truth. (check: `autochecks/authoring.py:rule_5_3_no_readme`)

04. Constraints MUST use RFC 2119 keywords (MUST, SHOULD, MAY, MUST NOT) and
    negative constraints MUST carry a "because \[reason\]" clause. (check:
    `autochecks/authoring.py:rule_5_4_constraints_form`)

05. SQL queries MUST live in `references/`, because keeping them out of SKILL.md
    preserves scannability.

06. Tables MUST be whitespace-aligned for readability.

07. Prose lines MUST fill to at least 75 chars before wrapping at 80; tables MAY
    extend to 100 chars. (check: `autochecks/authoring.py:rule_5_7_line_widths`)

08. Constraints SHOULD be written in positive form; MUST NOT is reserved for
    hard safety boundaries, because reserving MUST NOT preserves its weight
    when authors reach for it on a genuine boundary.

09. RFC 2119 keywords MUST stand alone; authors MUST NOT prefix them with
    "CRITICAL", "IMPORTANT", "ALWAYS", or exclamation marks, because the model
    overtriggers on amplified language. (check: `autochecks/authoring.py:rule_5_9_emphasis_stacking`)

10. Authors MUST challenge every token before adding it: ask whether the model
    already knows what is being explained.

11. When multiple approaches exist, skills MUST recommend a single default with
    an escape hatch for edge cases.

12. Every file under `references/` MUST be reachable from SKILL.md through the
    markdown link graph; chained references are allowed. (check:
    `autochecks/authoring.py:rule_5_12_references_reachable`)

13. Reference files over 100 lines SHOULD start with a table of contents.
    (check: `autochecks/authoring.py:rule_5_13_toc_long_files`)

14. Sub-step prose MUST NOT re-narrate what a script does internally (algorithm,
    edge cases, return values), because re-narration drifts from the script over
    time and bloats SKILL.md.

15. Files under `scripts/`, `schemas/`, and `templates/` MUST be referenced by
    SKILL.md, other scripts, prompts, or plan code; orphan files MUST be
    deleted, because they signal incomplete refactors or dead code that confuses
    reviewers. (check: `autochecks/authoring.py:rule_5_15_no_orphans`)

## 6. Completion Status

1. Every skill MUST end with a `## Completion` section defining terminal states.
   (check: `autochecks/authoring.py:rule_6_1_completion_section`)

2. The section MUST use exactly four statuses: `DONE`, `DONE_WITH_CONCERNS`,
   `BLOCKED`, `NEEDS_CONTEXT`. (check: `autochecks/authoring.py:rule_6_2_completion_statuses`)

3. `DONE_WITH_CONCERNS` MUST be used only for workflow-level problems (sub-agent
   returned empty, verification skipped because a tool was unavailable, partial
   failure tolerated) that warranted a retro but did not stop the workflow.

4. `DONE_WITH_CONCERNS` MUST NOT be used for outcome-level caveats the user
   consciously accepted (audit passed with overrides, user kept a flagged
   finding), because those belong in a clean `DONE` report.

5. The `DONE` row MUST state concrete evidence (e.g., "report saved", "drafts
   published"), not generic "task completed".

6. Skills involving iteration or investigation MUST include an escalation rule —
   e.g., "MUST stop after 3 failed attempts and report BLOCKED with what was
   tried".

```markdown
## Completion

| Status               | Criteria                            |
|----------------------|-------------------------------------|
| `DONE`               | Review report saved, drafts posted  |
| `DONE_WITH_CONCERNS` | Report saved, some files unreadable |
| `BLOCKED`            | CR checkout failed or no diff found |
| `NEEDS_CONTEXT`      | CR URL not provided                 |
```

## 7. Handle Policy

1. Skill files (SKILL.md, references, examples) MUST NOT contain other people's
   aliases, because that exposes PII. (check: `autochecks/authoring.py:rule_7_1_no_other_aliases`)

2. When a handle is needed in an example, authors MUST use their own handle or a
   generic placeholder (e.g., `userA`, `userB`).

## 8. Degrees of Freedom

1. Skills MUST match instruction specificity to task fragility per the table
   below.
2. Tasks where errors cause data loss or embarrassment MUST use low-freedom
   instructions: exact commands and pre-execution validation.
3. Tasks where errors only produce a suboptimal draft SHOULD use high-freedom
   instructions: goals and quality criteria, not steps.

| Task type                       | Freedom | Skill pattern                             |
| ------------------------------- | ------- | ----------------------------------------- |
| Fragile (vault write, git push) | Low     | Exact commands, validate before execution |
| Structured (RCA, tests)         | Medium  | SOP with constraints, allow adaptation    |
| Creative (research, review)     | High    | Goals and quality criteria, not steps     |

## 9. Trigger Phrase Hygiene

1. New or updated skill descriptions MUST be checked against other skills'
   descriptions for overlapping trigger words.
2. Each skill SHOULD claim at least 2-3 unique trigger phrases that no other
   skill uses.
3. When two skills share a trigger domain, both descriptions MUST state the
   routing criteria explicitly.
4. When scope overlaps, descriptions MUST include a negative trigger — e.g., "Do
   NOT use for X (use Y skill instead)" — as in debug-symbolize vs fast-debug,
   or owls/fleet-sweep vs rca.

## 10. Instruction Effectiveness

1. When the agent ignores a skill's instructions, authors SHOULD shorten the
   skill rather than adding more text, because verbosity dilutes signal.
2. Constraints essential to correctness MUST appear at the top of SKILL.md, not
   buried in later steps, because deeper steps are read less reliably.
3. Deterministic validations (file format, schema) MUST be enforced by a script,
   not a natural-language instruction, because code is deterministic and
   language interpretation is not.

## 11. See Also

- `script-conventions.md` — script APIs, oracles, Python packaging, invocation
  paths, Jinja rendering, magic constants, stdlib first, producer/consumer
  contracts.
- `model-awareness.md` — model behaviour tendencies and token budget.
- `secure-llm-conventions.md` — when sub-agent prompts must inject the
  secure-llm security frame for external content.
- `interface-conventions.md`, `tool-conventions.md`, `workflow-conventions.md`,
  `reference-conventions.md` — per-type structure rules.
