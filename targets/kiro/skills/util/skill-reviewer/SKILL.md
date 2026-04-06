---
name: skill-reviewer
description: Review and audit skill quality for formatting, conventions, and completeness. Use when user says "review skill", "audit skill", "check skill quality", "analyze skill", or wants to verify a skill meets conventions. Do NOT use for creating or modifying skills — use skill-builder instead.
---

# Skill Reviewer

Audit skills in `~/.kiro/skills/` for quality, formatting,
and convention compliance.

## Prerequisites

- Read
  `~/.kiro/skills/util/skill-builder/references/conventions.md`
  for the rules being checked

## Parameters

- **name** (required): kebab-case skill name to review
- **category** (optional): `dev`, `diagnostics`, or `util`
  — searches all if not given

## Workflow

### 1. Load Skill

Read SKILL.md and all files in `references/` and `scripts/`.

**Constraints:**
- You MUST read every file in the skill directory before
  reporting because partial review misses issues
- You MUST locate the skill by searching
  `~/.kiro/skills/*/` if category is not given

### 2. Check Quality

Run these checks against SKILL.md and all reference files:

| Check                        | Rule                                  |
|------------------------------|---------------------------------------|
| Frontmatter fields           | Single lines, no YAML folding         |
| `name` field                 | 1-64 chars, lowercase, hyphens only   |
| `description` field          | ≤ 1024 chars, has trigger keywords    |
| Trigger phrase uniqueness    | No overlap with other skill triggers  |
| Functionality uniqueness     | No overlap in operations/tools/output |
| Negative trigger phrases     | Present if scope overlaps with others |
| RFC2119 keywords             | Constraints use MUST/SHOULD/MAY       |
| Negative constraint reasons  | "because [reason]" present            |
| Prose line width             | Fills to ≥ 75 chars, wraps at 80      |
| Table formatting             | Whitespace-aligned, ≤ 100 chars wide  |
| SKILL.md length              | Under 500 lines                       |
| Reference file focus         | Each file covers one topic            |
| Script location              | In `scripts/` subfolder               |
| Handle policy                | No other people's aliases             |
| Completion status section    | Has `
**Constraints:**
- You MUST log activation at the start of the first
  workflow step:
  ```bash
  ~/.kiro/skills/util/skill-analytics/scripts/add-invocation.sh \
    skill-reviewer TYPE:NAME  # e.g. user:alice, skill:cr-review
  ```

## Completion` with status table |
| Analytics logging            | Logs activation per skill-analytics   |

**Constraints:**
- You MUST check all items in the table above
- You SHOULD identify missing error handling or edge cases
  in workflows
- You SHOULD flag constraints that lack "because [reason]"
  even if they are positive constraints, as a suggestion

### 3. Report

Present findings grouped by severity:

- **Errors**: Convention violations that MUST be fixed
- **Warnings**: Issues that SHOULD be fixed
- **Suggestions**: Optional improvements

**Constraints:**
- You MUST show the specific line or section for each
  finding
- You MUST ask which findings to implement rather than
  auto-fixing because the user may disagree with some
