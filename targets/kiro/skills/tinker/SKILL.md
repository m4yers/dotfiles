---
name: tinker
type: workflow
description: Loomv2-driven feature development pipeline — plan-driven research, design, constrain, task, implement, review — project and language agnostic. Use when the user says "tinker", "tinker feature", "full dev loop", or wants an end-to-end feature pipeline in any repo. Do NOT use for the PADB-specific pipeline — use feature-make instead. Do NOT use for skill creation — use dojo instead.
---

# Tinker

Drives the full feature development pipeline as a loomv2 graph: ingest →
workspace-intelligence prelude (code-inventory, build/test detection, dependency
map, symbol index, `domain-detect`, LLM file summaries, workspace brief) →
research fan-out (3 slots) → design → tasks → implementation fan-out (3 slots) →
verify-tests → review loop → final gate. Project and language agnostic —
build/test verbs are learned from installed `<build_system>-*` skills discovered
by build-detect and test-detect, with a static fallback matrix for Python and
C/C++ toolchains and `--build-system` / `--test-system` overrides for anything
else (Brazil and other AWS-internal systems reach the pipeline only via
override). Prelude results are cached per workspace+commit under
`/tmp/tinker-cache` so re-runs retrieve instead of recompute.

The design/tasks/review-diffs reviews are fully agent-driven: each subject is
reviewed in parallel by one SWE-primed instance plus two domain-primed instances
(roles emitted by `domain-detect`), then aggregated by a deterministic tool
merge that owns the loop's latch role. The human touches the pipeline ONLY at
final-gate.

## Dependencies

- `loomv2` — DAG execution engine driving the tinker graph.
- `tiling` — activity tracking during the run.
- `template` — used internally by prompts (secure-llm frame + role
  prompt).
- `secure-llm` — security frame partial included by every agent
  prompt.

## Parameters

- **description** (required): free-text feature request.
- **workspace** (required): absolute path to the target
  repository/workspace.
- **build-system** (optional): family name override (e.g. `brazil`,
  `uv`, `makefile`) that wins over manifest-based detection.
- **test-system** (optional): test family override; defaults to the
  resolved build system.
- **cache-mode** (optional): `read-write` (default), `read-only`,
  `write-only`, or `bypass` for the workspace-intelligence cache.

## Commands

Bind these aliases once at the top of the session so every step below can
reference them:

```bash
TK_SKILLS=~/.kiro/skills
TK_LOOM_ROOT=$TK_SKILLS/home/tinker/loom
TK_TILING=$TK_SKILLS/home/tiling/scripts/run-ttm.sh
TK_EDITOR=$TK_SKILLS/home/editor/scripts/run-editor.sh
LOOM=$TK_SKILLS/home/loomv2/scripts/loom.sh
```

## Rules

1. Skill-driven build/test verbs win over the static fallback matrix.
   Prompts and `verify-tests` MUST prefer an installed skill's
   `scripts/test.sh` / `scripts/build.sh` shim when one exists for the
   resolved build system.
2. Brazil and other AWS-internal build systems are supported strictly
   via `--build-system <name>` at ingest — never through manifest
   detection.
3. Loop latches (`design-review-merge`, `tasks-review-merge`,
   `review-fix`) cap at fuel=5. Fuel exhaustion terminates the run
   with `DONE_WITH_CONCERNS`. The loop MUST NOT be extended without
   explicit user direction because latch expansion bypasses the
   fuel-based runaway-cutoff. Latch headers live in
   `loom/graph.yaml` `latches:`.
4. Review guards are enforced in their sites: each `review-diffs-*`
   prompt carries the three approval guards, and
   `review-diffs-merge` approves only on unanimous reviewer
   approval.

## Workflow

### Step 1: Ingest

1. Set tiling activity and build layout:
   ```bash
   $TK_TILING activity set "tinker(<workspace>): Ingest"
   eval "$($TK_TILING layout build)"
   ```
2. Ingest — init the loom workdir directly. `workspace` MUST be an
   absolute path to an existing directory; `build_system_override` is
   always set, empty when no override was given:
   ```bash
   TK_WD=$($LOOM runtime init --loom-root "$TK_LOOM_ROOT" \
       --set "description=<description>" \
       --set "workspace=<absolute-workspace-path>" \
       --set "build_system_override=<name-or-empty>" \
       --set "test_system_override=<name-or-empty>" \
       --set "cache_mode=<mode-or-read-write>")
   ```
3. If `runtime init` fails: NEEDS_CONTEXT.
4. On success: proceed to Step 2.

### Step 2: Drive the loop

1. Set tiling activity:
   ```bash
   $TK_TILING activity set "tinker(<workspace>): Drive the loop"
   ```
2. Ask loom for the next batch of ready tasks and parse the YAML
   response:
   ```bash
   $LOOM runtime next "$TK_WD"
   ```
   If `done: true`, mark the run finished and exit the loop:
   ```bash
   $TK_TILING activity set "tinker(<workspace>): Done"
   ```
   If `stuck: true`, return BLOCKED.
3. For each `ready[].id`, dispatch by `kind`:
   - `kind == human` → drive the human gate (see helper).
   - `kind == agent` → dispatch the sub-agent (see helper).
   - Independent ids in one batch can be dispatched in parallel.
4. Mark each dispatched id complete after its body finishes:
   ```bash
   $LOOM runtime complete "$TK_WD" <id>
   ```
5. Return to sub-step 2.

## Helper: Dispatch agent task

`$LOOM runtime next` yields ready agent tasks with their `prompt_path` already
rendered. For each id, dispatch via the `subagent` MCP tool with `role: trusted`
(grants file-read/write access).

Unused fan-out slot short-circuit: the slot tasks (`research-q1..q3`,
`impl-t1..t3`, `file-summary-b1..b4`) always run; when a slot's materialised
`input.yaml` carries an empty `question` / empty `task.title` / empty `files`
list, do NOT spawn a sub-agent — write the empty output directly (`--set-json`
empty values per the task's io.yaml) and complete it.

The sub-agent's `prompt_template` should instruct it to `fs_read` the
`prompt_path` and follow it. The agent writes its output to the `output_path`
(also in the `next` response). After dispatch returns, call `$LOOM runtime
complete "$TK_WD" "<id>"`.

Dispatch independent ids in parallel via the `subagent` `stages` array with no
`depends_on`.

## Helper: Drive human gate

Human tasks are conversational. Read the rendered prompt at `message_path`,
follow its instructions, and write structured YAML to `output_path` against the
gate's schema. Then call `$LOOM runtime complete "$TK_WD" "<id>"`. In the
current graph, the ONLY human gate is `final-gate` — the design and tasks review
loops are fully agent-driven with a deterministic tool merge at each subject's
latch point.

Construct `output_path` via loom's writer (schema-checked) rather than free-form
`fs_write`, e.g. for `final-gate`:

```bash
$LOOM output init "$TK_WD" --task final-gate
$LOOM output add  "$TK_WD" --task final-gate \
    --set decision=<accept|abandon> \
    --set note='<optional note>'
```

Do not spawn a sub-agent for human gates.

For gates that show files, use the editor:

```bash
$TK_EDITOR show file <path>
```

STOP and wait for the user. The user can accept, edit, or decline. Capture their
decision and any edits in the output file before completing the task.

## Completion

| Status               | Criteria                                                             |
| -------------------- | -------------------------------------------------------------------- |
| `DONE`               | `final-gate.decision == 'accept'`.                                   |
| `DONE_WITH_CONCERNS` | Any loop latch exhausted fuel=5.                                     |
| `BLOCKED`            | `final-gate.decision == 'abandon'`, or `runtime next` exit non-zero. |
| `NEEDS_CONTEXT`      | Missing description/workspace, or workspace path does not exist.     |
