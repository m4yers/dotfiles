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
`input.yaml`. There is no shared state between tasks, so every run is
replayable from the recorded inputs.

## Invocation

```bash
LOOM=~/.kiro/skills/home/loomv2/scripts/loom.sh
$LOOM <group> <command> [options]
```

## API

Consumer surface is the CLI, grouped by command family.

### runtime

| Command            | Args                                    | Output                          |
|--------------------|-----------------------------------------|---------------------------------|
| `runtime init`     | `<workdir> --loom-root PATH`            | prints workdir path             |
| `runtime next`     | `<workdir>`                             | YAML: `done` + `ready` batch    |
| `runtime complete` | `<workdir> <task-address>`              | `ok`; validates `output.yaml`   |
| `runtime fail`     | `<workdir> <task-address> --message T`  | marks failed; writes error.yaml |
| `runtime reset`    | `<workdir> <task-address>`              | resets task (region-aware)      |
| `runtime status`   | `<workdir>`                             | YAML: totals + status counts    |

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

| Command       | Args                                 | Output                         |
|---------------|--------------------------------------|--------------------------------|
| `output init` | `<workdir> --task <id>`              | seeds `output.yaml`            |
| `output add`  | `<workdir> --task <id> --set K=V...` | dotted-path writes + validates |

### misc

| Command     | Args                         | Output                          |
|-------------|------------------------------|---------------------------------|
| `validate`  | `<skill-root> [--plan PATH]` | non-zero on any `LoomPlanError` |
| `visualise` | `<workdir>`                  | ASCII DAG with namespaced tasks |

## Commands

Per-command contracts live below. Each subsection carries the invocation
example, arguments, and behaviour notes callers need. Full edge-case
contracts and cross-command interactions live in
[references/commands.md](references/commands.md).

### runtime init

```bash
$LOOM runtime init "$WORKDIR" --loom-root "$LOOM_ROOT"
```

Creates a fresh workdir on top of `<loom-root>/graph.yaml`. Loads the graph,
inlines subgraphs, runs static validation, then writes `plan.yaml` and
per-task folders. Prints the workdir path on success.

- `<workdir>` — target folder; must not already contain a `plan.yaml`.
- `--loom-root PATH` — folder containing `graph.yaml` and task folders.
- Non-zero exit on any `LoomPlanError`; nothing is written when validation
  fails.

### runtime next

```bash
$LOOM runtime next "$WORKDIR"
```

Resumes the workdir, runs every ready tool task internally, and emits a YAML
document to stdout (shape: `schemas/next.yaml`). If `done: true` execution is
finished; otherwise execute each entry in `ready` — dispatch `kind: agent`
entries to a sub-agent using `prompt_path`, drive `kind: human` entries from
`message_path`, write each task's `output.yaml`, then call
`$LOOM runtime complete`. The surfaced batch is committed to `running` before
`next` returns; tool tasks never appear in `ready`.

At every dispatch (once per activation; per round for loop bodies) `next`
evaluates the `when` predicate, resolves and strictly validates any
`input:` mapping in `graph.yaml`, and captures a tool body's stderr into
`stderr.yaml` when non-empty. Skipped tasks write `skip-reason.yaml`; input
validation failures write `schema-error.yaml` (`phase: input`).

- `<workdir>` — run workdir produced by `runtime init`.
- Non-zero exit if the run is aborted. Stderr carries the abort variant of
  `schemas/next.yaml` (`failed_task` + `error_path`).

### runtime complete

```bash
$LOOM runtime complete "$WORKDIR" "$TASK_ADDRESS"
```

Validates `<task-workdir>/output.yaml` against the task's `io.yaml/output`,
marks the task done, and persists the plan. Prints `ok` on success.
Completing a loop-latch task also runs the loop decision — `fuel` is
decremented and `while_` is evaluated against the round that just
finished; on continue the loop body is reset and the next `runtime next`
re-dispatches it under a fresh `iter-NN/` round dir.

- `<workdir>` — the run workdir.
- `<task-address>` — canonical task address as surfaced by `runtime next`.
- Raises `OutputSchemaError` (non-zero exit) if `output.yaml` fails its
  schema; the task is marked failed and a `schema-error.yaml`
  (`phase: output`) is written.

### runtime fail

```bash
$LOOM runtime fail "$WORKDIR" "$TASK_ADDRESS" --message "human reason"
```

Marks the task failed and writes `<task_workdir>/error.yaml` with the given
message. Used by callers to surface human/agent failures the CLI cannot
detect on its own (a human refuses, an external agent returns a fault).
Prints `ok`. The next `runtime next` raises `RunAborted`.

- `<workdir>` — the run workdir.
- `<task-address>` — canonical task address.
- `--message TEXT` — human-readable failure reason recorded in
  `error.yaml`.

### runtime reset

```bash
$LOOM runtime reset "$WORKDIR" "$TASK_ADDRESS"
```

Flips the task back to `pending` and clears its generated artifacts —
`output.yaml`, `error.yaml`, diagnostic YAMLs (`skip-reason.yaml`,
`schema-error.yaml`, `stderr.yaml`), rendered `prompt.md` / `message.md`,
and every `iter-NN/` round dir. Region-aware: resetting any task inside a
loop body resets the whole region so round indexing restarts at `iter-00`.
Caller-seeded `input.yaml` is preserved; mapping-driven `input.yaml` is
deleted and re-materialised on the next dispatch. Latch `fuel` is NOT
restored.

- `<workdir>` — the run workdir.
- `<task-address>` — canonical task address.

### runtime status

```bash
$LOOM runtime status "$WORKDIR"
```

Emits a YAML document with `total`, `is_done`, `is_stuck`, and per-status
counts (`pending`/`ready`/`running`/`done`/`failed`/`skipped`). Read-only.

- `<workdir>` — the run workdir.

### task new

```bash
$LOOM task new greet-user --loom-root ./loom
```

Creates `<loom-root>/<name>/` — folder only, no files inside. The authoring
agent then writes `io.yaml` by hand (see `schemas/io.yaml`) and the body
file appropriate to the task kind: tool task → run `task io-python` then
write `tool.py`; agent task → write `prompt.md.j2`; human task → write
`message.md.j2`.

- `<name>` — kebab-case, matches `^[a-z][a-z0-9-]*$`.
- `--loom-root PATH` — override the default (`./loom`).
- Raises `TaskFolderError` on bad name or when the folder already exists.

### task io-python

```bash
$LOOM task io-python greet-user --loom-root ./loom
```

Reads `<loom-root>/<name>/io.yaml` and (re)writes
`<loom-root>/<name>/io_types.py` — a fully generator-owned file carrying
`<TaskName>Input` / `<TaskName>Output` dataclasses with `VERSION`,
JSON→Python-typed fields, and `from_dict` / `to_dict` helpers. Regenerate
any time — the whole file is overwritten. Prints `wrote io_types.py (vN)`.

- `<name>` — task folder name.
- `--loom-root PATH` — override the default (`./loom`).
- Only meaningful for tool tasks; not gated on kind.
- Raises `TaskFolderError` if the folder is missing; `IOYamlError` if
  `io.yaml` is missing or fails the meta-schema.

### graph new

```bash
$LOOM graph new --loom-root ./loom
```

Idempotent. If `<loom-root>/graph.yaml` is absent, scaffolds a starter by
discovering task folders and pinning each entry to the current `io.yaml`
version (prints `scaffolded <path> with N task(s)`). If present, preserves
every authored field (task entries, `depends_on_all`/`any`, `when`,
latches, subgraph entries and their `root` paths, ordering, extra fields)
and restamps each entry's `version` from the referenced task folder's
current `io.yaml` (prints `repinned N task(s)` or `unchanged`).

- `--loom-root PATH` — override the default (`./loom`).
- Raises `GraphYamlError` if the existing file fails the meta-schema.

### output init

```bash
$LOOM output init "$WORKDIR" --task greet-user
```

Seeds `<workdir>/tasks/<id>/output.yaml` from the task's `io.yaml/output`
schema with the schema defaults.

- `<workdir>` — the run workdir.
- `--task <id>` — canonical task address.
- Non-zero exit if the task or workdir is missing.

### output add

```bash
$LOOM output add "$WORKDIR" --task greet-user \
    --set greeting='Hello' \
    --set meta.tone='cheerful'
```

Applies dotted-path assignments to the task's `output.yaml`, coerces each
value against the schema, revalidates, and writes atomically.

- `--set path=value` — repeatable; supports `field`, `field.sub`, and
  `field[]` for list append (`field[-1]` targets the last append).
- Non-zero exit on schema failure; the file on disk is not modified.

### validate

```bash
$LOOM validate <skill-root> [--plan PATH]
```

Runs the static validation set against a skill's `loom/` folder without
touching a workdir.

- `<skill-root>` — the skill root.
- `--plan PATH` — optional path to a `graph.yaml` to validate; when
  omitted, validates `<skill-root>/loom/graph.yaml`.
- Exits non-zero on any `LoomPlanError`; every message quotes the schema
  field description or the exception `remedy`.

### visualise

```bash
$LOOM visualise <workdir>
```

Renders `plan.yaml` as an ASCII DAG with statuses, loop glyphs, and
subgraph child tasks under their subgraph header.

- `<workdir>` — run workdir; must contain `plan.yaml`.

## References

- `references/guide.md` — step-by-step guide for building a loom skill;
  `examples/hello-graph/` is the finished reference skill it builds.
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

| Status               | Criteria                                                    |
|----------------------|-------------------------------------------------------------|
| `DONE`               | Runtime returned; workdir holds a valid `plan.yaml`         |
| `DONE_WITH_CONCERNS` | Validation surfaced a non-fatal warning the workflow logged |
| `BLOCKED`            | Validation raised a `LoomPlanError`; no writes performed    |
| `NEEDS_CONTEXT`      | No workdir/loom_root supplied; `resume` on a missing dir    |

Escalation: any failure surfaces the exception unchanged; there is no retry.
