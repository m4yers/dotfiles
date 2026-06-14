---
name: dojo
type: workflow
description: Creates, updates, or reviews skills for the Kiro CLI setup. Use when user says "create skill", "new skill", "improve skill", "update skill", "review skill", "audit skill", or wants to build, modify, or audit a skill.
---

# Dojo

Drives loom to create, update, or review a skill. The orchestrator's job: drive
`$DOJO ingest/next/complete`, dispatch agent tasks, run human gates. Loom owns
task ordering, predicate evaluation, schema validation, and persistence.

## Dependencies

- `loom` — DAG execution library
- `tiling` — pane layout and activity tracking
- `editor` — used by human gates to show files

## Parameters

- **operation** (required): `create`, `update`, or `review`
- **name** (required): kebab-case skill name. For `create`, the desired name of
  the new skill. For `update`, the name of an existing installed skill.

## Workflow

### Step 1: Ingest

1. Capture parameters and set up tooling aliases:
   ```bash
   DOJO_OP=<create|update|review>
   DOJO_NAME=<skill-name>
   DOJO_TAG="dojo($DOJO_OP:$DOJO_NAME)"

   DOJO=~/.kiro/skills/home/dojo/scripts/dojo.sh
   TILING=~/.kiro/skills/home/tiling/scripts/run-ttm.sh
   EDITOR=~/.kiro/skills/home/editor/scripts/run-editor.sh
   ```
2. Set tiling activity and build layout:
   ```bash
   $TILING activity set "$DOJO_TAG: Ingest"
   eval "$($TILING layout build)"
   ```
3. Ingest:
   ```bash
   DOJO_WD=$($DOJO ingest --op "$DOJO_OP" --name "$DOJO_NAME")
   ```
4. If `ingest` fails: NEEDS_CONTEXT.

### Step 2: Drive the loop

```bash
$TILING activity set "$DOJO_TAG: Drive the loop"
```

Loop until done:

1. Run `$DOJO next "$DOJO_WD"`. Parse the YAML response.
2. If `done: true` → break.
3. If `stuck: true` → BLOCKED.
4. Otherwise, for each `ready[].id`:
   - If the task `kind == human` → drive the human gate (see helper).
   - If the task `kind == agent` → dispatch the sub-agent (see helper).
   - Then `$DOJO complete "$DOJO_WD" <id>`.

Independent ids in one batch can be dispatched in parallel.

When stepping into a per-task action, refresh the activity to include the
current task id so the user can see progress:

```bash
$TILING activity set "$DOJO_TAG: <task-id>"
```

```bash
$TILING activity set "$DOJO_TAG: Done"
```

## Helper: Dispatch agent task

`$DOJO next` yields ready agent tasks with their `prompt_path` already
rendered. For each id, dispatch via the `subagent` MCP tool with `role: trusted`
(grants file-read/write access).

The sub-agent's `prompt_template` should instruct it to `fs_read` the
`prompt_path` and follow it. The agent writes its output to the `output_path`
(also in the `next` response). After dispatch returns, call
`$DOJO complete "$DOJO_WD" "<id>"`.

Dispatch independent ids in parallel via the `subagent` `stages` array with no
`depends_on`.

## Helper: Drive human gate

Human tasks are conversational. Read the rendered prompt at `prompt_path`,
follow its instructions, and write structured YAML to `output_path` against the
schema. Then call `$DOJO complete "$DOJO_WD" "<id>"`.

For gates that show files (e.g., `design-review`, `final-review`), use the
editor:

```bash
$EDITOR show file <path>
```

STOP and wait for the user. The user can accept, edit, or decline. Capture their
decision and any edits in the output file before completing the task.

## Rules

1. The orchestrator MUST dispatch `agent` tasks via `subagent` — never inline as
   part of its own thinking. The subagent has the focused prompt and isolated
   context.
2. Human gates MUST be human-driven. Auto-completing them removes the user's
   veto.
3. A failed task aborts the entire run. Loom's `next()` raises `RunAborted`; the
   orchestrator emits a run-level error. Do not try to recover by re-running the
   failed task; report status and stop.

## Plan topology

### Create

```text
○  23 summary
▣  22 final-review
◆  21 skill-modify
○                  20 checks-report
├─┬─┬─┬─┬─┬─┬─┬─╮
│ ◆ ╷ ╷ ╷ ╷ ╷ ╷ ╷  12 check-authoring
├─╯ ╷ ╷ ╷ ╷ ╷ ╷ ╷
│   ◆ ╷ ╷ ╷ ╷ ╷ ╷  13 check-model-awareness
├───╯ ╷ ╷ ╷ ╷ ╷ ╷
│     ◆ ╷ ╷ ╷ ╷ ╷  14 check-scripts
├─────╯ ╷ ╷ ╷ ╷ ╷
│       ◆ ╷ ╷ ╷ ╷  15 check-interface   when: ${task:find-skill:type} == 'interface'
├───────╯ ╷ ╷ ╷ ╷
│         ◆ ╷ ╷ ╷  16 check-tool   when: ${task:find-skill:type} == 'tool'
├─────────╯ ╷ ╷ ╷
│           ◆ ╷ ╷  17 check-workflow   when: ${task:find-skill:type} == 'workflow'
├───────────╯ ╷ ╷
│             ◆ ╷  18 check-reference   when: ${task:find-skill:type} == 'reference'
├─────────────╯ ╷
│               ◆  19 check-design
├───────────────╯
○  11 check-autochecks
○  10 find-skill
◆  09 skill-materialize
↻      08 design-review   ↻ loop → design · while …
├─┬─╮
│ ○ │  06 design-render
├─╯ │
│   ○  07 design-checks
├───╯
◆      05 design
├─┬─╮
○ │ │  02 check-name
│ ○ │  03 check-location
├─╯ │
│   ○  04 check-overlaps
├───╯
▣  01 gather
```

### Update

```text
○  15 summary
▣  14 final-review
◆  13 skill-modify
○                12 checks-report
├─┬─┬─┬─┬─┬─┬─╮
│ ◆ ╷ ╷ ╷ ╷ ╷ ╷  05 check-authoring
├─╯ ╷ ╷ ╷ ╷ ╷ ╷
│   ◆ ╷ ╷ ╷ ╷ ╷  06 check-model-awareness
├───╯ ╷ ╷ ╷ ╷ ╷
│     ◆ ╷ ╷ ╷ ╷  07 check-scripts
├─────╯ ╷ ╷ ╷ ╷
│       ◆ ╷ ╷ ╷  08 check-interface   when: ${task:gather-update:type} == 'interface'
├───────╯ ╷ ╷ ╷
│         ◆ ╷ ╷  09 check-tool   when: ${task:gather-update:type} == 'tool'
├─────────╯ ╷ ╷
│           ◆ ╷  10 check-workflow   when: ${task:gather-update:type} == 'workflow'
├───────────╯ ╷
│             ◆  11 check-reference   when: ${task:gather-update:type} == 'reference'
├─────────────╯
○  04 check-autochecks
◆  03 modify-changes
▣  02 gather-update
○  01 find-skill
```

### Review

```text
○  14 finalize
↻  13 skill-fix-apply   ↻ loop → show-report · while …
▣  12 skill-fix-review
○  11 show-report
○                10 checks-report
├─┬─┬─┬─┬─┬─┬─╮
│ ◆ ╷ ╷ ╷ ╷ ╷ ╷  03 check-authoring
├─╯ ╷ ╷ ╷ ╷ ╷ ╷
│   ◆ ╷ ╷ ╷ ╷ ╷  04 check-model-awareness
├───╯ ╷ ╷ ╷ ╷ ╷
│     ◆ ╷ ╷ ╷ ╷  05 check-scripts
├─────╯ ╷ ╷ ╷ ╷
│       ◆ ╷ ╷ ╷  06 check-interface   when: ${task:find-skill:type} == 'interface'
├───────╯ ╷ ╷ ╷
│         ◆ ╷ ╷  07 check-tool   when: ${task:find-skill:type} == 'tool'
├─────────╯ ╷ ╷
│           ◆ ╷  08 check-workflow   when: ${task:find-skill:type} == 'workflow'
├───────────╯ ╷
│             ◆  09 check-reference   when: ${task:find-skill:type} == 'reference'
├─────────────╯
○  02 check-autochecks
○  01 find-skill
```

## Completion

| Status               | Criteria                                                   |
| -------------------- | ---------------------------------------------------------- |
| `DONE`               | `final-review` (create) or `user-review` (update) accepted |
| `DONE_WITH_CONCERNS` | Accepted with the user noting unresolved concerns          |
| `BLOCKED`            | `next`/`complete` errored, plan stuck, or user declined    |
| `NEEDS_CONTEXT`      | `ingest` rejected the operation                            |

Loom workdirs live under `/tmp/dojo/<skill-name>/` — ephemeral by design, named
by the skill being created or updated. Re-running
`ingest --op <op> --name <name>` wipes the workdir and starts fresh; previous
runs are not auto-resumed.
