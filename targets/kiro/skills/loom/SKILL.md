---
name: loom
type: interface
description: Generic DAG task-execution library. Use when a skill needs to drive a DAG of tool / agent / human-gate tasks with mandatory output schemas, static validation, built-in Jinja prompt rendering, and crash-resumable workdir state. Do NOT invoke directly from user prompts — skills import loom and call loom.init / loom.extend / loom.resume.
---

# Loom

Loom is a passive, single-process DAG task-execution library. Skills declare
a static plan; loom validates it, lowers it to `plan.yaml` on disk,
schedules tasks, executes internal `tool` tasks inline, renders prompts for
external `agent` and `human` tasks, validates outputs against per-task
JSON-Schema, and persists every state transition atomically.

Loom never imports skill code, never auto-triggers anything on task
completion, and never owns workdir paths — the caller is in charge.

## Public API

Three top-level functions plus one runtime class:

```python
import loom
from loom import tool, agent, human, make_plan

plan = make_plan(
    tool('fetch',
         cmd=[...],
         output_schema='/abs/path/fetch.schema.yaml'),
    agent('classify',
          template='/abs/path/classify.j2',
          output_schema='/abs/path/classify.schema.yaml',
          depends_on=['fetch']),
    agent('extract-paper',
          template='/abs/path/extract.j2',
          output_schema='/abs/path/extract.schema.yaml',
          depends_on=['classify'],
          when="${task:classify:quintet.form == 'paper'}"),
)

# Lifecycle
runtime = loom.init(workdir='/abs/path/run', plan=plan)
loom.extend(runtime, more_tasks)
runtime = loom.resume('/abs/path/run')

# Execution loop
while True:
    action = runtime.next()
    if action is None:
        break
    for task in action.tasks:
        # render prompt, dispatch agent / show human gate
        write_output_yaml(task)
    runtime.commit_running([t['id'] for t in action.tasks])
    for task in action.tasks:
        runtime.complete(task['id'])
```

## Task kinds

Three kinds, fixed:

- **`tool`** — engine runs the `cmd` as a subprocess inside `next()`. Stdout
  goes to `output.yaml`, stderr to `stderr.log`. Engine validates the
  output against the task's schema and marks `done` or `failed`.
- **`agent`** — engine renders the Jinja `template` to `prompt.md` inside
  `next()` and yields the task to the caller. Caller dispatches to a
  sub-agent / LLM, writes `output.yaml`, then calls `runtime.complete`.
- **`human`** — same as agent but typically used for approval gates and
  free-form input. Default schema (`{type: object}`) accepts any output.

## Status lifecycle

Six statuses; transitions are atomic plan.yaml writes:

```
pending  →  ready  →  running  →  done | failed | skipped
```

- `ready` is yielded but not yet committed; idempotent on re-yield.
- `skipped` is `pending → skipped` when a `when:` predicate is false.
- A task with at least one dep that has every dep in `skipped` status is
  auto-skipped via cascade — there's nothing to act on. Cascade applies
  after `when:` evaluation: an explicit `when: false` always wins.
- Render failure transitions `ready → failed` (skipping `running`).

## Dependency lists

Each task carries two dependency lists; both are optional and may
be combined on the same task.

- **`depends_on_all`** — the task becomes ready when **every** id
  in the list is in a terminal status (`done`, `failed`, or
  `skipped`). This is the legacy "wait for all" semantics.
- **`depends_on_any`** — the task becomes ready when **at least
  one** id in the list is in a terminal status. Use this for
  alternative-path joins where any one upstream's output is
  enough to proceed.

When both lists are present, **both** conditions must hold.

### Cascade-skip

Cascade-skip applies independently to each list. A task is
auto-skipped when:

- `depends_on_all` is non-empty and every id in it is `skipped`, OR
- `depends_on_any` is non-empty and every id in it is `skipped`.

Either condition by itself triggers cascade — a task whose
all-list is satisfied but whose entire any-list was skipped has
no upstream output to consume and is skipped.

### Legacy `depends_on` (deprecated)

The pre-1.0 `depends_on` field is deprecated. It is silently
migrated to `depends_on_all` on construction and on YAML load,
preserving the historical "wait for all" semantics. The plan
factories (`tool` / `agent` / `human`) emit a `FutureWarning`
when called with `depends_on=`. Mixing `depends_on=` with the
new `depends_on_all=` raises immediately.

```python
# old (deprecated; emits FutureWarning)
tool('build', cmd=[...], output_schema=s, depends_on=['compile'])

# new — same semantics
tool('build', cmd=[...], output_schema=s, depends_on_all=['compile'])

# new — wait-for-any
tool('build', cmd=[...], output_schema=s, depends_on_any=['ci-x86', 'ci-arm'])
```

The `Task.depends_on` attribute stays populated as the order-
preserving union of the two canonical lists, so consumers that
just want "every upstream id" (template context, viz layout)
keep working.

## Workdir layout

Caller supplies the workdir path. Loom creates:

```
<workdir>/
├── plan.yaml             # engine-owned DAG + statuses
├── tasks/<NN-id>/        # per-task scratch
│   ├── output.yaml       # the only file engine reads from a task
│   ├── prompt.md         # rendered prompt (agent/human only)
│   ├── stderr.log        # tool subprocess stderr
│   ├── render-error.log  # jinja error, if any
│   ├── schema-error.log  # output_schema mismatch, if any
│   └── skip-reason.log   # predicate skip reason, if any
└── global/               # cross-task shared state, skill-owned
```

## Output schemas

Every `tool` and `agent` task MUST declare an `output_schema` pointing to a
YAML file containing JSON Schema. Loom loads, meta-validates, and caches
schemas at `init` / `extend` time. At runtime, `complete()` validates the
written `output.yaml` against the schema; mismatch → task transitions to
`failed` and `OutputSchemaError` is raised.

`human` tasks may omit `output_schema`; loom uses a permissive default.

## Reference grammar

Five built-in placeholders, no skill extension:

| Placeholder              | Resolves to                           |
|--------------------------|---------------------------------------|
| `${workdir}`             | absolute workdir path                 |
| `${task_workdir}`        | absolute path to the current task dir |
| `${task:<id>}`            | upstream task's full output (native)  |
| `${task:<id>:<jmespath>}` | JMESPath query result (native)        |
| `${task_path:<id>}`      | absolute path to upstream output.yaml |
| `${global}` / `${global:<rel>}` | absolute path to `<workdir>/global[/<rel>]` |

Inside a `when:` predicate the syntax is identical; the engine desugars
`${task:<id>:<expr>}` to JMESPath `task."<id>".<expr>` and evaluates against
a virtual document of all task outputs.

`$${...}` produces a literal `${...}` (escape).

## Static validation pipeline

`loom.init` and `loom.extend` run, in order, before any disk write:

1. DAG integrity (cycles, missing deps, duplicate ids)
2. Kind-field consistency (tool has `cmd`; agent has `template`; etc.)
3. Mandatory `output_schema` on every tool and agent task
4. Schema files exist, parse as YAML, are valid JSON Schema
5. Every `${task:<id>:...}` reference targets an existing task
6. JMESPath dot-paths and array-indices resolve against the referenced
   task's `output_schema` (filter projections and function calls
   are parse-checked only; not field-traced)
7. Comparator literals are type-compatible with declared field types

Any failure raises a `LoomPlanError` subclass; no disk state is created.

## Error hierarchy

| Class                 | Raised by                                   |
|-----------------------|---------------------------------------------|
| `LoomPlanError`       | base for plan-time validation failures      |
| `DAGError`            | cycle / duplicate id / missing dep          |
| `SchemaError`         | schema file missing or invalid JSON Schema  |
| `ReferenceError`      | bad `${task:id:...}` reference              |
| `TypeMismatchError`   | comparator literal vs. declared field type  |
| `WorkdirExistsError`  | `loom.init` on workdir with `plan.yaml`     |
| `WorkdirNotEmptyError`| `loom.init` on dirty workdir                |
| `RunFailed`           | tool subprocess exited non-zero             |
| `OutputSchemaError`   | output.yaml fails schema validation         |
| `RenderFailed`        | Jinja render error                          |

## Plan extension pattern

Plan extension is explicit. Recommended pattern: a `tool` task generates a
new plan as YAML; the orchestrator reads its output and feeds it to
`loom.extend`:

```python
runtime.complete('build-stage2-plan')
plan_yaml = runtime.task_output('build-stage2-plan')
loom.extend(runtime, loom.LoomPlan.from_dict(plan_yaml))
```

For A-or-B branching, declare two `tool` tasks with complementary `when:`
predicates; whichever runs writes the plan, and the orchestrator extends
with whichever non-empty output it finds.

## Implementation reference

- `loom/__init__.py` — public surface re-exports
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
- `loom/errors.py` — exception hierarchy

## Output writer CLI

Loom ships a small CLI that lets agent tasks write `output.yaml`
through schema-validated shell calls instead of raw `fs_write`.
Sub-agents (LLM tasks) invoke it from rendered prompts.

```
loom output init <workdir> --task <id>
loom output add  <workdir> --task <id> --set path=value [--set ...]
```

- `init` resolves the task's `output_schema` from `plan.yaml`,
  embeds the schema path in `_schema`, seeds top-level array /
  object containers, and writes `tasks/<NN-id>/output.yaml`.
- `add` applies dotted `path=value` assignments (numeric segments
  are array indices), coerces values per the schema, validates the
  full file against the schema, and writes back atomically.

Loom still validates at `runtime.complete()`; the CLI's eager
validation just shifts the failure earlier so a bad write is caught
before the orchestrator marks the task done.

The wrapper at `scripts/loom.sh` runs `python -m loom` under uv:

```bash
loom_sh=~/.kiro/skills/home/loom/scripts/loom.sh
$loom_sh output init "$WORKDIR" --task extract-keywords
$loom_sh output add  "$WORKDIR" --task extract-keywords \
    --set keywords.0.name='RAG' \
    --set keywords.0.definition='retrieval augmentation pattern'
```

Skills passing this wrapper into prompts typically inject it as a
template var (e.g. `vars.loom_sh`) at plan time and reference
`{{ run.workdir }}` and `{{ task.id }}` to address the task.

Implementation reference:
- `loom/builders.py` — write path: schema lookup, path setter,
  type coercion, atomic save, jsonschema validation.
- `loom/__main__.py` — argparse CLI (`output init`, `output add`).
- `scripts/loom.sh` — uv wrapper.

## Template inheritance

For templates that use Jinja `{% extends %}` or `{% include %}`, set
`template_search_paths` on the task to include any directories the
included paths resolve against. Loom's FileSystemLoader uses
`[template_path.parent, *template_search_paths]`.

Tests live at `scripts/loom/tests/` (215 cases covering all in-scope
constraints; coverage matrix at `~/shared/projects/loom/promoted/test-coverage.md`).
