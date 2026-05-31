---
name: dojo
type: workflow
description: Creates, updates, or reviews skills for the Kiro CLI setup. Use when user says "create skill", "new skill", "improve skill", "update skill", "review skill", "audit skill", or wants to build, modify, or audit a skill.
---

# Dojo

Drives loom to create, update, or review a skill. The orchestrator's job:
drive `$DOJO_SH ingest/next/complete`, dispatch agent tasks,
run human gates. Loom owns task ordering, predicate evaluation,
schema validation, and persistence.

## Dependencies

- `loom` — DAG execution library
- `tiling` — pane layout and activity tracking
- `skill-analytics` — activation logging
- `editor` — used by human gates to show files

## Parameters

- **operation** (required): `create`, `update`, or `review`
- **name** (required): kebab-case skill name. For `create`,
  the desired name of the new skill. For `update`, the name
  of an existing installed skill.

## Workflow

### Step 1: Ingest

1. Capture parameters and set up tooling aliases:
   ```bash
   DOJO_OP=<create|update|review>
   DOJO_NAME=<skill-name>
   DOJO_TAG="dojo($DOJO_OP:$DOJO_NAME)"

   DOJO_SKILLS=~/.kiro/skills
   DOJO_SH=$DOJO_SKILLS/home/dojo/scripts/dojo.sh
   DOJO_TILING=$DOJO_SKILLS/home/tiling/scripts/run-ttm.sh
   DOJO_EDITOR=$DOJO_SKILLS/home/editor/scripts/run-editor.sh
   DOJO_ANALYTICS=$DOJO_SKILLS/home/skill-analytics/scripts/add-invocation.sh
   ```
2. Set tiling activity, record invocation, build layout:
   ```bash
   $DOJO_TILING activity set "$DOJO_TAG: Ingest"
   $DOJO_ANALYTICS dojo TRIGGER_TYPE:TRIGGER_NAME
   eval "$($DOJO_TILING layout build)"
   ```
3. Ingest:
   ```bash
   DOJO_WD=$($DOJO_SH ingest --op "$DOJO_OP" --name "$DOJO_NAME")
   ```
4. If `ingest` fails: NEEDS_CONTEXT.

### Step 2: Drive the loop

```bash
$DOJO_TILING activity set "$DOJO_TAG: Drive the loop"
```

Loop until done:

1. Run `$DOJO_SH next "$DOJO_WD"`. Parse the YAML response.
2. If `done: true` → break.
3. If `stuck: true` → BLOCKED.
4. Otherwise, for each `ready[].id`:
   - If the task `kind == human` → drive the human gate (see helper).
   - If the task `kind == agent` → dispatch the sub-agent
     (see helper).
   - Then `$DOJO_SH complete "$DOJO_WD" <id>`.

Independent ids in one batch can be dispatched in parallel.

When stepping into a per-task action, refresh the activity to
include the current task id so the user can see progress:

```bash
$DOJO_TILING activity set "$DOJO_TAG: <task-id>"
```

```bash
$DOJO_TILING activity set "$DOJO_TAG: Done"
```

## Helper: Dispatch agent task

`$DOJO_SH next` yields ready agent tasks with their `prompt_path`
already rendered. For each id, dispatch via the `subagent` MCP
tool with `role: trusted` (grants file-read/write access).

The sub-agent's `prompt_template` should instruct it to
`fs_read` the `prompt_path` and follow it. The agent writes its
output to the `output_path` (also in the `next` response).
After dispatch returns, call `$DOJO_SH complete "$DOJO_WD" "<id>"`.

Dispatch independent ids in parallel via the `subagent` `stages`
array with no `depends_on`.

## Helper: Drive human gate

Human tasks are conversational. Read the rendered prompt at
`prompt_path`, follow its instructions, and write structured
YAML to `output_path` against the schema. Then call
`$DOJO_SH complete "$DOJO_WD" "<id>"`.

For gates that show files (e.g., `design-review`,
`final-review`), use the editor:

```bash
$DOJO_EDITOR show file <path>
```

STOP and wait for the user. The user can accept, edit, or
decline. Capture their decision and any edits in the output
file before completing the task.

## Rules

1. The orchestrator MUST dispatch `agent` tasks via `subagent` —
   never inline as part of its own thinking. The subagent has
   the focused prompt and isolated context.
2. Human gates MUST be human-driven. Auto-completing them
   removes the user's veto.
3. A failed task aborts the entire run. Loom's `next()`
   raises `RunAborted`; the orchestrator emits a run-level
   error. Do not try to recover by re-running the failed task;
   report status and stop.

## Completion

| Status               | Criteria                                              |
|----------------------|-------------------------------------------------------|
| `DONE`               | `final-review` (create) or `user-review` (update) accepted |
| `DONE_WITH_CONCERNS` | Accepted with the user noting unresolved concerns     |
| `BLOCKED`            | `next`/`complete` errored, plan stuck, or user declined |
| `NEEDS_CONTEXT`      | `ingest` rejected the operation                       |

Loom workdirs live under `/tmp/dojo/<skill-name>/` —
ephemeral by design, named by the skill being created or
updated. Re-running `ingest --op <op> --name <name>` wipes
the workdir and starts fresh; previous runs are not
auto-resumed.
