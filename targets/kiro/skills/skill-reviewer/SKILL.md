---
name: skill-reviewer
type: workflow
description: Review and audit skill quality for formatting, conventions, and completeness. Use when user says "review skill", "audit skill", "check skill quality", "analyze skill", or wants to verify a skill meets conventions. Do NOT use for creating or modifying skills — use skill-builder instead.
---

# Skill Reviewer

Audit skills in `~/.kiro/skills/` for quality, formatting, and convention
compliance. Use subagents only for the parallel reference checks in Step
3. For sequential operations (locating, assembling, applying), work
directly.

## Dependencies

- `tiling` — pane layout and activity tracking
- `editor` — show report in editor
- `skill-analytics` — log activation

### Convention sources

Convention reference files live under
`~/.kiro/skills/home/skill-builder/references/`.

### Always applied (all skill types)

- `conventions.md` — general rules
- `model-aware-authoring.md` — model behavior guidance
- `patterns.md` — reusable skill patterns

### Applied by skill type

| Skill type  | Additional reference file        |
|-------------|----------------------------------|
| `interface` | `interface-conventions.md`       |
| `tool`      | `tool-conventions.md`            |
| `workflow`  | `workflow-conventions.md`        |
| `reference` | `reference-conventions.md`       |

### Local references

- `references/manual-checks.md` — cross-skill checks
- `references/subagent-queries.md` — query templates

## Parameters

- **name** (required): kebab-case skill name to review
- **category** (optional): `dev`, `diagnostics`, or `util`
  — searches all if not given

## Workflow

### Step 1: Locate Skill

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
     activity set "skill-reviewer(<name>): Locate Skill"
   ```
2. Log activation:
   ```bash
   ~/.kiro/skills/home/skill-analytics/scripts/add-invocation.sh \
     skill-reviewer <trigger_type>:<trigger_name>
   ```
3. Find the skill directory:
   ```bash
   skill_dir=$(python3 ~/.kiro/skills/home/skill-reviewer/scripts/find-skill.py \
     <name> [<category>])
   ```
4. Determine the applicable reference files based on the
   skill's `type` field from the frontmatter:
   ```bash
   type=$(python3 ~/.kiro/skills/home/skill-reviewer/scripts/extract-type.py \
     <skill-dir>)
   ```
   Build the list: 3 always-applied + 1 type-specific +
   manual-checks.
5. Set up the layout:
   ```bash
   eval "$(~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
     layout build)"
   ```

On completion: proceed to Step 2.

### Step 2: Run Automated Checks

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
     activity set "skill-reviewer(<name>): Run Automated Checks"
   ```
2. Run the automated lint script:
   ```bash
   python3 ~/.kiro/skills/home/skill-reviewer/scripts/skill-lint.py \
     <skill-dir>
   ```
3. Note any false positives from the lint output to pass
   to sub-agents for exclusion.

On completion: proceed to Step 3.

### Step 3: Run Sub-Agent Checks

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
     activity set "skill-reviewer(<name>): Run Sub-Agent Checks"
   ```
2. Read `references/subagent-queries.md` for the query
   templates.
3. Spawn sub-agents in parallel using the query template
   from `references/subagent-queries.md` — one per
   applicable reference file (3 always-applied + 1
   type-specific + `references/manual-checks.md`). Use
   `agent_name: trusted` (grants file-read access
   to skill directories) for every sub-agent.
   The template is the same for all; only the reference
   path differs.
4. Collect sub-agent results. Each sub-agent returns
   exactly one of: a violations list, `NO_FINDINGS`, or
   `ERROR: <reason>`. For each sub-agent whose output
   begins with `ERROR:` (or is empty/malformed):
   a. Retry once with the same query.
   b. If the retry also returns `ERROR:` (or empty),
      fall back to an inline check: read the reference
      file yourself and walk the skill against each rule.
      Mark any findings produced via fallback with
      `(fallback)` in the description so downstream
      reviewers know the sub-agent dispatch failed.
   Sub-agents that returned a violations list or
   `NO_FINDINGS` are terminal — do NOT retry them.
5. Deduplicate violations that appear in multiple
   results. Match on file:line and message similarity.
   Do not revisit deduplication decisions.

On completion: proceed to Step 4.

### Step 4: Assemble Report

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
     activity set "skill-reviewer(<name>): Assemble Report"
   ```
2. Merge lint output with sub-agent findings. Silently
   exclude lint false positives — only include findings
   that are actionable and fixable.
3. Create the report file:
   ```bash
   python3 ~/.kiro/skills/home/skill-reviewer/scripts/report-writer.py \
     create /tmp/skill-review-<name>.md <name> <category> <type>
   ```
4. Append each finding using the `error`, `warning`,
   or `info` command:
   ```bash
   python3 ~/.kiro/skills/home/skill-reviewer/scripts/report-writer.py \
     <severity> /tmp/skill-review-<name>.md \
     "<title>" "<file>:<line>" "<description>" "<fix>"
   ```
   Every finding MUST include a suggested fix.
5. Format the report:
   ```bash
   python3 ~/.kiro/skills/home/skill-reviewer/scripts/report-writer.py \
     format /tmp/skill-review-<name>.md
   ```

On completion: proceed to Step 5.

### Step 5: Show Report

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
     activity set "skill-reviewer(<name>): Show Report"
   ```
2. Show the report in the editor:
   ```bash
   ~/.kiro/skills/home/editor/scripts/run-editor.sh \
     show file /tmp/skill-review-<name>.md
   ```
3. STOP and wait for the user to review the report and
   indicate which findings to implement.

On user selection: proceed to Step 6.

### Step 6: Apply Fixes

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
     activity set "skill-reviewer(<name>): Apply Fixes"
   ```
2. For each finding the user accepts, apply the fix.
3. After applying, mark the finding with ✅ in the report
   and reload in the editor:
   ```bash
   python3 ~/.kiro/skills/home/skill-reviewer/scripts/report-writer.py \
     strikeout /tmp/skill-review-<name>.md <finding_number>
   ~/.kiro/skills/home/editor/scripts/run-editor.sh \
     show file /tmp/skill-review-<name>.md
   ```
4. For each finding the user explicitly rejects, mark it
   declined with their reason:
   ```bash
   python3 ~/.kiro/skills/home/skill-reviewer/scripts/report-writer.py \
     decline /tmp/skill-review-<name>.md <finding_number> \
     --reason "<user's reason>"
   ```
   Findings the user did not mention remain open — never
   mark them declined. Silence is not rejection.
5. Repeat from sub-step 2 until all findings are
   addressed or skipped.

On completion: proceed to Step 7.

### Step 7: Verify Fixes

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
     activity set "skill-reviewer(<name>): Verify Fixes"
   ```
2. Re-run the automated lint script:
   ```bash
   python3 ~/.kiro/skills/home/skill-reviewer/scripts/skill-lint.py \
     <skill-dir>
   ```
3. If new errors appear and this is the 3rd fix-verify
   cycle, STOP and report remaining errors to the user.
   Limit: 3 cycles max between Step 6 and Step 7
   because unbounded loops risk infinite fix-break
   cycles. Otherwise return to Step 6.

On completion: proceed to Step 8.

### Step 8: Finalize & Set Done

1. Set tiling activity to Done:
   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
     activity set "skill-reviewer(<name>): Done"
   ```

## Completion

| Status               | Criteria                              |
|----------------------|---------------------------------------|
| `DONE`               | All findings addressed or skipped     |
| `DONE_WITH_CONCERNS` | Checks run, some files unreadable     |
| `BLOCKED`            | Skill directory not found             |
| `NEEDS_CONTEXT`      | Skill name not provided               |

- You MUST stop after 3 failed attempts to locate or read
  the skill and report status BLOCKED with what was tried
