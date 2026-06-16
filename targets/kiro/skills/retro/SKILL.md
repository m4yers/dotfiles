---
name: retro
type: workflow
description: Analyzes the current session for learnings and encodes them into skills, steering, or prompts. Use when the user says "retro", "retrospective", "what did we learn", or "session review". Do not use for tracking learnings mid-session — that happens automatically via the retro steering file.
---

# Session Retrospective

Review learnings collected during this session and encode them into skills,
steering, or prompts.

Learnings are tracked per the `retro` steering file and stored
as JSON files in `~/.kiro/retro/pending/`.

## Parameters

- **folder** (optional): path to retro pending directory. Default:
  `~/.kiro/retro/pending/`

Activity label target is `default` when using the default folder, `custom` when
an explicit folder is provided.

## Workflow

### Step 1: Load Learnings

1. Set tiling activity:
   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
       activity set "retro(<target>): Load Learnings"
   ```
2. Read all JSON files from `~/.kiro/retro/pending/`.

On completion: proceed to Step 2.

### Step 2: Pre-check

1. Set tiling activity:

   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
       activity set "retro(<target>): Pre-check"
   ```

2. Ultrathink about whether each finding is truly novel before dropping or
   keeping it. Before presenting findings:

   - For skill/update: read the target SKILL.md to verify the suggestion isn't
     already encoded
   - For steering/update: read the target steering file to verify
   - Drop any findings that are already covered
   - Delete the backing JSON files for duplicates and already-encoded findings
     so the dashboard only shows actionable items

   When verifying multiple findings, the reads and searches are independent —
   make all calls in parallel.

On completion: proceed to Step 3.

### Step 3: Dashboard

1. Set tiling activity:

   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
       activity set "retro(<target>): Dashboard"
   ```

2. Run the table script to display findings:

   ```bash
   python3 ~/.kiro/skills/home/retro/scripts/retro-table.py \
       --dir <folder>
   ```

3. Show the script output as-is — do NOT reformat or duplicate it as a separate
   table. Never substitute a custom markdown table for the script output, even
   when resuming or re-displaying the dashboard. Just append the prompt:

   ```
   → Pick a number to start, or "all" to go through each
   ```

   Severity icons: ● high | ◐ medium | ○ low

4. If zero high/medium findings: "No actionable learnings from this session."
   and stop.

On completion: proceed to Step 4.

### Step 4: Process One at a Time

1. Set tiling activity:

   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
       activity set "retro(<target>): Process Findings"
   ```

2. For each selected finding, ultrathink about the proposed change before
   presenting it. Show:

   ```
   ## [#N] Finding title
   **Area:** skill | **Action:** update | **Severity:** high
   **Target:** <skill-name>
   **Path:** ~/.kiro/skills/<ns>/<skill-name>/SKILL.md
   **Evidence:** <what happened in the conversation>
   **Proposed change:** <concrete diff or description>
   ```

   Then ask: **apply / skip?**

3. After each apply or skip, delete the backing JSON file.

4. Check for any new retro files added during this session.

5. Re-display the dashboard with only the remaining pending items.

**Apply rules by area/action (see Categories and Severity for the full
mapping):**

- skill/update: Read the full target SKILL.md, apply the change with `fs_write`,
  `str_replace` or `append`.
- skill/new: Run the Namespace Decision flow, then create
  `~/.kiro/skills/{location}/{name}/SKILL.md` following the conventions in
  `~/.kiro/skills/home/dojo/references/conventions.md` (frontmatter,
  trigger phrases, completion status section).
- steering/update: Read the target, apply with `fs_write`.
- steering/new: Run the Namespace Decision flow, then create
  `~/.kiro/steering/{location}/{name}.md`.
- prompt/update: Read the target prompt in `~/.kiro/prompts/`, apply the change
  with `fs_write`.
- prompt/new: Create `~/.kiro/prompts/{name}.md`. Prompts are flat — no
  namespace selection is required.

## Namespace Decision

For any finding with `action=new` on an area that lives under a
namespaced tree (`skill` or `steering`), retro MUST ask the user
where the new artefact belongs before writing files. retro never
infers the target namespace from the finding's content.

1. Enumerate installed namespaces:
   ```bash
   ~/.kiro/skills/home/retro/scripts/list-namespaces.sh
   ```
2. Show the user the list and ask: "Where should this <area> live?
   (e.g. `home` for a home-flat entry, `aws/util` for a categorised
   aws entry)".
3. The user's answer becomes `{location}`. Validate that the
   containing directory exists (`~/.kiro/skills/{location}/` or
   `~/.kiro/steering/{location}/`) — if not, re-prompt.
4. Validate that the target path does not already exist — refuse
   to overwrite.

Proceed to the next finding after each apply/skip.

On completion: proceed to Step 5.

### Step 5: Summary & Cleanup

1. Set tiling activity:

   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
       activity set "retro(<target>): Summary & Cleanup"
   ```

2. After processing all items:

   ```
   Applied: 2 (skill/update: <skill>, steering/new: <rule>)
   Skipped: 1
   ```

3. Verify `~/.kiro/retro/pending/` is empty. If files remain from items that
   were not presented (e.g., added mid-session), list them and ask whether to
   process or discard.

4. Set tiling activity to done:

   ```bash
   ~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
       activity set "retro(<target>): Done"
   ```

## Categories and Severity

| Area     | Action | Write method     |
| -------- | ------ | ---------------- |
| skill    | update | Direct write     |
| skill    | new    | Direct write     |
| steering | update | Direct write     |
| steering | new    | Direct write     |
| prompt   | update | Direct write     |
| prompt   | new    | Direct write     |

Severity levels:

- **high** — user corrected the agent, wasted >2 min, factual error, or data
  loss risk
- **medium** — missing capability user worked around, wrong default, repeated
  friction in this session
- **low** — minor optimization, documentation of already-correct behavior

## Rules

- Keep retro skill changes out of retro sessions — modifying the skill that is
  currently executing creates self-referential loops.
- Generalize findings into durable rules, not incident-specific fixes, because
  specific details become stale while patterns endure. Ask: "If I strip the
  specific names, does the rule still hold?" Specific details belong in the
  evidence, not the rule.
- Read the entire skill directory (SKILL.md + references/) before proposing a
  skill change because partial reads cause contradictions. These reads are
  independent — make all calls in parallel.
- Propose one concrete change per finding and commit to it — do not present
  multiple alternatives unless the user asks.

## Completion

| Status               | Criteria                            |
| -------------------- | ----------------------------------- |
| `DONE`               | All findings processed              |
|                      | (applied/skipped), pending dir      |
|                      | empty                               |
| `DONE_WITH_CONCERNS` | Findings processed but script      |
|                      | errors hit                         |
| `BLOCKED`            | Cannot read pending files or target |
|                      | skills/steering unreadable          |
| `NEEDS_CONTEXT`      | Retro JSON files reference unknown  |
|                      | skills or targets that no longer    |
|                      | exist                               |

- Stop after 3 failed apply attempts and report status BLOCKED with what was
  tried.
