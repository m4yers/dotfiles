---
name: retro
type: flow
description: Reviews learnings queued as JSON items in ~/.kiro/retro/pending/ and applies the ones the user approves to skills, steering, or prompts. Applies only queued pending items; queuing happens mid-session via the retro steering file. Use when the user says "retro", "retrospective", "what did we learn", or "session review". Do NOT use to create or update a skill on request outside a retro — use dojo or sifu instead.
---

# Session Retrospective

Review learnings queued during the session and encode the approved ones into
skills, steering, or prompts. The `retro` steering file queues them as JSON
files in the pending folder.

## Invariants

These hold whatever path the flow takes.

1. Retro skill changes MUST stay out of retro sessions, because modifying the
   skill that is currently executing creates self-referential loops.
2. Findings MUST be generalized into durable rules, not incident-specific
   fixes, because specific details go stale while patterns endure. Ask: "If I
   strip the specific names, does the rule still hold?" Specific details
   belong in the evidence, not the rule.
3. The entire skill directory (SKILL.md + references/) MUST be read before
   proposing a skill change, because partial reads cause contradictions. The
   reads are independent; make all calls in parallel.
4. Each finding MUST get one concrete proposed change; present alternatives
   only when the user asks.

## Dependencies

- `tiling` — activity tracking.
- `dojo` / `sifu` — authoring conventions (`sifu/references/`) and the
  `autochecks` lint run after each skill change.

## Parameters

- **folder** (optional): path to the retro pending directory. Default:
  `~/.kiro/retro/pending/`

The activity label target is `default` when using the default folder,
`custom` when an explicit folder is provided.

## Commands

```bash
TTM=~/.kiro/skills/home/tiling/scripts/run-ttm.sh
RETRO_TABLE=~/.kiro/skills/home/retro/scripts/retro-table.py
RETRO_WRITE=~/.kiro/skills/home/retro/scripts/write-retro-item.py
LIST_NS=~/.kiro/skills/home/retro/scripts/list-namespaces.py
CHECK_TARGET=~/.kiro/skills/home/retro/scripts/list-namespaces.py
SIFU=~/.kiro/skills/home/sifu/scripts/sifu.sh
```

- `RETRO_TABLE` shows the dashboard and, with `--list`, `--count`, `--path
  N` or `--delete N...`, lists, counts, resolves or deletes pending items by
  dashboard number. See `--help` for the JSON shape.
- `RETRO_WRITE` queues one item; the `retro` steering file calls it, this
  flow does not.
- `LIST_NS` lists skill namespaces; `CHECK_TARGET --check` validates a new
  target path (see [namespace decision](references/namespace-decision.md)).
- `scripts/retro-reminder.sh` is run by the agent hook in dotfiles-hidden
  `targets/aws-kiro/agents/trusted-aws.json`; this flow does not call it.

## Workflow

The steps below are the default path. The operator MAY redirect at any point:
skip, repeat, reorder, or add a step. Announce each change in one line before
acting, and confirm first when it would break an invariant.

### Step 1: Load Learnings

Goal: load every pending item.

```bash
$TTM activity set "retro(<target>): Load Learnings"
```

1. Load the items:

   ```bash
   $RETRO_TABLE --dir <folder> --list
   ```

   Exit 1 means some files were skipped; the `error:` lines name them. Note
   them for the Step 5 summary.

On completion: proceed to Step 2.

### Step 2: Pre-check

Goal: drop findings that are already encoded.

```bash
$TTM activity set "retro(<target>): Pre-check"
```

1. Read the target of every skill/update and steering/update finding. The
   reads are independent; make all calls in parallel.
2. Ultrathink, then decide for each finding: novel or already covered
   (encoded in the target, or a duplicate of another finding).
3. Tell the user which findings are covered, one line each with the file
   that already encodes it.
4. Delete the covered findings in one call, using ids from the latest
   `--list`:

   ```bash
   $RETRO_TABLE --dir <folder> --delete <N> [<N> ...]
   ```

On completion: proceed to Step 3.

### Step 3: Dashboard

Goal: show the actionable findings and let the user pick.

```bash
$TTM activity set "retro(<target>): Dashboard"
```

1. Run the dashboard:

   ```bash
   $RETRO_TABLE --dir <folder>
   ```

2. Show the script output unchanged, then append the prompt below.

   ```
   → Pick a number to start, or "all" to go through each
   ```

3. If there are zero high/medium findings, say "No actionable learnings from
   this session." and stop.

4. STOP and wait for the user.

On completion: proceed to Step 4.

### Step 4: Process One at a Time

Goal: get an apply or skip decision for each selected finding.

```bash
$TTM activity set "retro(<target>): Process Findings"
```

1. Ultrathink about the proposed change, then show it and ask **apply /
   skip?** STOP and wait for the user.

   ```
   ## [#N] Finding title
   **Area:** skill | **Action:** update | **Severity:** high
   **Target:** <skill-name>
   **Path:** ~/.kiro/skills/<ns>/<skill-name>/SKILL.md
   **Evidence:** <what happened in the conversation>
   **Proposed change:** <concrete diff or description>
   ```

2. On apply, make the change per [Apply Rules](#apply-rules).

3. On apply to a skill, lint it and fix every error before going on:

   ```bash
   $SIFU autochecks <skill-dir> --format text
   ```

   Pass: `Summary: 0 errors`. Fail: fix the reported lines and rerun.
   Steering and prompt files have no autocheck; check them against the
   formatting rule in Apply Rules.

4. Record the decision, then delete the item by its number on the latest
   dashboard:

   ```bash
   $RETRO_TABLE --dir <folder> --delete <N>
   ```

5. Re-display the dashboard with `$RETRO_TABLE --dir <folder>`; it also
   shows items added during the session. STOP and wait for the next pick.

When no findings remain: proceed to Step 5.

### Step 5: Summary & Cleanup

Goal: report every decision and confirm the pending folder is empty.

```bash
$TTM activity set "retro(<target>): Summary & Cleanup"
```

1. Print the summary, one entry per deleted item:

   ```
   Applied: 2 (skill/update: <skill>, steering/new: <rule>)
   Skipped: 1 (<title>)
   Covered: 1 (<title> → <file>)
   ```

2. Check that nothing is left:

   ```bash
   $RETRO_TABLE --dir <folder> --count
   ```

   Pass: prints `0`, exit 0. Fail: show the remaining items with
   `$RETRO_TABLE --dir <folder>`, ask whether to process or discard them,
   STOP and wait for the user, then re-enter Step 4.

3. Mark the flow done:

   ```bash
   $TTM activity set "retro(<target>): Done"
   ```

## Apply Rules

- skill/update: read the full target skill directory, then apply the change
  with `fs_write` or `str_replace`.
- skill/new: search installed skills for overlapping scope with `grep -R
  --include=SKILL.md '^description:' ~/.kiro/skills/`. If one overlaps, ask
  whether to broaden it instead and STOP and wait for the user; when
  accepted, handle the finding as skill/update on that skill. Otherwise load
  [namespace decision](references/namespace-decision.md), then create
  `SKILL.md` at the checked path following
  `~/.kiro/skills/home/sifu/references/authoring.md` (frontmatter, trigger
  phrases, completion status section).
- steering/update: read the target, apply with `fs_write`.
- steering/new: load [namespace decision](references/namespace-decision.md),
  then create `{name}.md` at the checked path.
- prompt/update: read the target prompt in `~/.kiro/prompts/`, apply the
  change with `fs_write`.
- prompt/new: create `~/.kiro/prompts/{name}.md`. Prompts are flat, so no
  namespace selection is required.

Formatting: changes to skill files MUST follow the 80-char prose, aligned table
and single-line frontmatter rules of the sifu style guide in
`~/.kiro/skills/home/sifu/references/style.md`.

## Severity

- **high** — user corrected the agent, wasted >2 min, factual error, or data
  loss risk
- **medium** — missing capability user worked around, wrong default, repeated
  friction in this session
- **low** — minor optimization, documentation of already-correct behavior

## Completion

| Status               | Criteria                                                              |
| -------------------- | --------------------------------------------------------------------- |
| `DONE`               | measure: `--count` prints 0 and every deleted item is in the Step 5   |
|                      | summary as applied, skipped or covered; intent: every pending         |
|                      | learning was shown to the user and applied or declined                |
| `DONE_WITH_CONCERNS` | measure: `--count` prints 0 but a script exited non-zero (skipped     |
|                      | files, lint unavailable); intent: decisions recorded, tooling needs a |
|                      | retro                                                                 |
| `BLOCKED`            | measure: `RETRO_TABLE` cannot read the folder or a target is          |
|                      | unreadable; intent: no change can be applied safely                   |
| `NEEDS_CONTEXT`      | measure: an item names a skill or target that no longer exists;       |
|                      | intent: the user must say where the learning belongs                  |

- Stop after 3 failed apply attempts and report status BLOCKED with what was
  tried.
