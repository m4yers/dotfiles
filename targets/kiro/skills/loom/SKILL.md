---
name: loom
type: interface
description: Generic DAG task-execution library. Use when a skill needs to drive
  a DAG of tool / agent / human-gate tasks with mandatory output schemas, static
  validation, built-in Jinja prompt rendering, and crash-resumable workdir 
  state. Do NOT invoke directly from user prompts — skills import loom and call 
  loom.init / loom.extend / loom.resume.
---

# Loom

A passive, single-process DAG task-execution library. Skills declare a static
plan; loom validates it, lowers it to `plan.yaml`, schedules tasks, executes
internal `tool` tasks inline, renders prompts for external `agent` and
`human` tasks, validates outputs against per-task JSON Schema, and persists
every state transition atomically.

Loom never imports skill code, never auto-triggers anything on completion,
and never owns workdir paths.

## Task primitive

A task has fields
`(id, kind, output_schema, depends_on_all, depends_on_any, when, kind-specific fields)`:

- `id` — unique within the plan; used for refs and paths.
- `kind` — `tool`, `agent`, or `human`.
- `output_schema` — path to YAML JSON Schema. Required for `tool`/`agent`;
  optional for `human` (defaults to `{type: object}`).
- `depends_on_all` — list of upstream ids. Optional.
- `depends_on_any` — list of upstream ids. Optional.
- `when` — predicate string. Optional; defaults to true.
- `cmd` — argv for `tool`.
- `template` — Jinja template path for `agent` and `human`.

### Kinds

| Kind    | Body                                                            |
| ------- | --------------------------------------------------------------- |
| `tool`  | Engine runs `cmd` as a subprocess inside `next()`. Stdout →     |
|         | `output.yaml`, stderr → `stderr.log`. Output validated against  |
|         | schema.                                                         |
| `agent` | Engine renders the Jinja template to `prompt.md` and yields the |
|         | task. Caller dispatches LLM, writes `output.yaml`, then calls   |
|         | `runtime.complete(id)`. Output validated at completion.         |
| `human` | Same as `agent` but typically gates or approval flows.          |

## Semantics

Statuses: `pending → ready → running → done | failed | skipped`. Every
transition is an atomic `plan.yaml` write.

`next()` resolves a task once every id in `depends_on_all` and
`depends_on_any` is in a terminal status (`done`, `failed`, or
`skipped`). Resolution applies these checks in order:

1. Cascade-fail. Mark `failed` and write `cascade-fail-reason.log` if
   either:
   - `depends_on_all` contains a dep with status `failed`.
   - `depends_on_any` is non-empty and every dep has status `failed`.
1. Predicate. Evaluate `when:`. If it returns false, mark `skipped`
   and write `skip-reason.log`.
1. Otherwise mark `ready` and dispatch.

`done` and `skipped` are equivalent for the cascade-fail check;
`depends_on_all=[done, skipped]` does not cascade.

Body failures transition the task to `failed`:

- `tool` subprocess exited non-zero.
- `agent` `output.yaml` failed schema validation.
- Jinja render error (`ready → failed`).

## Public API

```python
import loom
from loom import tool, agent, human, make_plan

plan = make_plan(
    tool("fetch", cmd=[...], output_schema="/abs/fetch.yaml"),
    agent(
        "classify",
        template="/abs/classify.j2",
        output_schema="/abs/classify.yaml",
        depends_on_all=["fetch"],
    ),
    agent(
        "extract-paper",
        template="/abs/extract.j2",
        output_schema="/abs/extract.yaml",
        depends_on_all=["classify"],
        when="${task:classify:quintet.form == 'paper'}",
    ),
)

runtime = loom.init(workdir="/abs/run", plan=plan)
loom.extend(runtime, more_tasks)
runtime = loom.resume("/abs/run")

while True:
    action = runtime.next()
    if action is None:
        break
    for task in action.tasks:
        # render prompt is already on disk; dispatch + write output.yaml
        ...
    runtime.commit_running([t["id"] for t in action.tasks])
    for task in action.tasks:
        runtime.complete(task["id"])
```

## Worked example

A plan with two source-shape branches and a fan-in.

```python
plan = make_plan(
    tool("fetch", cmd=["curl", URL], output_schema=fetch_schema),
    agent(
        "classify",
        template=classify_j2,
        output_schema=quintet_schema,
        depends_on_all=["fetch"],
    ),
    # Paper-only branch
    agent(
        "extract-paper",
        template=paper_j2,
        output_schema=extract_schema,
        depends_on_all=["classify"],
        when="${task:classify:quintet.form == 'paper'}",
    ),
    # Video-only branch
    agent(
        "extract-video",
        template=video_j2,
        output_schema=extract_schema,
        depends_on_all=["classify"],
        when="${task:classify:quintet.form == 'video'}",
    ),
    # Fan-in across the optional branches.
    tool(
        "aggregate",
        cmd=["python", AGG_SCRIPT, "--workdir", "${workdir}"],
        output_schema=agg_schema,
        depends_on_all=["extract-paper", "extract-video"],
    ),
)
```

Trace for a paper source:

1. `fetch` → `done`.
1. `classify` → `done` with `{quintet: {form: 'paper'}}`.
1. `extract-paper`: no failed deps, `when:` true → `done`.
1. `extract-video`: no failed deps, `when:` false → `skipped`.
1. `aggregate`: deps `[done, skipped]` → no cascade-fail, no `when:` →
   `done`.

Trace if `extract-paper` fails:

1. `aggregate`: `depends_on_all` has a `failed` dep → `failed`.
   `cascade-fail-reason.log` records
   `cascade-fail: 1/2 all-deps failed (first: extract-paper)`.

## Reference grammar

| Placeholder                     | Resolves to                         |
| ------------------------------- | ----------------------------------- |
| `${workdir}`                    | absolute workdir path               |
| `${task_workdir}`               | absolute path to current task dir   |
| `${task:<id>}`                  | upstream task's full output         |
| `${task:<id>:<jmespath>}`       | JMESPath query result               |
| `${task_path:<id>}`             | absolute path to upstream output    |
| `${global}` / `${global:<rel>}` | absolute path to `<workdir>/global` |

Inside a `when:` predicate the syntax is identical; the engine desugars
`${task:<id>:<expr>}` to JMESPath `task."<id>".<expr>` and evaluates
against a virtual document of all task outputs.

`$${...}` produces a literal `${...}` (escape).

## Workdir layout

```
<workdir>/
├── plan.yaml             # engine-owned DAG + statuses
├── tasks/<NN-id>/        # per-task scratch
│   ├── output.yaml       # the only file engine reads from a task
│   ├── prompt.md         # rendered prompt (agent/human only)
│   ├── stderr.log        # tool subprocess stderr
│   ├── render-error.log  # jinja error, if any
│   ├── schema-error.log  # output_schema mismatch, if any
│   ├── skip-reason.log   # when:-false reason, if any
│   └── cascade-fail-reason.log  # upstream-failure cascade reason
└── global/               # cross-task shared state, skill-owned
```

## Output schemas

Every `tool` and `agent` MUST declare `output_schema` pointing to a YAML
JSON Schema file. Loom loads, meta-validates, and caches schemas at
`init`/`extend`. At runtime, `complete()` validates `output.yaml`
against the schema; mismatch → `failed` and `OutputSchemaError`.

## Output writer CLI

Lets agent tasks write `output.yaml` through schema-validated shell
calls instead of raw `fs_write`:

```
loom output init <workdir> --task <id>
loom output add  <workdir> --task <id> --set path=value [--set ...]
```

- `init` resolves the task's schema from `plan.yaml`, seeds top-level
  array / object containers, and writes `tasks/<NN-id>/output.yaml`.
- `add` applies dotted `path=value` assignments (numeric segments are
  array indices), coerces values per the schema, validates the full
  file against the schema, and writes back atomically.

The wrapper at `scripts/loom.sh` runs `python -m loom` under uv:

```bash
$loom_sh output init "$WORKDIR" --task extract-keywords
$loom_sh output add  "$WORKDIR" --task extract-keywords \
    --set keywords.0.name='RAG' \
    --set keywords.0.definition='retrieval augmentation pattern'
```

## Plan extension

`loom.extend(runtime, more_tasks)` re-runs static validation against the
merged plan, then appends. New tasks may reference existing ids in
`depends_on_*` / `${task:...}` / `when:`.

Pattern for branched plans: a `tool` task generates a plan dict; the
orchestrator reads its output and feeds it to `loom.extend`:

```python
runtime.complete("build-stage2-plan")
plan_dict = runtime.task_output("build-stage2-plan")
loom.extend(runtime, loom.LoomPlan.from_dict(plan_dict))
```

## Static validation (init / extend)

Run before any disk write:

1. DAG integrity — cycles, missing deps, duplicate ids.
1. Kind-field consistency — tool has `cmd`; agent has `template`; etc.
1. Mandatory `output_schema` on every `tool` and `agent`.
1. Schema files exist, parse as YAML, are valid JSON Schema.
1. Every `${task:<id>:...}` reference targets an existing task.
1. JMESPath dot-paths and array indices resolve against the referenced
   task's `output_schema`.
1. Comparator literals are type-compatible with declared field types.

Any failure raises a `LoomPlanError` subclass; no disk state is created.

## Errors

| Class                  | Raised by                                  |
| ---------------------- | ------------------------------------------ |
| `LoomPlanError`        | base for plan-time validation failures     |
| `DAGError`             | cycle / duplicate id / missing dep         |
| `SchemaError`          | schema file missing or invalid JSON Schema |
| `ReferenceError`       | bad `${task:id:...}` reference             |
| `TypeMismatchError`    | comparator literal vs. declared field type |
| `WorkdirExistsError`   | `loom.init` on workdir with `plan.yaml`    |
| `WorkdirNotEmptyError` | `loom.init` on dirty workdir               |
| `RunFailed`            | tool subprocess exited non-zero            |
| `OutputSchemaError`    | output.yaml fails schema validation        |
| `RenderFailed`         | Jinja render error                         |

## Template inheritance

For Jinja `{% extends %}` / `{% include %}`, set `template_search_paths`
on the task to include any directories the included paths resolve
against. Loom's FileSystemLoader uses
`[template_path.parent, *template_search_paths]`.

## Legacy `depends_on` (deprecated)

`depends_on=` is silently migrated to `depends_on_all=` on construction
and YAML load. Factories emit `FutureWarning`. Mixing `depends_on=` with
`depends_on_all=` raises immediately. `Task.depends_on` remains
populated as the order-preserving union of the two canonical lists for
callers that just want "every upstream id".

## Implementation

- `loom/__init__.py` — public surface
- `loom/_lifecycle.py` — `init`, `extend`, `resume`
- `loom/plan.py` — `tool`, `agent`, `human`, `make_plan` factories
- `loom/engine/models.py` — `Task`, `LoomPlan`, `ActionSpec`
- `loom/engine/store.py` — `plan.yaml` and `output.yaml` IO
- `loom/engine/algorithm.py` — ready-set, predicates, transitions
- `loom/engine/runner.py` — `LoomRuntime` execution methods
- `loom/engine/resolve.py` — placeholder substitution
- `loom/render/jinja.py` — Jinja rendering with default context bags
- `loom/validate/dag.py` — DAG + kind-field checks
- `loom/validate/schemas.py` — `SchemaCache`
- `loom/validate/references.py` — reference + JMESPath + type checks
- `loom/builders.py` — `output init` / `output add` write path
- `loom/__main__.py` — argparse CLI
- `scripts/loom.sh` — uv wrapper for the CLI
- `loom/errors.py` — exception hierarchy

Tests at `scripts/loom/tests/` — 315 cases.
