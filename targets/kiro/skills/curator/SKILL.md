---
name: curator
type: workflow
description: Ingests a URL or file into an Obsidian vault. Use when the user says "curator", "curator-ingest", or provides a URL or local file path to add to ~/Obsidian/MahVault. Do NOT use for personal zettels — those are human-only.
---

# Curator

Drives loom to ingest a URL or local file into the Obsidian vault.
The orchestrator's job: drive `$CURATOR_SH ingest/next/complete`, dispatch
agent tasks, run the human gate. Loom owns task ordering, predicate evaluation,
schema validation, and persistence.

## Dependencies

- `loom` — DAG execution library
- `tiling` — pane layout and activity tracking
- `editor` — used by the human gate to show the rendered report

## Parameters

- **url-or-path** (required): http(s) URL or local file path to ingest into the
  Obsidian vault.

## Critical rules

1. The orchestrator MUST dispatch `agent` tasks via `subagent` — never inline as
   part of its own thinking. The subagent has the focused prompt and isolated
   context.
2. The human gate MUST be human-driven. Auto-approving removes the user's veto.

## Workflow

### Step 1: Ingest

1. Set tiling activity, capture the parameter and build
   layout:
   ```bash
   CURATOR_INPUT="<url-or-path>"
   CURATOR_TARGET=$(basename "$CURATOR_INPUT")

   CURATOR_SKILLS=~/.kiro/skills
   CURATOR_SH=$CURATOR_SKILLS/home/curator/scripts/curator.sh
   CURATOR_LOOM=$CURATOR_SKILLS/home/loom/scripts/loom.sh
   CURATOR_TILING=$CURATOR_SKILLS/home/tiling/scripts/run-ttm.sh
   CURATOR_EDITOR=$CURATOR_SKILLS/home/editor/scripts/run-editor.sh

   $CURATOR_TILING activity set "curator($CURATOR_TARGET): Ingest"
   eval "$($CURATOR_TILING layout build)"
   ```
2. Ingest:
   ```bash
   CURATOR_WD=$($CURATOR_SH ingest "$CURATOR_INPUT")
   ```
3. If `ingest` fails: NEEDS_CONTEXT.

### Step 2: Drive the loop

```bash
$CURATOR_TILING activity set "curator($CURATOR_TARGET): Drive the loop"
```

Loop until done:

1. Run `$CURATOR_SH next "$CURATOR_WD"`. Parse the YAML response.

2. If `done: true` → break.

3. If `stuck: true` → BLOCKED.

4. Otherwise, for each `ready[].id`:

   - If the task `kind == human` → drive the human gate (see helper).
   - If the task `kind == agent` → dispatch the sub-agent (see helper).

   After the chosen branch returns, run
   `$CURATOR_SH complete "$CURATOR_WD" <id>`.

Dispatch independent agent ids in the same batch in parallel; human tasks always
run serially.

When stepping into a per-task action, refresh the activity to include the
current task id so the user can see progress:

```bash
$CURATOR_TILING activity set "curator($CURATOR_TARGET): <task-id>"
```

```bash
$CURATOR_TILING activity set "curator($CURATOR_TARGET): Done"
```

## Helper: Dispatch agent task

`$CURATOR_SH next` yields ready agent tasks with their `prompt_path` already
rendered. For each id, dispatch via the `subagent` MCP tool with `role: trusted`
(grants file-read/write access).

The sub-agent's `prompt_template` should instruct it to `fs_read` the
`prompt_path` and follow it. The agent writes its output to the `output_path`
(also in the `next` response). After dispatch returns, call
`$CURATOR_SH complete "$CURATOR_WD" "<id>"`.

Dispatch independent ids in parallel via the `subagent` `stages` array with no
`depends_on`.

## Helper: Drive human gate

Human tasks are conversational. The orchestrator reads the rendered
prompt at `prompt_path`, follows its instructions, captures the user's
decision into `output_path` against the task's `output_schema` via loom's
output writer, then calls `$CURATOR_SH complete "$CURATOR_WD" "<id>"`.

For the `gate` task (the sole human task), the rendered prompt is the ingest
report. Show it in the editor:

```bash
$CURATOR_EDITOR show file "<prompt_path>"
```

STOP and wait for the user. They may edit or `rm` files in
`$CURATOR_WD/global/vault-replica/`; replica state at apply time is the
authoritative decision. When the user signals proceed or abort, capture the
decision via the loom writer:

```bash
$CURATOR_LOOM output init "$CURATOR_WD" --task gate
$CURATOR_LOOM output add  "$CURATOR_WD" --task gate \
    --set 'proceed=true'   # or false
```

Then mark the task complete:

```bash
$CURATOR_SH complete "$CURATOR_WD" gate
```

`strip-dead-links` and `apply-replica` are gated on `proceed == true` via loom's
`when:` predicates — `false` skips both.

## Rules

1. The orchestrator MUST dispatch `agent` tasks via `subagent` — never inline as
   part of its own thinking. The subagent has the focused prompt and isolated
   context.
2. The human gate MUST be human-driven. Auto-approving removes the user's veto.
3. Source binary files and `*.assets/` folders are immutable — they are copied
   verbatim from source so any edit loses fidelity.
4. Atomic page filenames use natural item names (no kebab-casing) so
   `[[Item Name]]` wikilinks resolve directly.
5. A failed task aborts the entire run. Loom's `next()` raises
   `RunAborted`; the orchestrator emits a run-level error. Do not
   try to recover by re-running the failed task; report status and
   stop.

## Completion

| Status               | Criteria                                                  |
| -------------------- | --------------------------------------------------------- |
| `DONE`               | `next` reported done; no judge verdict was REJECT         |
| `DONE_WITH_CONCERNS` | `next` reported done; ≥1 verdict was REJECT               |
| `BLOCKED`            | `next` / `complete` errored, plan stuck, or user declined |
| `NEEDS_CONTEXT`      | `ingest` rejected the input                               |

Determine the final status by aggregating judge verdicts:

```bash
$CURATOR_SH status "$CURATOR_WD"
```

Loom workdirs live under `/tmp/curator/<YYYY-MM-DD>/<slug>/` — ephemeral by
design. Re-running `ingest "<url-or-path>"` wipes the workdir and starts fresh;
previous runs are not auto-resumed.
