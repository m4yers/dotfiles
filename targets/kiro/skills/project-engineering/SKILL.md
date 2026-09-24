---
name: project-engineering
type: workflow
description: Loomv2-driven tasks/implementation/code-review pipeline — task decomposition with review loop, branch setup, serial implementation pool, verify-tests, multi-role diff review with fix loop, human final gate — project and language agnostic. Use when the user says "project engineering", "implement this design", or has an approved design ready to build. Do NOT use for research/design — use project-design instead. Do NOT use for the full dev loop — use project-feature instead.
---

# Project Engineering

Implements an approved design as a loomv2 graph: `ingest-input`
(exact parameters: design + note, workspace, build/test env, six
reviewer personas) → tasks-author → tasks review panel (latch,
fuel 5) → workspace-guard → `branch-gate` (human; auto-proceed when
clean) → branch-create → implementation pool loop (pool-draw →
impl-round → pool-advance; one sub-agent session per task; fuel 200
runaway net) → verify-tests → diff review panel → review-fix (latch
back to verify-tests, fuel 5 — fixes are re-verified and
re-reviewed) → `final-gate` (human, always-stop) → `publish-output`
(branch, counts, verdicts, final decision).

This skill is self-contained: it declares its inputs and knows
nothing about which skill produces them. Standalone runs seed the
entry fields directly; a composing parent graph (the only place
skills connect) wires them from whatever siblings emit compatible
fields.

## Dependencies

- `loomv2` — DAG execution engine.
- `tiling` — activity tracking during the run.
- `template` / `secure-llm` — prompt rendering + security frame.
- `git` — staging-commit discipline inside the implementation pool.

## Parameters

The graph's entry contract (`loom/ingest-input/io.yaml`) — all
required, seeded into the entry task's `input.yaml`:

- **design** / **design_note**: the approved design document and
  the human guidance note that accompanied its approval.
- **workspace_abs** / **feature_slug**: where to implement and the
  branch identifier.
- **build_system** / **test_system** / **build_installed_skills** /
  **test_installed_skills** / **fallback_build_cmd** /
  **fallback_test_cmd**: how to build and test.
- **reviewer_role_d1..d6**: six reviewer personas (scale variants
  use the first 2/4/6).

Driver-level:

- **scale** (optional): `s`, `m` (default), or `l` — selects
  `loom/graph-<scale>.yaml`: reviewer panels 1 SWE + 2/4/6.

## Commands

```bash
PE_SKILLS=~/.kiro/skills
PE_LOOM_ROOT=$PE_SKILLS/home/project-engineering/loom
PE_TILING=$PE_SKILLS/home/tiling/scripts/run-ttm.sh
PE_EDITOR=$PE_SKILLS/home/editor/scripts/run-editor.sh
PE_LOOM=$PE_SKILLS/home/loomv2/scripts/loom.sh
eval "$($PE_TILING layout build)"
```

## Rules

1. The graph variants (`loom/graph-{s,m,l}.yaml`) MUST stay
   wiring-identical except for reviewer fan-out arity; validate all
   three after any wiring change.
2. Review latches (`tasks-review-merge`, `review-fix`) cap at
   fuel=5; exhaustion ends the run `DONE_WITH_CONCERNS`. The pool
   latch (`pool-advance`) terminates on pool emptiness; its
   fuel=200 is a runaway net only.
3. `review-diffs-merge` approves only on unanimous approval; the
   review-fix latch re-enters at verify-tests so every fix round is
   re-built, re-tested, and re-reviewed.
4. Never push or publish from this pipeline; it ends at a local
   branch and the human final gate.

## Workflow

### Step 1: Ingest

1. `$PE_TILING activity set "project-engineering(<workspace>): Ingest"`
2. Obtain values for the entry parameters (an approved design plus
   workspace/build facts from any compatible source; ask the user
   if unavailable) and write them to a YAML file matching
   `loom/ingest-input/io.yaml` input schema.
3. ```bash
   PE_WD=/tmp/project-engineering/$(uuidgen | cut -c1-12)
   $PE_LOOM runtime init "$PE_WD" \
       --loom-root "$PE_LOOM_ROOT" \
       --graph "graph-<scale>.yaml"
   cp <params>.yaml "$PE_WD/tasks/01-ingest-input/input.yaml"
   ```
4. `$PE_TILING activity set "project-engineering(<workspace>): Ingest done"`

If `runtime init` fails or parameters are unavailable: NEEDS_CONTEXT.

### Step 2: Drive the loop

1. `$PE_TILING activity set "project-engineering(<workspace>): Drive"`
2. Loop until done:
   - `$PE_LOOM runtime next "$PE_WD"`; non-zero exit → BLOCKED.
   - `done: true` → break.
   - Dispatch ready `kind: agent` entries in parallel via the
     `subagent` tool (`role: trusted`; forward any `model` hint);
     drive `kind: human` entries sequentially; after each,
     `$PE_LOOM runtime complete "$PE_WD" <task-address>`.
   - After every wave: verify each dispatched agent's declared
     `output_path` exists on disk before completing; re-dispatch
     silent failures.
   - Implementation pool: `impl-round` surfaces once per pool task;
     the agent reports `applied: true|false` honestly; retry/skip
     policy is enforced by `pool-advance`, never by the host.
3. `$PE_TILING activity set "project-engineering(<workspace>): Done"`

## Helper: Drive human gate

- `branch-gate`: when the rendered message says the workspace is
  CLEAN, complete immediately with `decision=proceed` — do NOT
  stop. When DIRTY, STOP and ask the user (clean up / carry
  changes / abort; abort fails branch-create → BLOCKED).
- `final-gate`: always STOP. Show the diff bundle and review
  summary via `$PE_EDITOR show file <path>`, wait for the user,
  capture decision + note, then complete.

## Completion

| Status               | Criteria                                            |
| -------------------- | --------------------------------------------------- |
| `DONE`               | `final-gate.decision == 'accept'`.                  |
| `DONE_WITH_CONCERNS` | `tasks-review-merge` or `review-fix` latch exhausted fuel=5. |
| `BLOCKED`            | `final-gate.decision == 'abandon'`, `branch-gate.decision == 'abort'`, or `runtime next` non-zero. |
| `NEEDS_CONTEXT`      | Entry parameters unavailable.                       |
