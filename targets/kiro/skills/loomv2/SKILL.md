---
name: loomv2
type: interface
description: Loom v2 — DAG task-execution library. Tasks are self-contained folders with io.yaml IO contracts, composed into graphs (including cross-skill subgraphs) via graph.yaml. Use when a skill needs to define or drive a DAG of tool, agent, and human tasks. Do NOT use for the legacy Python-API loom — use loom instead.
---

# Loom v2

Loom v2 executes graphs of tasks. A task is a self-contained folder with a
declared IO contract; a graph wires tasks together and can embed graphs from
other skills. Loom owns ordering, validation, and persistence. The skill using
loom drives the run loop and executes the agent and human tasks loom surfaces.

**Contract-locality:** a task sees only its own `io.yaml` interface — the
validated `input.yaml` it reads and the `output.yaml` it writes. Cross-task
data flows only through the `input:` block on each `graph.yaml` task entry,
which the engine resolves at dispatch and materialises into that task's
`input.yaml`. There is no shared state between tasks, so every run is replayable
from the recorded inputs.

**Parallel-dispatch:** agent entries in the same `ready` batch surfaced by
`runtime next` are independent by DAG construction and MUST be dispatched in
parallel — host skills MUST NOT serialize them, because serial dispatch drops
the DAG's concurrency guarantee and inflates end-to-end latency for no gain.
Tool tasks never appear in `ready` (loom runs them internally); human gates
surface one message at a time.

## Invocation

```bash
LOOM=~/.kiro/skills/home/loomv2/scripts/loom.sh
$LOOM <group> <command> [options]
```

## API

Consumer surface is the CLI, grouped by command family.

### runtime

| Command            | Args                                                   | Output             |
|--------------------|--------------------------------------------------------|--------------------|
| `runtime init`     | `[<workdir>] --loom-root PATH [--set K=V ...]`         | workdir path       |
| `runtime next`     | `<workdir>`                                            | YAML: done + ready |
| `runtime complete` | `<workdir> <task-address>`                             | validates output   |
| `runtime fail`     | `<workdir> <task-address> --message T`                 | writes error.yaml  |
| `runtime reset`    | `<workdir> <task-address>`                             | region-aware reset |
| `runtime status`   | `<workdir>`                                            | totals + counts    |

### task

| Command          | Args                        | Output                            |
|------------------|-----------------------------|-----------------------------------|
| `task new`       | `<name> [--loom-root PATH]` | creates task folder (empty)       |
| `task io-python` | `<name> [--loom-root PATH]` | writes `io_types.py` from io.yaml |

### graph

| Command     | Args                 | Output                            |
|-------------|----------------------|-----------------------------------|
| `graph new` | `[--loom-root PATH]` | scaffolds or re-pins `graph.yaml` |

### output

| Command       | Args                                                         | Output            |
|---------------|--------------------------------------------------------------|-------------------|
| `output init` | `<workdir> --task <task-address>`                            | seeds output.yaml |
| `output add`  | `<workdir> --task <task-address> --set K=V [--set-json K=V]` | validated write   |

`output add` accepts `--set` (scalar with bool/int/float coercion) and
`--set-json` (value parsed as JSON) — use `--set-json` for explicit empty values
(`items=[]`, `note=""`, `owner=null`) and nested structures the scalar grammar
cannot express. Required by the io.md contract-soundness rule: when data may
be absent, the producer emits the explicit empty value — never omitting a
required field.

### misc

| Command     | Args                              | Output    |
|-------------|-----------------------------------|-----------|
| `validate`  | `<skill-root> [--graph PATH]`     | non-zero  |
| `visualise` | `<workdir>|--plan PATH [options]` | ASCII DAG |

`validate --graph PATH` targets a `graph.yaml`; `visualise --plan PATH` targets
a `plan.yaml`. The flag names are distinct so callers cannot cross-feed the two
file shapes. `visualise` takes exactly one of `<workdir>` or `--plan PATH`; the
`[options]` placeholder covers `-o PATH` (write to file), `--no-when` /
`--no-loops` (omit annotations), and `--ascii-only` (7-bit output). Full
per-flag semantics live under `visualise` in
[references/commands.md](references/commands.md).

## Commands

Per-command contracts, flags, error paths, and edge-case notes live in
[references/commands.md](references/commands.md). The ### subsections below
name each command in the API table; follow the link for the full contract.

### runtime init

- Purpose: builds the workdir on top of `<loom-root>/graph.yaml`.
- Default form: `WD=$($LOOM runtime init --loom-root "$LOOM_ROOT"
  [--set K=V ...])` — workdir positional omitted, engine picks
  `/tmp/<skill_name>/<uuid4-hex-12>/` and prints it on stdout.
- Explicit form: `$LOOM runtime init "$WORKDIR" --loom-root
  "$LOOM_ROOT" [--set K=V ...]` — the caller names the workdir; the
  engine still wipes and recreates it.
- Contract: [commands.md#runtime-init](references/commands.md#runtime-init).

### runtime next

- Purpose: runs tool tasks internally and prints a
  [`schemas/next.yaml`](schemas/next.yaml) doc with the next `ready` batch.
- Contract: [commands.md#runtime-next](references/commands.md#runtime-next).

### runtime complete

- Purpose: validates `output.yaml` against `io.yaml/output`, marks done,
  and runs any loop-latch decision.
- Contract:
  [commands.md#runtime-complete](references/commands.md#runtime-complete).

### runtime fail

- Purpose: marks a task failed and writes `error.yaml` from a
  caller-supplied message.
- Contract: [commands.md#runtime-fail](references/commands.md#runtime-fail).

### runtime reset

- Purpose: region-aware reset — flips a task to `pending`, clears
  generated artefacts, resets the loop region when inside a body.
- Contract: [commands.md#runtime-reset](references/commands.md#runtime-reset).

### runtime status

- Purpose: read-only YAML summary — `total`, `is_done`, `is_stuck`, and
  per-status counts.
- Contract:
  [commands.md#runtime-status](references/commands.md#runtime-status).

### task new

- Purpose: creates an empty task folder for author-written body files.
- Contract: [commands.md#task-new](references/commands.md#task-new).

### task io-python

- Purpose: regenerates `io_types.py` from the task's `io.yaml`.
- Contract:
  [commands.md#task-io-python](references/commands.md#task-io-python).

### graph new

- Purpose: scaffolds `graph.yaml` from task folders or restamps every
  entry's `version` from the current `io.yaml` (idempotent).
- Contract: [commands.md#graph-new](references/commands.md#graph-new).

### output init

- Purpose: seeds `<workdir>/tasks/<task-address>/output.yaml` from the
  task's `io.yaml/output` defaults.
- Contract: [commands.md#output-init](references/commands.md#output-init).

### output add

- Purpose: applies dotted-path assignments to `output.yaml`;
  partial-validates so callers can build the document across many calls.
- Contract: [commands.md#output-add](references/commands.md#output-add).

### validate

- Purpose: runs static validation (references, subtype, DAG,
  single-entry/exit, templates, tool-entry, loop admission) against a
  skill's `loom/` folder.
- Contract: [commands.md#validate](references/commands.md#validate).

### visualise

- Purpose: renders `plan.yaml` (or a stand-alone `--plan PATH`) as an
  ASCII DAG.
- Contract: [commands.md#visualise](references/commands.md#visualise).

## Defaults

| Command family                            | `--loom-root` default |
|-------------------------------------------|-----------------------|
| `task new`, `task io-python`, `graph new` | `./loom`              |
| `runtime init`                            | required (no default) |

`runtime init` has no default because the initial workdir MUST be pinned to an
explicit source graph — the flag is unbracketed in the API table. Auto-workdir
path derivation and the unconditional wipe-and-recreate contract live under
### runtime init above and in
[references/commands.md](references/commands.md#runtime-init).

## References

- `references/guide.md` — step-by-step guide for building a loom skill;
  `references/hello-graph/` is the finished reference skill it builds.
- `references/commands.md` — per-command CLI contracts.
- `references/grammar.md` — placeholder grammar table.
- `references/io.md` — io.yaml contract: version, input/output blocks,
  `$ref` convention, and the two reserved default objects (`__loom`,
  `__task`).
- `schemas/loom-meta.yaml` — canonical shape of the `__loom` reserved
  input object.
- `schemas/task-meta.yaml` — canonical shape of the `__task` reserved
  input object.
- `templates/step-drive-loop.md.j2` — host-skill workflow step: the
  next/dispatch/complete loop.
- `templates/step-ingest.md.j2` — host-skill workflow Step 1: the
  DEFAULT single-call `WD=$(runtime init --loom-root ... --set K=V)`
  ingest step (auto workdir + unconditional wipe + entry-task seed).
- `templates/helper-dispatch-agent.md.j2` — host-skill helper: dispatch
  a surfaced agent task via `subagent`.
- `templates/helper-drive-human-gate.md.j2` — host-skill helper: drive
  a surfaced human gate.
- `schemas/io.yaml` — a task's `io.yaml`: `version`, `input`, `output`.
- `schemas/graph.yaml` — a graph declaration: task entries, deps, latches,
  subgraph entries, version pins, per-entry `input:` mappings.
- `schemas/next.yaml` — the document `$LOOM runtime next` prints (success on
  stdout, abort on stderr).
- `schemas/plan.yaml` — the engine-owned `plan.yaml` inside a workdir.
- `schemas/error.yaml` — the `error.yaml` written when a task fails.
- `schemas/skip-reason.yaml` — the `skip-reason.yaml` written when a task is
  skipped (`when-false` or `cascade-skip`).
- `schemas/schema-error.yaml` — the `schema-error.yaml` written when the
  materialised `input.yaml` (`phase: input`) or `output.yaml`
  (`phase: output`) fails validation.
- `schemas/stderr.yaml` — the `stderr.yaml` capturing a task body's stderr
  output.

## Completion

Evidence per command family — every command has a concrete DONE phrase so
authoring, ingest, runtime, and diagnostic callers all know when to move on.

| Status               | Criteria                                                          |
|----------------------|-------------------------------------------------------------------|
| `DONE`               | See per-family evidence rows below                                |
| `DONE_WITH_CONCERNS` | Non-fatal warning logged: `stderr.yaml` present, deprecated field |
| `BLOCKED`            | Any `LoomPlanError` raised; nothing was written                   |
| `NEEDS_CONTEXT`      | Missing `<workdir>` / `<name>` / `<skill-root>` / `--loom-root`   |

Per-family `DONE` evidence:

| Command family           | Evidence                                                      |
|--------------------------|---------------------------------------------------------------|
| `runtime`                | `next` returned `done: true` and `plan.yaml` validates        |
| `task new`               | Task folder exists (empty; author writes bodies next)         |
| `task io-python`         | `io_types.py` regenerated at the current `io.yaml/version`    |
| `graph new`              | Prints `scaffolded ...`, `repinned ...`, or `unchanged`       |
| `output init` / `add`    | Task `output.yaml` validates against `io.yaml/output`         |
| `validate` / `visualise` | Exit 0 (validate: no `LoomPlanError`; visualise: DAG printed) |

Escalation: any failure surfaces the exception unchanged; there is no retry.
