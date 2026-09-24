---
name: notepad
type: workflow
description: Interactive notepad session — sets up the standard layout, creates a temp notebook dir with a notepad.md, opens it in the editor, and waits for user commands. Use when the user says "notepad", "open notepad", "notebook session", or wants an interactive scratch session where questions are answered inline and actions are executed in per-action sub-folders and logged to the notebook. Do NOT use for skill creation — use dojo instead. Do NOT use for editor-only operations — use editor instead.
---

# Notepad

Drives loom to run an interactive scratch notebook session. Sets up the standard
tiling layout, seeds a per-session notebook directory with a `notepad.md`, opens
it in the editor, and enters a loop over user commands — answering questions
inline and executing actions in numbered sub-folders while appending outcomes to
the notebook.

## Dependencies

- `loom` — DAG execution library
- `tiling` — pane layout and activity tracking
- `editor` — used to open the session's `notepad.md` in the EDITOR pane
- `template` — used by `ingest` to render the seed `notepad.md`

## Parameters

- **(none)** — the skill takes no invocation parameters. Subsequent user
  messages inside the session become the interactive commands.

## Workflow

### Step 1: Ingest

1. Set up tooling aliases:
   ```bash
   NOTEPAD=~/.kiro/skills/home/notepad/scripts/notepad.sh
   TILING=~/.kiro/skills/home/tiling/scripts/run-ttm.sh
   EDITOR=~/.kiro/skills/home/editor/scripts/run-editor.sh
   ```
2. Set tiling activity and build layout:
   ```bash
   $TILING activity set "notepad: Ingest"
   eval "$($TILING layout build)"
   ```
3. Ingest:
   ```bash
   NP_WD=$($NOTEPAD ingest)
   ```
4. If `ingest` fails: NEEDS_CONTEXT. On success: proceed to Step 2.

### Step 2: Drive the loop


1. Set tiling activity:
   ```bash
   $TILING activity set "notepad: Drive the loop"
   ```
2. Loop until done:
   - Run `$NOTEPAD next "$NP_WD"`.
     Parse the YAML response.
   - If `done: true` → break.
   - If `stuck: true` → BLOCKED.
   - Otherwise, for each `ready[].id`:
     - If `kind == human` → drive the human gate (see helper). After
       completing `command-wait`, inspect its output: if the user
       classified their command as `question`, answer inline in this
       response and append the exchange to `${NP_WD}/notepad.md` — no
       sub-agent runs. Loom's `when:` guard on `command-process` skips
       it for non-action commands.
     - If `kind == agent` → dispatch the sub-agent (see helper). Only
       `command-process` for `kind == 'action'` reaches this branch.
     - Then `$NOTEPAD complete "$NP_WD" <id>`.
   - Independent ids in one batch can be dispatched in parallel.
3. Set tiling activity to Done:
   ```bash
   $TILING activity set "notepad: Done"
   ```


## Helper: Dispatch agent task


`$NOTEPAD next` yields ready agent tasks with their `prompt_path` already
rendered. For each id, dispatch via the `subagent` MCP tool with `role: trusted`
(grants file-read/write access).

The sub-agent's `prompt_template` should instruct it to `fs_read` the
`prompt_path` and follow it. The agent writes its output to the `output_path`
(also in the `next` response). After dispatch returns, call `$NOTEPAD complete
"$NP_WD" "<id>"`.

Dispatch independent ids in parallel via the `subagent` `stages` array with no
`depends_on`.


## Helper: Drive human gate


Human tasks are conversational. Read the rendered prompt at `prompt_path`,
follow its instructions, and write structured YAML to `output_path` against the
schema. Then call `$NOTEPAD complete "$NP_WD" "<id>"`.

For gates that show files, use the editor:

```bash
$EDITOR show file <path>
```

STOP and wait for the user. The user can accept, edit, or decline. Capture their
decision and any edits in the output file before completing the task.


## Rules

1. Intermediate files for an `action` command MUST live under that action's
   `NN-<slug>/` sub-folder.
2. `question` commands MUST NOT create sub-folders because they produce no
   artefacts and would leave orphan directories under the workdir.
3. The session ends when the operator classifies a command as `end`. Loom's
   `when:`/`latch` predicate then skips `command-process` and exits the loop.
4. A failed task aborts the whole run. Loom's `next()` raises `RunAborted`;
   the orchestrator reports the failure and stops.
5. Spawn sub-agents only for tasks where loom yields `kind == agent`. Human
   gates and orchestrator bash run inline.


## Plan visualisation

```
PLAN  ·  4 tasks

↻  04 command-process   ↻ loop → command-wait · while …   when: ${task:command-wait:kind} == 'action'
▣  03 command-wait
○  02 editor-open
○  01 setup-layout

legend: ○ tool · ◆ agent · ▣ human · ↻ loop   │ all-dep · ╷ any-dep   when:/↻ inline
```


## Completion

| Status               | Criteria                                                              |
|----------------------|-----------------------------------------------------------------------|
| `DONE`               | `notepad.md` written with per-command entries; loom run marked done.  |
| `DONE_WITH_CONCERNS` | Some `action` tasks flagged partial or degraded outcomes in notepad.  |
| `BLOCKED`            | A task failed, plan is stuck, or user declined at a human gate.       |
| `NEEDS_CONTEXT`      | `ingest` failed to create the workdir or initialise loom.             |
