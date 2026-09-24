---
name: project-feature
type: workflow
description: Loomv2-driven feature development pipeline — plan-driven research, design, constrain, task, implement, review — project and language agnostic. Use when the user says "project feature", "project-feature" (legacy alias), "full dev loop", or wants an end-to-end feature pipeline in any repo. Do NOT use for the PADB-specific pipeline — use feature-make instead. Do NOT use for skill creation — use dojo instead.
---

# Project Feature

Drives a feature end-to-end as a loomv2 graph: workspace
intelligence (`project-overview`) and research/design/review
(`project-design`) embedded as SIBLING subgraphs — design's entry
takes exact parameters wired field-by-field from overview's output — → tasks (unbounded ordered pool) →
branch gate → implementation pool loop (single serial lane, one
sub-agent session per task) → verify-tests → review loop → final
gate. Tasks and diff reviews are agent-driven (1 SWE + N domain
reviewers, deterministic tool merge); the human touches the run at
`design/design-gate` (always), `branch-gate` (dirty tree only), and
`final-gate`.

## Dependencies

- `loomv2` — DAG execution engine driving the project-feature graph.
- `project-overview` — workspace-intelligence stage, embedded as
  the `overview` subgraph (entry of the composed plan).
- `project-design` — research/design/review stage, embedded as the
  `design` subgraph, sibling of `overview`. Later stages read
  workspace facts from `${task:overview:...}` directly and
  design artifacts from `${task:design:...}`.
- `tiling` — activity tracking during the run.
- `template` — used internally by prompts (secure-llm frame + role
  prompt).
- `secure-llm` — security frame partial included by every agent
  prompt.

## Parameters

- **description** (required): free-text feature request.
- **workspace** (required): absolute path to the target workspace.
- **build-system** / **test-system** (optional): family overrides
  (e.g. `brazil`, `uv`) that win over manifest detection;
  test-system defaults to build-system.
- **cache-mode** (optional): `read-write` (default), `read-only`,
  `write-only`, or `bypass`.
- **scale** (optional): `s`, `m` (default), or `l` — selects
  `loom/graph-<scale>.yaml`. Controls reviewer panels
  (1 SWE + 2/4/6 domain reviewers) and, inside the embedded
  project-design stage, research questions (2/3/5). The sibling
  project-overview prelude always runs at its own full width
  (unused fan-out self-limits via `skip_output`), and the
  implementation pool loop is identical across scales.

## Commands

Bind these aliases once at the top of the session:

```bash
TK_SKILLS=~/.kiro/skills
TK_LOOM_ROOT=$TK_SKILLS/home/project-feature/loom
TK_TILING=$TK_SKILLS/home/tiling/scripts/run-ttm.sh
TK_EDITOR=$TK_SKILLS/home/editor/scripts/run-editor.sh
TK_LOOM=$TK_SKILLS/home/loomv2/scripts/loom.sh
eval "$($TK_TILING layout build)"
```

## Rules

1. The graph variants (`loom/graph-{s,m,l}.yaml`) MUST stay
   wiring-identical except for fan-out arity; validate every variant
   after any wiring change:
   `$TK_LOOM validate <skill-root> --graph loom/graph-<x>.yaml`.
2. Skill-taught build/test verbs win over the static fallback matrix.
3. Brazil and other AWS-internal build systems enter only via
   `--build-system <name>`, never manifest detection.
4. Review latches (`design/design-review-merge`, `tasks-review-merge`,
   `review-fix`) cap at fuel=5; exhaustion ends the run
   `DONE_WITH_CONCERNS`. The pool latch (`pool-advance`) terminates
   on pool emptiness; its fuel=200 is a runaway net only. Do not
   extend latches without explicit user direction.
5. Review guards live in the `review-diffs-*` prompts;
   `review-diffs-merge` approves only on unanimous approval.

## Workflow

### Step 1: Ingest

1. Set tiling activity:
   ```bash
   $TK_TILING activity set "project-feature(<workspace>): Ingest"
   ```
2. Run the DEFAULT single-call ingest — the loomv2 CLI picks a fresh
   engine-owned workdir under `/tmp/<skill>/<uuid>/`, wipes and
   recreates it unconditionally, and seeds the entry task's
   `input.yaml` in one shot. Capture the printed path on stdout:
   ```bash
   TK_WD=$($TK_LOOM runtime init \
       --loom-root "$TK_LOOM_ROOT" \
       --graph "graph-<scale>.yaml" \
       --set "description=<description>" \
       --set "workspace=<absolute-workspace-path>" \
       --set "build_system_override=<name-or-empty>" \
       --set "test_system_override=<name-or-empty>" \
       --set "cache_mode=<mode-or-read-write>")
   ```
   No per-skill Python or wrapper logic is required — the loomv2 CLI
   owns workdir naming, wipe, init, and entry-task seeding, and never
   needs a `--force` flag. If the entry task cannot be seeded via
   `--set` (for example, the graph's entry task has an `input:`
   mapping in `graph.yaml`), the host skill drops `--set`, passes an
   explicit workdir path (`runtime init "$WD" --loom-root ...`), and
   writes `input.yaml` by hand before the first `runtime next` —
   supported as the escape hatch, not the default.
3. Set tiling activity to Ingest done:
   ```bash
   $TK_TILING activity set "project-feature(<workspace>): Ingest done"
   ```

If `runtime init` fails: NEEDS_CONTEXT.

### Step 2: Drive the loop

1. Set tiling activity:
   ```bash
   $TK_TILING activity set "project-feature(<workspace>): Drive the loop"
   ```
2. Loop until done:
   - Run `$TK_LOOM runtime next "$TK_WD"`.
     Parse the YAML response (shape: loomv2 `schemas/next.yaml`).
   - If the command exits non-zero → BLOCKED; stderr carries
     `{failed_task, error_path}`.
   - If `done: true` → break.
   - Otherwise, handle the `ready[]` batch (all entries are
     `kind: agent|human`; tool tasks already ran inside
     `runtime next`). Entries in one batch are independent:
     - Dispatch every `kind: agent` entry in parallel (see the
       agent-dispatch helper) — these are independent sub-agent
       calls and MUST NOT be serialized.
     - Drive every `kind: human` entry sequentially after the
       agent dispatches (see the human-gate helper) — user
       interaction cannot be parallelized.
     - After each entry finishes, call
       `$TK_LOOM runtime complete "$TK_WD" <task-address>`.
3. Set tiling activity to Done:
   ```bash
   $TK_TILING activity set "project-feature(<workspace>): Done"
   ```

## Helper: Dispatch agent task

`$TK_LOOM runtime next` yields ready agent tasks with
their `prompt_path` already rendered from the task's materialised
`input.yaml`. For each entry, dispatch via the `subagent` MCP tool
with `role: trusted` (grants file-read/write access).

The sub-agent's `prompt_template` should instruct it to `fs_read` the
`prompt_path` and follow it. When a ready entry carries a `model`
field (a graph-declared per-task model hint, e.g. the embedded
`overview/summarise-files-*` slots), pass it through as the subagent
stage's `model`. The agent writes its output to the
`output_path` from the same entry (or via
`$TK_LOOM output add`). After dispatch returns, call
`$TK_LOOM runtime complete "$TK_WD" "<task-address>"`.

Dispatch independent entries in parallel via the `subagent` `stages`
array with no `depends_on`.

Project-feature specifics:

- Unused fan-out slots (the embedded `design/research-q*` and
  `overview/summarise-files-b*`) never surface: their graph entries
  carry `when:` + `skip_output`, so the engine completes them with
  schema-valid empty outputs in-engine.
- Embedded subgraph tasks surface under their instance namespaces:
  project-overview tasks as `overview/<task>` (e.g.
  `overview/detect-domains`) and project-design tasks as
  `design/<task>` (e.g. `design/design-gate`); dispatch and complete
  them by that canonical address exactly as any other task.
- Implementation pool loop: `impl-round` surfaces once per pool task
  (the `pool-advance` latch re-materialises the region until the pool
  drains). Only one round is ever ready; the prompt already carries
  the current task, pool position, and prior-round diff summary. The
  agent reports `applied: true|false` honestly; retry/skip policy is
  enforced by the `pool-advance` tool, never by the host.

## Helper: Drive human gate

Human tasks are conversational. Read the rendered prompt at
`message_path`, follow its instructions, and write structured YAML to
`output_path` against the task's `io.yaml/output` schema (use
`$TK_LOOM output add` for validated writes). Then call
`$TK_LOOM runtime complete "$TK_WD" "<task-address>"`.

For gates that show files, use the editor:

```bash
$TK_EDITOR show file <path>
```

STOP and wait for the user. The user can accept, edit, or decline.
Capture their decision and any edits in the output file before
completing the task.

Project-feature specifics:

- `design/design-gate`: ALWAYS STOP. Write the design body to a temp file,
  show it via `$TK_EDITOR show file`, and wait. Capture the user's
  decision and any decomposition guidance in `note` (it feeds
  tasks-author). On `abort`, stop driving the run → BLOCKED.
- `branch-gate`: when the rendered message says the workspace is
  CLEAN, complete immediately with `decision=proceed` — do NOT stop.
  When DIRTY, STOP and ask the user (clean up / carry changes /
  abort; abort fails `branch-create` → BLOCKED).
- `final-gate`: always STOP and wait for the user.

## Completion

| Status               | Criteria                                                             |
| -------------------- | -------------------------------------------------------------------- |
| `DONE`               | `final-gate.decision == 'accept'`.                                   |
| `DONE_WITH_CONCERNS` | Any review latch exhausted fuel=5.                                   |
| `BLOCKED`            | `final-gate.decision == 'abandon'`, `design/design-gate.decision == 'abort'`, `branch-gate.decision == 'abort'`, or `runtime next` exit non-zero. |
| `NEEDS_CONTEXT`      | Missing description/workspace, or workspace path does not exist.     |
