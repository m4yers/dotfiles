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

   DOJO=~/.kiro/skills/home/dojo/scripts/dojo.sh
   TILING=~/.kiro/skills/home/tiling/scripts/run-ttm.sh
   EDITOR=~/.kiro/skills/home/editor/scripts/run-editor.sh
   ```
2. Set tiling activity and build layout:
   ```bash
   $TILING activity set "dojo($DOJO_OP:$DOJO_NAME): Ingest"
   eval "$($TILING layout build)"
   ```
3. Ingest:
   ```bash
   DOJO_WD=$($DOJO ingest --op "$DOJO_OP" --name "$DOJO_NAME")
   ```
4. If `ingest` fails: NEEDS_CONTEXT.
5. On success: proceed to Step 2.

### Step 2: Drive the loop

1. Set tiling activity to Drive:
   ```bash
   $TILING activity set "dojo($DOJO_OP:$DOJO_NAME): Drive the loop"
   ```
2. Loop until done:
   - Run `$DOJO next "$DOJO_WD"`. Parse the YAML response.
   - If `done: true` → break.
   - If `stuck: true` → BLOCKED.
   - Otherwise, for each `ready[].id`:
     - If `kind == human` → drive the human gate (see helper).
     - If `kind == agent` → dispatch the sub-agent (see helper).
     - Then `$DOJO complete "$DOJO_WD" <id>`.
   - Independent ids in one batch can be dispatched in parallel.

   When stepping into a per-task action, refresh the activity to include the
   current task id so the user can see progress:
   ```bash
   $TILING activity set "dojo($DOJO_OP:$DOJO_NAME): <task-id>"
   ```
3. Set tiling activity to Done:
   ```bash
   $TILING activity set "dojo($DOJO_OP:$DOJO_NAME): Done"
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
4. Skill modifications dispatched to sub-agents MUST be limited to what is
   directly requested; sub-agents MUST NOT add abstractions, helpers, or
   defensive code beyond what was asked, because uncommanded additions inflate
   the diff and drift from the requested change.

## Plan visualisation

See [references/plan-topology.md](references/plan-topology.md) for the
per-operation task DAGs (create, update, review).

## Completion

| Status               | Criteria                                                              |
|----------------------|-----------------------------------------------------------------------|
| `DONE`               | Skill files materialised under ~/.kiro/skills/<category>/<name>/, or review report saved to the workdir. |
| `DONE_WITH_CONCERNS` | Check sub-agent failed to produce output, or autocheck unavailable.   |
| `BLOCKED`            | `next`/`complete` errored, plan stuck, or user declined               |
| `NEEDS_CONTEXT`      | `ingest` rejected the operation                                       |

Loom workdirs live under `/tmp/dojo/<skill-name>/` — ephemeral by design, named
by the skill being created or updated. Re-running
`ingest --op <op> --name <name>` wipes the workdir and starts fresh; previous
runs are not auto-resumed.

## References

- [Authoring rules](references/authoring.md) — directory structure,
  frontmatter, style, completion, freedom, trigger hygiene, instruction
  effectiveness.
- [Workflow conventions](references/workflow-conventions.md) — workflow-skill
  structure, task naming, output construction, prompt templates, step rules.
- [Interface conventions](references/interface-conventions.md) — interface
  skill rules (API tables, branches).
- [Tool conventions](references/tool-conventions.md) — tool skill rules
  (fixed-step sequences).
- [Reference conventions](references/reference-conventions.md) — passive rule
  set conventions.
- [Script conventions](references/script-conventions.md) — script APIs,
  oracles, packaging, rendering, magic constants, producer/consumer contracts.
- [Secure-LLM conventions](references/secure-llm-conventions.md) — when
  sub-agent prompts must inject the secure-llm security frame.
- [Model awareness](references/model-awareness.md) — Claude behaviour
  tendencies and token budget.
- [Plan topology](references/plan-topology.md) — per-operation task DAGs.
