---
name: skill-builder
type: workflow
description: Creates or updates skills for the Kiro CLI setup. Use when user says "create skill", "new skill", "improve skill", "update skill", or wants to build or modify a skill. Do NOT use for reviewing or auditing skill quality — use skill-reviewer instead.
---

# Skill Builder

Create or update skills for the `~/.kiro/skills/` setup.

## Dependencies

- `tiling` — pane layout and activity tracking
- `skill-analytics` — activation logging
- `skill-reviewer` — post-creation quality check (Step 7)

## Parameters

- **operation** (required): "create" or "update"
- **name** (optional for create, required for update):
  kebab-case name
- **category** (optional): `dev`, `diagnostics`, or `util`
  — inferred from purpose if not given

## Workflow

If operation is "create", proceed to Step 1. If operation
is "update", proceed to Step 8.

### Step 1: Gather Requirements

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/util/tiling/scripts/run-ttm.sh \
     activity set "skill-builder(<name>): Gather Requirements"
   ```
2. Log activation:
   ```bash
   ~/.kiro/skills/util/skill-analytics/scripts/add-invocation.sh \
     skill-builder TRIGGER_TYPE:TRIGGER_NAME
   ```
3. Ask the user about the skill's purpose, when it
   triggers, and which category it belongs to.

**Constraints:**
- You MUST validate the name is kebab-case:
  ```bash
  echo "<name>" | grep -qE '^[a-z][a-z0-9-]*$' \
    || echo "ERROR: name must be kebab-case"
  ```
- You MUST determine the category
  (`dev`/`diagnostics`/`util`) — suggest one based on
  purpose
- You MUST determine the type
  (`interface`/`tool`/`workflow`/`reference`) — suggest
  one based on purpose per `references/conventions.md`
- You MUST get a description (max 1024 chars) that includes
  trigger keywords
- You MUST check existing skill descriptions for
  overlapping triggers because overlaps cause misrouting:
  ```bash
  python3 ~/.kiro/skills/util/skill-builder/scripts/check-overlaps.py \
    <skill-name> [category]
  ```
- You MUST check existing skills for overlapping
  functionality (same operations, same tools, same
  outputs). Two skills overlap if they invoke the same
  script or tool to produce the same artifact — shared
  input sources alone do not count as overlap.
- You SHOULD ultrathink about whether the new skill's
  scope overlaps with existing skills before running the
  overlap checker because subtle overlaps cause router
  misfires that are hard to debug later
- If scope overlaps with another skill, you MUST add
  negative trigger phrases to the description ("Do NOT use
  for X — use Y instead") because the router needs explicit
  disambiguation

On completion: proceed to Step 2.

### Step 2: Create SKILL.md

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/util/tiling/scripts/run-ttm.sh \
     activity set "skill-builder(<name>): Create SKILL.md"
   ```
2. Create `~/.kiro/skills/{category}/{name}/SKILL.md`.
3. Read the applicable reference files for the skill type
   — these reads are independent, make them in parallel:
   - Always: `references/conventions.md` and
     `references/model-aware-authoring.md`
   - By type: `references/{type}-conventions.md`
   - If iterative: `references/patterns.md`

**Constraints:**
- You MUST only create content that is directly requested
  or clearly necessary — do not add abstractions, helpers,
  or defensive code for hypothetical scenarios
- You MUST follow the section order prescribed in the
  type-specific convention file because skill-reviewer
  checks section order and flags violations
- For workflow skills: you MUST follow the step rules in
  workflow-conventions.md — activity tracking as first
  sub-step, max 5 sub-steps per step, descriptive step
  names, explicit transitions between steps, and user
  interaction points using prescribed phrasing ("STOP and
  wait for user", "Ask the user", "On approval: proceed
  to Step N")
- For interface skills: you MUST include Invocation, API,
  and Commands sections per interface-conventions.md
- For tool skills: you MUST include a Steps section with
  numbered indivisible actions per tool-conventions.md
- For reference skills: the description MUST use "MUST load
  whenever" phrasing per reference-conventions.md
- You MUST include frontmatter with `name`, `type`, and
  `description`
- You MUST use RFC2119 keywords (MUST, SHOULD, MAY) in
  constraints
- You MUST provide "because [reason]" for negative
  constraints
- You MUST keep SKILL.md under 500 lines — move details to
  `references/`
- You MUST include a `## Completion` section defining
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
- You MUST identify verifiable outcomes in each step and
  add oracle sub-steps per `references/conventions.md`
  "Executable Oracles" because unverified outcomes are
  degrees of freedom the LLM will get wrong
- You SHOULD prefer positive framing ("Always validate
  input") over negation ("Do NOT skip validation") —
  reserve MUST NOT for hard safety boundaries only
- You SHOULD avoid emphasis stacking — plain RFC2119
  keywords without CRITICAL/IMPORTANT/ALWAYS prefixes
- Deterministic repeatable actions MUST be scripts, not
  prose instructions the agent re-interprets each time
- If success criteria reference measurable outcomes (test
  count, coverage), add anti-gaming guards because the
  model may trivially satisfy metrics
- Research and investigation steps SHOULD include thinking
  cues ("ultrathink") per model-aware-authoring.md
- Steps with independent tool calls SHOULD note when they
  can be parallelized
- Iterative skills SHOULD include a circuit breaker (3-
  attempt limit) per patterns.md
- Prose lines MUST fill to at least 75 chars before
  wrapping unless the sentence naturally ends shorter
- You MUST NOT include other people's aliases in skill
  files because it exposes PII — use generic placeholders
4. Verify the created SKILL.md:
   ```bash
   python3 ~/.kiro/skills/util/skill-reviewer/scripts/skill-lint.py \
     ~/.kiro/skills/{category}/{name}
   ```

On completion: proceed to Step 3.

### Step 3: Create Reference Files

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/util/tiling/scripts/run-ttm.sh \
     activity set "skill-builder(<name>): Create Reference Files"
   ```
2. Place reference files in
   `~/.kiro/skills/{category}/{name}/references/`.

**Constraints:**
- You SHOULD move SQL queries, templates, and detailed
  reference material to separate files
- You MUST keep each reference file focused on one topic
- Reference files SHOULD stay under 300 lines because
  larger files reduce model attention on key rules
- Reference files over 100 lines SHOULD start with a table
  of contents

On completion: proceed to Step 4.

### Step 4: Create Scripts

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/util/tiling/scripts/run-ttm.sh \
     activity set "skill-builder(<name>): Create Scripts"
   ```
2. Place scripts in a `scripts/` subfolder within the skill
   directory.

**Constraints:**
- You MUST place scripts in
  `~/.kiro/skills/{category}/{name}/scripts/` because this
  keeps them separate from documentation
- If the script has no external dependencies (stdlib only),
  you MUST run it directly via `python3` because uv adds
  unnecessary overhead
- If the script has external dependencies, you MUST create
  `pyproject.toml` in the `scripts/` directory and a shim
  `.sh` script that wraps the `uv run` invocation per
  `references/conventions.md` because callers should not
  know about uv
- You SHOULD use Python 3.7+ compatible syntax because the
  dev desktop may not have newer versions
- You MUST include a module docstring in Python scripts
  and a header comment in shell scripts because scripts
  without self-documentation are not queryable by the LLM
- You MUST add `--help` support (argparse or manual) to
  any script that accepts arguments because the LLM needs
  to discover the interface at runtime
- You MUST comment every hardcoded value in scripts because
  uncommented magic constants are flagged by skill-reviewer
- You MUST use Python stdlib modules and standard Linux
  tools instead of reimplementing their functionality
  because custom reimplementations add maintenance burden

On completion: proceed to Step 5.

### Step 5: Review

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/util/tiling/scripts/run-ttm.sh \
     activity set "skill-builder(<name>): Review"
   ```
2. STOP and wait for user to review the skill.

**Constraints:**
- You MUST review the skill with the user before
  considering it complete because automated checks miss
  domain-specific issues only the user can catch
- You SHOULD suggest testing with a real scenario

On completion: proceed to Step 6.

### Step 6: Check Subagent and Prompt Alignment

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/util/tiling/scripts/run-ttm.sh \
     activity set "skill-builder(<name>): Check Subagent and Prompt Alignment"
   ```
2. List agent tool sets and prompt domains:
   ```bash
   python3 ~/.kiro/skills/util/skill-builder/scripts/check-alignment.py
   ```
3. Scan the output for subagents that share tools with the
   new skill. If a subagent shares tools, update its prompt
   to read the skill at runtime rather than duplicating
   rules.
4. Scan the output for prompts that cover the same domain
   as the new skill. If a prompt overlaps, update it to
   reference the skill.

**Constraints:**
- Ultrathink about whether the subagent or prompt truly
  overlaps before modifying it
- If a subagent shares tools, you MUST update its prompt to
  read the skill at runtime rather than duplicating rules
  because duplicated rules go stale
- If a prompt overlaps, you MUST update it to reference the
  skill because prompts should defer to skills for tool
  usage rules

On completion: proceed to Step 7.

### Step 7: Run Skill Reviewer

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/util/tiling/scripts/run-ttm.sh \
     activity set "skill-builder(<name>): Run Skill Reviewer"
   ```
2. Run the `skill-reviewer` skill against the new skill.

**Constraints:**
- You MUST run the skill-reviewer workflow on the newly
  created skill before considering the create workflow
  complete because unreviewed skills accumulate quality
  debt
- You MUST fix any errors reported by skill-reviewer
- You SHOULD fix warnings unless the user declines
- You MUST stop after 3 fix-then-rerun cycles and report
  DONE_WITH_CONCERNS with remaining issues listed

On completion: set tiling activity to done and report
status:
```bash
~/.kiro/skills/util/tiling/scripts/run-ttm.sh \
  activity set "skill-builder(<name>): Done"
```

### Step 8: Load Existing Skill

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/util/tiling/scripts/run-ttm.sh \
     activity set "skill-builder(<name>): Load Existing Skill"
   ```
2. Log activation:
   ```bash
   ~/.kiro/skills/util/skill-analytics/scripts/add-invocation.sh \
     skill-builder TRIGGER_TYPE:TRIGGER_NAME
   ```
3. Read the full SKILL.md and all files in `references/`
   — these reads are independent, make them in parallel.

**Constraints:**
- You MUST read the full SKILL.md and any files in
  `references/` before making changes because partial
  reads risk breaking existing functionality
- STOP and ask the user what changes are needed if not
  specified

On completion: proceed to Step 9.

### Step 9: Apply Changes

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/util/tiling/scripts/run-ttm.sh \
     activity set "skill-builder(<name>): Apply Changes"
   ```
2. Apply the requested changes.

**Constraints:**
- You MUST preserve existing functionality unless explicitly
  changing it because removing functionality silently
  breaks callers that depend on it
- You MUST NOT remove constraints without user approval
  because they may encode hard-won lessons

On completion: set tiling activity to done and report
status:
```bash
~/.kiro/skills/util/tiling/scripts/run-ttm.sh \
  activity set "skill-builder(<name>): Done"
```

## Completion

| Status               | Criteria                            |
|----------------------|-------------------------------------|
| `DONE`               | Skill created/updated, reviewer ran |
| `DONE_WITH_CONCERNS` | Created but reviewer found warnings |
| `BLOCKED`            | Cannot create skill directory       |
| `NEEDS_CONTEXT`      | Skill purpose or name not specified |

- You MUST stop after 3 failed attempts to create the
  skill directory and report status BLOCKED with what
  was tried
