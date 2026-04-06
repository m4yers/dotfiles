---
name: skill-builder
description: Create or update skills for the Kiro CLI setup. Use when user says "create skill", "new skill", "improve skill", "update skill", or wants to build or modify a skill. Do NOT use for reviewing or auditing skill quality — use skill-reviewer instead.
---

# Skill Builder

Create or update skills for the `~/.kiro/skills/` setup.

## Prerequisites

- Read `references/conventions.md` before any skill creation
  or update
- Read `references/patterns.md` when the skill iterates on
  output or has overlapping triggers

## Skill Directory Layout

```
~/.kiro/skills/
├── dev/           # Build, test, and development workflows
├── diagnostics/   # Cluster diagnostics, log tools, and RCA
└── util/          # Meta-skills, vault, retro, utilities
```

## Parameters

- **operation** (required): "create" or "update"
- **name** (optional for create, required for update):
  kebab-case name
- **category** (optional): `dev`, `diagnostics`, or `util`
  — inferred from purpose if not given

## Workflow: Create

### 1. Gather Requirements

Ask about the skill's purpose, when it triggers, and which
category it belongs to.

**Constraints:**
- You MUST confirm the name is kebab-case
- You MUST determine the category
  (`dev`/`diagnostics`/`util`) — suggest one based on
  purpose
- You MUST get a description (max 1024 chars) that includes
  trigger keywords
- You MUST check existing skill descriptions for
  overlapping triggers because overlaps cause misrouting
- You MUST check existing skills for overlapping
  functionality (same operations, same tools, same
  outputs) because duplicate functionality leads to
  inconsistent behavior and maintenance burden

### 2. Create SKILL.md

Create `~/.kiro/skills/{category}/{name}/SKILL.md`.

**Constraints:**
- You MUST include frontmatter with `name` and `description`
- You MUST use RFC2119 keywords (MUST, SHOULD, MAY) in
  constraints
- You MUST provide "because [reason]" for negative
  constraints
- You MUST keep SKILL.md under 500 lines — move details to
  `references/`
- You MUST include a `
**Constraints:**
- You MUST log activation at the start of the first
  workflow step:
  ```bash
  ~/.kiro/skills/util/skill-analytics/scripts/add-invocation.sh \
    skill-builder TYPE:NAME  # e.g. user:alice, skill:cr-review
  ```

## Completion` section defining
  terminal states (DONE, DONE_WITH_CONCERNS, BLOCKED,
  NEEDS_CONTEXT) with skill-specific criteria per
  `references/conventions.md`
- You MUST ensure the skill logs its activation per
  the `skill-analytics` skill because usage data
  drives skill pruning and improvement
- You SHOULD match the style of existing skills (concise,
  practical, table-heavy for reference data)
- You MUST wrap prose at 80 characters
- You MUST whitespace-format markdown tables (align columns
  with spaces)
- You MUST keep frontmatter fields on single lines (no YAML
  folding)

### 3. Create Reference Files (if needed)

Place in `~/.kiro/skills/{category}/{name}/references/`.

**Constraints:**
- You SHOULD move SQL queries, templates, and detailed
  reference material to separate files
- You MUST keep each reference file focused on one topic

### 4. Create Scripts (if needed)

Place scripts in a `scripts/` subfolder within the skill
directory.

**Constraints:**
- You MUST place scripts in
  `~/.kiro/skills/{category}/{name}/scripts/` because this
  keeps them separate from documentation
- If the script has no external dependencies (stdlib only),
  you MUST run it directly via `python3` because uv adds
  unnecessary overhead
- If the script has external dependencies, you MUST create
  `pyproject.toml` in the `scripts/` directory and use
  `uv run --project
  ~/.kiro/skills/{category}/{name}/scripts` to execute
- You SHOULD use Python 3.7+ compatible syntax because the
  dev desktop may not have newer versions

### 5. Review

**Constraints:**
- You MUST review the skill with the user before considering
  it complete
- You SHOULD suggest testing with a real scenario

### 6. Check Subagent and Prompt Alignment

After creating a skill, check if any subagent or prompt
needs alignment.

**Constraints:**
- You MUST scan `~/.kiro/agents/*.json` for subagents that
  share tools with the new skill
- If a subagent shares tools, you MUST update its prompt to
  read the skill at runtime rather than duplicating rules
  because duplicated rules go stale
- You MUST scan `~/.kiro/prompts/*.md` for prompts that
  cover the same domain as the new skill
- If a prompt overlaps, you MUST update it to reference the
  skill because prompts should defer to skills for tool
  usage rules

### 7. Run Skill Reviewer

After the skill is created and reviewed with the user, run
the `skill-reviewer` skill against it.

**Constraints:**
- You MUST run the skill-reviewer workflow on the newly
  created skill before considering the create workflow
  complete
- You MUST fix any errors reported by skill-reviewer
- You SHOULD fix warnings unless the user declines

## Workflow: Update

### 1. Load Existing Skill

**Constraints:**
- You MUST read the full SKILL.md and any files in
  `references/` before making changes
- You MUST ask what changes are needed if not specified

### 2. Apply Changes

**Constraints:**
- You MUST preserve existing functionality unless explicitly
  changing it
- You MUST NOT remove constraints without user approval
  because they may encode hard-won lessons
