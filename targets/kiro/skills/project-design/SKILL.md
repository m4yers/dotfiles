---
name: project-design
type: workflow
description: Loomv2-driven research/design/review pipeline — workspace intelligence, research fan-out, design authoring, multi-role review loop, human design gate — project and language agnostic. Use when the user says "project design", "design this feature", "research and design", or wants a reviewed design document without implementation. Do NOT use for the full dev loop with implementation — use project-feature instead. Do NOT use for workspace analysis alone — use project-overview instead.
---

# Project Design

Produces a reviewed, human-approved design document as a loomv2
graph: `ingest-input` (entry declaring the EXACT parameters the
pipeline consumes: description, workspace_abs, build_system,
build_installed_skills, fallback_build_cmd, fallback_test_cmd,
domains, summaries_store, summaries_usage) → research plan +
question fan-out →
research merge → design author → review panel (1 SWE + N domain
reviewers + citation-check tool, deterministic merge, revise latch)
→ `design-gate` (human, always-stop) → `publish-output` (exit: the approved
design, decisions, open risks, research report, and the gate note —
design artifacts only; workspace facts stay on the sibling
overview).

project-overview is a SIBLING skill, not an embed: standalone runs
pre-run it and seed the entry fields from its output; embedded
runs (as in `project-feature`) wire each field from a sibling
overview instance (`${task:overview:<field>}`). Either way the
parent addresses everything via `${task:<instance>:...}` on the
exit contract.

## Dependencies

- `loomv2` — DAG execution engine.
- `project-overview` — sibling skill producing the output this
  graph consumes (pre-run standalone; sibling instance when
  embedded).
- `tiling` — activity tracking during the run.
- `template` / `secure-llm` — prompt rendering + security frame.

## Parameters

- **description** (required): free-text feature/problem statement.
- **workspace** (required): absolute path to the target workspace.
- **build-system** / **test-system** (optional): family overrides.
- **cache-mode** (optional): `read-write` (default), `read-only`,
  `write-only`, or `bypass`.
- **scale** (optional): `s`, `m` (default), or `l` — selects
  `loom/graph-<scale>.yaml`: research questions 2/3/5, reviewer
  panels 1 SWE + 2/4/6 domain reviewers.

## Commands

```bash
PD_SKILLS=~/.kiro/skills
PD_LOOM_ROOT=$PD_SKILLS/home/project-design/loom
PD_TILING=$PD_SKILLS/home/tiling/scripts/run-ttm.sh
PD_EDITOR=$PD_SKILLS/home/editor/scripts/run-editor.sh
PD_LOOM=$PD_SKILLS/home/loomv2/scripts/loom.sh
eval "$($PD_TILING layout build)"
```

## Rules

1. The graph variants (`loom/graph-{s,m,l}.yaml`) MUST stay
   wiring-identical except for fan-out arity; validate every variant
   after any wiring change:
   `$PD_LOOM validate <skill-root> --graph loom/graph-<x>.yaml`.
2. The design latch (`design-review-merge`) caps at fuel=5;
   exhaustion ends the run `DONE_WITH_CONCERNS`. Do not extend
   without explicit user direction.
3. The entry contract (`ingest-input/io.yaml`) declares exactly
   the fields the pipeline consumes; when a task needs a new
   workspace fact, add it there (and to the parent wiring) rather
   than widening any field to an opaque object.

## Workflow

### Step 1: Ingest

1. `$PD_TILING activity set "project-design(<workspace>): Ingest"`
2. Run project-overview to completion first (its SKILL.md workflow;
   warm-cached per workspace+commit), capture its output:
   ```bash
   OV_WD=<workdir of the completed project-overview run>
   ENV_YAML=$(ls $OV_WD/tasks/*publish-output/output.yaml)
   ```
3. Init with an explicit workdir and seed the entry input by hand
   (the documented escape hatch — the entry task takes a full
   object, not scalar `--set`s):
   ```bash
   PD_WD=/tmp/project-design/$(uuidgen | cut -c1-12)
   $PD_LOOM runtime init "$PD_WD" \
       --loom-root "$PD_LOOM_ROOT" \
       --graph "graph-<scale>.yaml"
   python3 -c "
   import yaml
   env = yaml.safe_load(open('$ENV_YAML'))
   fields = ['description', 'workspace_abs', 'build_system',
             'build_installed_skills', 'fallback_build_cmd',
             'fallback_test_cmd', 'domains', 'summaries_store',
             'summaries_usage']
   yaml.safe_dump({f: env[f] for f in fields},
                  open('$PD_WD/tasks/01-ingest-input/input.yaml', 'w'))
   "
   ```
4. `$PD_TILING activity set "project-design(<workspace>): Ingest done"`

If `runtime init` fails or the overview run is missing: NEEDS_CONTEXT.

### Step 2: Drive the loop

1. `$PD_TILING activity set "project-design(<workspace>): Drive"`
2. Loop until done:
   - `$PD_LOOM runtime next "$PD_WD"`; non-zero exit → BLOCKED.
   - `done: true` → break.
   - Dispatch ready `kind: agent` entries in parallel via the
     `subagent` tool (`role: trusted`; forward any `model` hint);
     drive `kind: human` entries sequentially; after each,
     `$PD_LOOM runtime complete "$PD_WD" <task-address>`.
   - After every wave: verify each dispatched agent's declared
     `output_path` exists on disk before completing; re-dispatch
     silent failures.
3. `$PD_TILING activity set "project-design(<workspace>): Done"`

## Helper: Drive human gate

- `design-gate`: ALWAYS STOP. Show the design via
  `$PD_EDITOR show file <path>`, wait for the user, capture their
  decision and guidance note in the output, then complete.

## Completion

| Status               | Criteria                                          |
| -------------------- | ------------------------------------------------- |
| `DONE`               | `publish-output` completed (gate accepted).       |
| `DONE_WITH_CONCERNS` | Design latch exhausted fuel=5.                    |
| `BLOCKED`            | `design-gate.decision == \'abort\'` or `runtime next` non-zero. |
| `NEEDS_CONTEXT`      | Missing description/workspace, or path invalid.   |
