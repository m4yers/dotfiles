---
name: retro
description: Analyze the current session for learnings and encode them into skills, steering, or vault. Use when the user says "retro", "retrospective", "what did we learn", or "session review". Do NOT use for tracking learnings mid-session — that happens automatically via the session-retro-tracker steering file.
---

# Session Retrospective

Review learnings collected during this session and encode them into skills,
steering, or vault.

Learnings are tracked per the `session-retro-tracker` steering file and stored
as JSON files in `~/.kiro/retro/pending/`.

## Categories

| Area       | Action   | Write method     |
|------------|----------|------------------|
| skill      | update   | Direct write     |
| skill      | new      | Direct write     |
| steering   | update   | Direct write     |
| steering   | new      | Direct write     |
| vault      | new      | Via vault-worker |
| vault      | update   | Via vault-worker |
| prompt     | update   | Direct write     |
| prompt     | new      | Direct write     |

## Severity

- **high** — user corrected the agent, wasted >2 min, factual error, or data
  loss risk
- **medium** — missing capability user worked around, wrong default, repeated
  friction in this session
- **low** — minor optimization, documentation of already-correct behavior

## Workflow

### Step 1 — Load Learnings

Read all JSON files from `~/.kiro/retro/pending/`.

Also check the conversation context for `vault-stale.py` output injected by the
agentSpawn hook. Any lines matching `STALE  <path>` represent vault articles
whose source files changed since the article was written. Add each as a vault/update finding with severity `medium` — the stale article path is the
target, the changed source files are the evidence.

### Step 2 — Pre-check

Before presenting findings:

- For skill/update: read the target SKILL.md to verify the suggestion
  isn't already encoded
- For steering/update: read the target steering file to verify
- For vault/update: run
  `~/.kiro/skills/util/vault/scripts/vault-search.py` to check existing
  coverage
- For vault/new: run
  `~/.kiro/skills/util/vault/scripts/vault-search.py` to verify the topic
  doesn't already exist
- Drop any findings that are already covered

### Step 3 — Dashboard

Run the table script to display findings:
```bash
~/.kiro/skills/util/retro/scripts/retro-table.sh
```

Show the script output as-is — do NOT reformat or duplicate it as a
separate table. Just append the prompt:

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
**Path:** ~/.kiro/skills/diagnostics/owls/SKILL.md
**Evidence:** <what happened in the conversation>
**Proposed change:** <concrete diff or description>
```

Then ask: **apply / skip?**

After each apply or skip, delete the backing JSON file, check for
any new retro files added during this session, and re-display the
dashboard with only the remaining pending items.

**Apply rules by area/action:**

- skill/update: Read the full target SKILL.md, apply the change with
  `fs_write`, `str_replace` or `append`.
- skill/new: Create `~/.kiro/skills/<category>/<name>/SKILL.md` following
  the conventions in
  `~/.kiro/skills/util/skill-builder/references/conventions.md` (frontmatter,
  trigger phrases, completion status section).
- steering/update: Read the target, apply with `fs_write`.
- steering/new: Create `~/.kiro/steering/<name>.md`.
- vault/new, vault/update: Prepare detailed facts with
  provenance, then delegate to `vault-worker` via `use_subagent`.
  Follow the full vault write protocol in
  `~/.kiro/skills/util/vault/SKILL.md`.
- prompt/update: Read the target prompt in
  `~/.kiro/prompts/`, apply the change with `fs_write`.
- prompt/new: Create `~/.kiro/prompts/<name>.md`.

Proceed to the next finding after each apply/skip.

### Step 5 — Summary & Cleanup

After processing all items:

```
Applied: 2 (skill/update: owls, steering/new: completion-status)
Skipped: 1
Vault writes delegated: 1 (vault/new: arrow batch lifecycle)
```

Verify `~/.kiro/retro/pending/` is empty. If files remain from items that were
not presented (e.g., added mid-session), list them and ask whether to process
or discard.

## Constraints

- You MUST NOT write to vault directly because all vault writes go through
  vault-worker sub-agent
- You MUST NOT suggest changes to this retro skill itself because it creates
  self-referential loops
- You MUST generalize findings into durable rules, not incident-specific fixes.
  Ask: "If I strip the specific names, does the rule still hold?" Specific
  details belong in the evidence, not the rule.
- You MUST read the entire skill directory (SKILL.md + references/) before
  proposing a skill change because partial reads cause contradictions
- You MUST follow the full consolidation protocol for vault writes (search →
  classify overlap → report → write)


**Constraints:**
- You MUST log activation at the start of the first
  workflow step:
  ```bash
  ~/.kiro/skills/util/skill-analytics/scripts/add-invocation.sh \
    retro TYPE:NAME  # e.g. user:alice, skill:cr-review
  ```

## Completion

| Status               | Criteria                                  |
|----------------------|-------------------------------------------|
| `DONE`               | All findings processed (applied/skipped), |
|                      | pending directory empty                   |
| `DONE_WITH_CONCERNS` | Findings processed but vault-worker       |
|                      | delegation pending or script errors hit   |
| `BLOCKED`            | Cannot read pending files or target       |
|                      | skills/steering unreadable                |
| `NEEDS_CONTEXT`      | Retro JSON files reference unknown skills |
|                      | or targets that no longer exist           |
