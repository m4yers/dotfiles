---
name: retro
description: Analyze the current session for learnings and encode them into skills, steering, or prompts. Use when the user says "retro", "retrospective", "what did we learn", or "session review". Do NOT use for tracking learnings mid-session — that happens automatically via the session-retro-tracker steering file.
---

# Session Retrospective

Review learnings collected during this session and encode
them into skills, steering, or prompts.

Learnings are tracked per the `session-retro-tracker` steering file and stored
as JSON files in `~/.kiro/retro/pending/`.

## Categories

| Area       | Action   | Write method |
|------------|----------|--------------|
| skill      | update   | Direct write |
| skill      | new      | Direct write |
| steering   | update   | Direct write |
| steering   | new      | Direct write |
| prompt     | update   | Direct write |
| prompt     | new      | Direct write |

## Severity

- **high** — user corrected the agent, wasted >2 min, factual error, or data
  loss risk
- **medium** — missing capability user worked around, wrong default, repeated
  friction in this session
- **low** — minor optimization, documentation of already-correct behavior

## Workflow

### Step 1 — Load Learnings

Read all JSON files from `~/.kiro/retro/pending/`.

### Step 2 — Pre-check

Before presenting findings:

- For skill/update: read the target SKILL.md to verify
  the suggestion isn't already encoded
- For steering/update: read the target steering file
  to verify
- Drop any findings that are already covered

### Step 3 — Dashboard

Run the table script to display findings:
```bash
~/.kiro/skills/workflows/retro/scripts/retro-table.sh
```

Show the script output as-is — do NOT reformat or duplicate
it as a separate table. Just append the prompt:

```
→ Pick a number to start, or "all" to go through each
```

Severity icons: ● high | ◐ medium | ○ low

If zero high/medium findings: "No actionable learnings from this session." and
stop.

### Step 4 — Process One at a Time

For each selected finding, show:

```
## [#N] Finding title
**Area:** skill | **Action:** update | **Severity:** high
**Target:** owls
**Path:** ~/.kiro/skills/tools/example-skill/SKILL.md
**Evidence:** <what happened in the conversation>
**Proposed change:** <concrete diff or description>
```

Then ask: **apply / skip?**

After each apply or skip, delete the backing JSON file,
check for any new retro files added during this session,
and re-display the dashboard with only the remaining
pending items.

**Apply rules by area/action:**

- skill/update: Read the full target SKILL.md, apply the change with
  `fs_write`, `str_replace` or `append`.
- skill/new: Create `~/.kiro/skills/<category>/<name>/SKILL.md` following
  the conventions in
  `~/.kiro/skills/workflows/skill-builder/references/conventions.md` (frontmatter,
  trigger phrases, completion status section).
- steering/update: Read the target, apply with `fs_write`.
- steering/new: Create `~/.kiro/steering/<name>.md`.
- prompt/update: Read the target prompt in
  `~/.kiro/prompts/`, apply the change with `fs_write`.
- prompt/new: Create `~/.kiro/prompts/<name>.md`.

Proceed to the next finding after each apply/skip.

### Step 5 — Summary & Cleanup

After processing all items:

```
Applied: 2 (skill/update: owls, steering/new: completion-status)
Skipped: 1
```

Verify `~/.kiro/retro/pending/` is empty. If files remain from items that were
not presented (e.g., added mid-session), list them and ask whether to process
or discard.

## Constraints

- You MUST NOT suggest changes to this retro skill itself
  because it creates self-referential loops
- You MUST generalize findings into durable rules, not
  incident-specific fixes. Ask: "If I strip the specific
  names, does the rule still hold?" Specific details belong
  in the evidence, not the rule.
- You MUST read the entire skill directory (SKILL.md +
  references/) before proposing a skill change because
  partial reads cause contradictions


## Completion

| Status               | Criteria                                  |
|----------------------|-------------------------------------------|
| `DONE`               | All findings processed                |
|                      | (applied/skipped), pending dir empty  |
| `DONE_WITH_CONCERNS` | Findings processed but script errors  |
| `BLOCKED`            | Cannot read pending files or target   |
|                      | skills/steering unreadable            |
| `NEEDS_CONTEXT`      | Retro JSON files reference unknown    |
|                      | skills or targets that no longer exist|
