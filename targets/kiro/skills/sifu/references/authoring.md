# Skill Authoring

**Code:** AUT
**Applies:** always

Structural rules for skills: layout, categories, frontmatter, and types. Read
when creating or updating skills.

## Contents

- [1. Directory Structure](#1-directory-structure)
- [2. Categories](#2-categories)
- [3. Frontmatter](#3-frontmatter)
- [4. Skill Types](#4-skill-types)
- [5. See Also](#5-see-also)

## 1. Directory Structure

1. (rule: AUT-1-1, severity: 90) Each skill MUST live under
   `~/.kiro/skills/{category}/{skill-name}/`.
2. (rule: AUT-1-2, severity: 90) `SKILL.md` MUST exist at the skill root.
3. (rule: AUT-1-3, severity: 50) Reference docs SHOULD live in `references/`.
   (check: `autochecks/authoring.py:rule_1_3_md_under_references`)
4. (rule: AUT-1-4, severity: 70) Shapes used by more than one task or script
   MUST live in top-level `schemas/` and be pulled in via relative `$ref`; a
   shape used by one task stays inline in that task's `io.yaml`. Schemas MUST
   NOT live under `references/`, because producer and consumer code MUST
   resolve them without crossing directories. (check:
   `autochecks/authoring.py:rule_1_4_schemas_top_level`)
5. (rule: AUT-1-5, severity: 70) Files with placeholders or used as starting
   points (artifact templates, example outputs, stage templates) MUST live under
   `templates/`.
6. (rule: AUT-1-6, severity: 70) Executable scripts MUST live under `scripts/`.
   (check: `autochecks/authoring.py:rule_1_6_scripts_directory`)
7. (rule: AUT-1-7, severity: 90) Loomv2 task folders MUST live under a loom root
   at the skill root (`loom/`, plus `loom-<name>/` for subgraph roots), because
   loomv2 resolves `{% raw %}{% include %}{% endraw %}` from
   `<task>/../../references/`.

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
├── schemas/              # Optional — shared schemas ($ref targets)
├── templates/            # Optional — fill-in templates
├── loom/                 # Workflow — loomv2 graph(s) + task folders
└── scripts/              # Optional — executable scripts
```

## 2. Categories

1. (rule: AUT-2-1, severity: 70) Skills MUST be placed in one of four
   categories: `home/`, `dev/`, `diagnostics/`, `util/`.
2. (rule: AUT-2-2, severity: 10) `home/` is for personal, work-independent
   Kiro-setup skills (sifu, loom, tiling, editor, retro).
3. (rule: AUT-2-3, severity: 10) `dev/` is for build, test, and development
   workflows.
4. (rule: AUT-2-4, severity: 10) `diagnostics/` is for cluster diagnostics, log
   tools, and root-cause analysis.
5. (rule: AUT-2-5, severity: 10) `util/` is for work meta-skills, vault, and
   other utilities.

## 3. Frontmatter

1. (rule: AUT-3-1, severity: 90) Frontmatter MUST include `name`, `type`, and
   `description`.

2. (rule: AUT-3-2, severity: 90) `name` MUST be 1-64 chars using only lowercase
   letters, digits, and hyphens. (check:
   `autochecks/authoring.py:rule_3_2_name_format`)

3. (rule: AUT-3-3, severity: 90) `type` MUST be one of `interface`, `tool`,
   `workflow`, `reference`, `flow`. (check:
   `autochecks/authoring.py:rule_3_3_type_values`)

4. (rule: AUT-3-4, severity: 80) `description` MUST be ≤1024 chars and MUST
   include trigger keywords for routing. (check:
   `autochecks/authoring.py:rule_3_4_description_length`)

5. (rule: AUT-3-5, severity: 65) `description` MUST be written in third person
   ("Extracts text from PDFs"), not first or second person. (check:
   `autochecks/authoring.py:rule_3_5_description_person`)

6. (rule: AUT-3-6, severity: 90) `name` and `description` MUST each stay on a
   single line, regardless of length.

```yaml
---
name: skill-name
type: interface
description: What it does. Use when [trigger phrases].
---
```

## 4. Skill Types

1. (rule: AUT-4-1, severity: 80) `interface` skills MUST provide an API consumed
   by other skills and MUST NOT have user-facing steps, because they are
   libraries, not workflows.
2. (rule: AUT-4-2, severity: 80) `tool` skills MUST be a fixed sequence of
   indivisible steps with no iteration or user interaction mid-execution.
3. (rule: AUT-4-3, severity: 80) `workflow` skills MUST be multi-step, often
   interactive, and driven by a loomv2 graph; their steps MAY contain sub-steps
   and MAY loop.
4. (rule: AUT-4-4, severity: 80) `reference` skills MUST be passive rule sets
   loaded as context when triggered, with no invocation, API, or steps.
5. (rule: AUT-4-5, severity: 80) `flow` skills MUST be prose steps in SKILL.md
   that the agent MAY adapt, reorder, or extend at the operator's request, with
   no loom graph; see `flow-conventions.md`.
6. (rule: AUT-4-6, severity: 80) Only `tool`, `workflow`, and `flow` skills
   SHALL contain numbered steps; a `tool` step is itself one indivisible
   action, and a `workflow` or `flow` step contains sub-steps that are single
   indivisible actions.

| Type        | Examples                 |
| ----------- | ------------------------ |
| `interface` | tiling, editor, template |
| `tool`      | cr-tree, cr-push         |
| `workflow`  | sifu, project-design     |
| `flow`      | live-journal             |
| `reference` | writing-cpp, obsidian    |

## 5. See Also

- `rule-codes.md` — rule codes, severity formula, review bands, topics.
- `style.md` — style guide, handle policy, degrees of freedom,
  instruction effectiveness.
- `completion.md` — completion statuses.
- `triggers.md` — trigger phrase hygiene.
- `script-conventions.md` — script APIs, oracles, packaging, contracts.
- `model-awareness.md` — model behaviour tendencies and token budget.
- `secure-llm-conventions.md` — security frame for external content.
- `interface-conventions.md`, `tool-conventions.md`, `workflow-conventions.md`,
  `flow-conventions.md`, `reference-conventions.md` — per-type structure
  rules.
