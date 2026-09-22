---
name: project-overview
type: workflow
description: Loomv2-driven workspace intelligence for any repository — code inventory, build/test-system detection, dependency map, symbol index, domain detection with reviewer roles, LLM file summaries, and a consolidated project brief, cached per workspace+commit. Use when the user says "project overview", "workspace intelligence", "analyze this repo", "analyze this workspace", "what is this project". Do NOT use for feature implementation — use tinker instead.
---

# Project Overview

Drives workspace intelligence end-to-end as a loomv2 graph: overview-ingest
→ code-inventory + build-detect + dep-analysis + symbol-index (parallel) →
test-detect (after build-detect) → code-analysis-plan → file-summary fan-out
(ref-instanced slots b1..bN gated by `when:` + `skip_output`) → domain-detect
→ workspace-brief → overview-exit. The exit task aggregates the cross-cutting
context envelope (workspace_abs, feature_slug, description echo, build_system
with installed_skills and fallback_build_cmd, test_system with installed_skills
and fallback_test_cmd, workspace_brief, domains[] with reviewer_role sentences,
cache identity) into one output document — the run's final report. All heavy
lifting is deterministic tool work; only domain-detect and the file-summary
slots are agent tasks.

## Dependencies

- `loomv2` — DAG execution engine driving the project-overview graph.
- `cache` — content-addressed key/value cache backing every per-task
  doc (`<cache_prefix>/<task>`) and per-file summary blob
  (`<blob_prefix>/<content-sha>`). The cache skill owns slug
  derivation, atomic writes, mode gating, and LRU retention; this
  skill wires no `cache gc` and creates no cache directories itself.
- `tiling` — activity tracking during the run.
- `template` — used internally by prompts (secure-llm frame + role
  prompt).
- `secure-llm` — security frame partial included by every agent
  prompt.

## Parameters

- **description** (required): free-text label for this overview run
  (used to derive the feature slug on the envelope).
- **workspace** (required): absolute path to the target repository.
- **build-system** / **test-system** (optional): family overrides
  (e.g. `brazil`, `uv`) that win over manifest detection; test-system
  defaults to build-system.
- **cache-mode** (optional): `read-write` (default), `read-only`,
  `write-only`, or `bypass`.
- **scale** (optional): `s`, `m` (default), or `l` — selects
  `loom/graph-<scale>.yaml`. Controls domain capacity and file-summary
  batch count: 2/2 (s), 4/4 (m), 6/6 (l).

## Commands

Bind these aliases once at the top of the session:

```bash
PO_SKILLS=~/.kiro/skills
PO_LOOM_ROOT=$PO_SKILLS/home/project-overview/loom
PO_TILING=$PO_SKILLS/home/tiling/scripts/run-ttm.sh
PO_LOOM=$PO_SKILLS/home/loomv2/scripts/loom.sh
```

## Rules

1. The graph variants (`loom/graph-{s,m,l}.yaml`) MUST stay wiring-identical except for fan-out arity (domain-detect
   `max_domains`, code-analysis-plan `max_batches`, and the file-summary
   slot count); validate every variant after any wiring change:
   `$PO_LOOM validate <skill-root> --graph loom/graph-<x>.yaml`.

## Workflow

### Step 1: Ingest

1. Set tiling activity:
   ```bash
   $PO_TILING activity set "project-overview(<workspace>): Ingest"
   ```
2. Run `runtime init` to prepare the workdir and seed the entry
   task; capture the printed path:
   ```bash
   PO_WD=$($PO_LOOM runtime init \
       --loom-root "$PO_LOOM_ROOT" \
       --graph "graph-<scale>.yaml" \
       --set "description=<description>" \
       --set "workspace=<absolute-workspace-path>" \
       --set "build_system_override=<name-or-empty>" \
       --set "test_system_override=<name-or-empty>" \
       --set "cache_mode=<mode-or-read-write>")
   ```
   See `~/.kiro/skills/home/loomv2/SKILL.md` for workdir semantics and
   the escape hatch when the entry task has a graph-level `input:`
   mapping.
3. Set tiling activity to Ingest done:
   ```bash
   $PO_TILING activity set "project-overview(<workspace>): Ingest done"
   ```

If `runtime init` fails: NEEDS_CONTEXT. On success: proceed to Step 2.

### Step 2: Drive the loop

1. Set tiling activity:
   ```bash
   $PO_TILING activity set "project-overview(<workspace>): Drive the loop"
   ```
2. Loop until done:
   - Run `$PO_LOOM runtime next "$PO_WD"`.
     Parse the YAML response (shape: loomv2 `schemas/next.yaml`).
   - If the command exits non-zero → BLOCKED; stderr carries
     `{failed_task, error_path}`.
   - If `done: true` → break.
   - Otherwise, handle the `ready[]` batch (all entries are
     `kind: agent|human`; tool tasks already ran inside
     `runtime next`). Entries in one batch are independent:
     - Dispatch every `kind: agent` entry in parallel (see the
       agent-dispatch helper) — these are independent sub-agent
       calls and MUST NOT be serialized because that erases the
       parallelism the graph already declared.
     - Drive every `kind: human` entry sequentially after the
       agent dispatches (see `~/.kiro/skills/home/loomv2/SKILL.md`
       for the human-gate protocol) — user interaction cannot be
       parallelized.
     - After each entry finishes, call
       `$PO_LOOM runtime complete "$PO_WD" <task-address>`.
3. Set tiling activity to Done:
   ```bash
   $PO_TILING activity set "project-overview(<workspace>): Done"
   ```

On `done: true`: proceed to Step 3.

### Step 3: Read the envelope

1. Set tiling activity:
   ```bash
   $PO_TILING activity set "project-overview(<workspace>): Read the envelope"
   ```
2. Read the final envelope from the overview-exit `output.yaml`
   under `$PO_WD/tasks/` and present it as the report: build/test
   systems and their skill shims, workspace brief, domains with
   reviewer roles, cache identity.

## Helper: Dispatch agent task

`$PO_LOOM runtime next` yields ready agent tasks with
their `prompt_path` already rendered from the task's materialised
`input.yaml`. For each entry, dispatch via the `subagent` MCP tool
with `role: trusted` (grants file-read/write access).

The sub-agent's `prompt_template` should instruct it to `fs_read` the
`prompt_path` and follow it. The agent writes its output to the
`output_path` from the same entry (or via
`$PO_LOOM output add`). After dispatch returns, call
`$PO_LOOM runtime complete "$PO_WD" "<task-address>"`.

Dispatch independent entries in parallel via the `subagent` `stages` array with
no `depends_on`.

project-overview specifics:

- The only agent tasks in the graph are `domain-detect` and the
  ref-instanced `file-summary-b*` slots. Unused `file-summary-b*`
  slots never surface as ready — their graph entries carry `when:` +
  `skip_output`, so the engine completes them with schema-valid
  empty outputs in-engine.
- Multiple file-summary slots may be ready in the same `next` batch;
  dispatch them in parallel.

## Completion

| Status               | Criteria                                                         |
| -------------------- | ---------------------------------------------------------------- |
| `DONE`               | `runtime next` returned `done: true` and envelope produced.      |
| `DONE_WITH_CONCERNS` | Envelope produced; a file-summary slot returned an empty output. |
| `BLOCKED`            | `runtime next` exits non-zero (stderr carries `failed_task`).    |
| `NEEDS_CONTEXT`      | Missing description/workspace or `runtime init` failed.          |
