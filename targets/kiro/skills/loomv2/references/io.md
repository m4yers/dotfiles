# io.yaml — the task IO contract

Every task folder MUST contain an `io.yaml` file. It is the single source of
truth for a task's interface: the shape of the validated `input.yaml` the engine
materialises at dispatch, and the shape of the `output.yaml` the task writes on
completion. The meta-schema lives at [../schemas/io.yaml](../schemas/io.yaml).

Contents:

- [1. Why io.yaml exists](#1-why-ioyaml-exists)
- [2. The `input` and `output` blocks](#2-the-input-and-output-blocks)
- [3. `$ref` convention](#3-ref-convention)
- [4. Versioning](#4-versioning)
- [5. Reserved default objects](#5-reserved-default-objects-__loom-__task)
- [6. Rules](#6-rules)
- [7. See also](#7-see-also)

## 1. Why io.yaml exists

Loom is contract-local: every task sees only its own validated `input.yaml` and
writes only its own `output.yaml`. Cross-task data flows through the graph.yaml
`input:` mapping the engine resolves at dispatch. `io.yaml` is where the shape
of both sides is declared, so that:

- The engine can strictly validate `input.yaml` before dispatch and
  `output.yaml` on completion.
- Static validators (references, template renderer, tool codegen) can
  reason about the task's interface without executing anything.
- Author-facing tooling (`$LOOM task io-python`) can generate typed
  Python dataclasses from the schema.

## 2. The `input` and `output` blocks

Each block is a JSON Schema (draft 2020-12) fragment. Root MUST be an object;
property shapes are ordinary JSON Schema:

```yaml
version: 1
input:
  type: object
  additionalProperties: false
  properties:
    greeting: {type: string}
  required: [greeting]
output:
  type: object
  additionalProperties: false
  properties:
    summary: {type: string}
  required: [summary]
```

- `type: object` at the root is mandatory (tool tasks receive a
  generated `<TaskName>Input` dataclass whose fields come from
  `properties`).
- `additionalProperties: false` locks the surface — a task cannot
  silently receive undeclared upstream data.
- `required` tracks which fields MUST be present in the materialised
  document.

## 3. `$ref` convention

Property shapes MAY reference external files or JSON Pointer fragments via
`$ref`:

| Form | Handling |
|---|---|
| `$ref: ../path/to/other.yaml` | Relative filesystem path (see below). |
| `$ref: '#/$defs/foo'` | JSON Pointer fragment; handled by jsonschema natively. |
| `$ref: 'http://...'` / `'file://...'` | Absolute URIs — NOT supported. |

Relative filesystem paths are resolved against the io.yaml's OWN folder; the
loader inlines the target at parse time. Nested `$ref`s inside the target
re-anchor to that file's folder. `$ref` cycles and missing targets raise
`IOYamlError` with the offending path.

Reserved names (`__loom`, `__task`) do NOT use `$ref` — see §5. Any `$ref`
on a reserved-name property is rejected.

## 4. Versioning

`version` is a monotonically-increasing integer that MUST bump whenever the
shape of `input` or `output` changes. Every `graph.yaml` entry pins the version
it saw at authoring time; drift at `$LOOM runtime init` raises
`TaskVersionMismatchError`. Re-pin after a bump with `$LOOM graph new`.

## 5. Reserved default objects (`__loom`, `__task`)

Two engine-provided objects are RESERVED names in every task's `io.yaml/input`:
`__loom` and `__task`. They are ordinary declared properties; the engine fills
the value at dispatch when the name is declared. Declaring is opt-in: templates
that do not need the values do not declare the names and pay no cost.

Because loom owns the canonical shape of these objects, authors declare them
BARE — as the empty mapping `{}` — and the io.yaml loader substitutes the
meta-schema (`schemas/loom-meta.yaml` / `schemas/task-meta.yaml`) in place.
Any non-empty declaration (`$ref`, inline `type`, extra keys) is rejected
with `IOYamlError`: reserved shapes are not author-editable.

- `input:` mappings in graph.yaml MUST NOT wire either reserved name,
  because the engine owns those values — both static (`ReservedShadowError`)
  and dispatch (`InputSchemaError`) reject the shadow.
- Templates access them dot-style —
  `{{ input.__loom.workdir }}` / `{{ input.__task.id }}`. Jinja's
  default `Environment.getattr` falls back to `obj[attribute]` when
  `getattr` raises `AttributeError`, so dict-subscript resolution
  works on the plain dicts persisted in `input.yaml`.
- Tools receive them typed: the scaffold aliases `__loom` → `loom`
  and `__task` → `task` on the generated dataclass (Python
  name-mangling workaround) and types the aliased fields with the
  hand-written engine dataclasses `LoomMeta` / `TaskMeta`, so tool
  code writes `inp.loom.workdir`, not `inp.loom["workdir"]`.

### 5.1 `__loom`

- **Mirror:** [../schemas/loom-meta.yaml](../schemas/loom-meta.yaml) /
  `LoomMeta` (in `scripts/loom/loom/engine/reserved.py`).
- **Fields:** `workdir` (string, absolute run workdir), `runtime`
  (string, absolute path to the dispatching `loom.sh` shim — use it in
  templates instead of hardcoding an install path).
- **Template access:** `{{ input.__loom.workdir }}`,
  `{{ input.__loom.runtime }}`.
- **Tool access:** aliased to `loom`, typed `LoomMeta` —
  `inp.loom.workdir`.

Declare the field bare — the loader substitutes the meta-schema:

```yaml
# my-skill/loom/greet/io.yaml
input:
  type: object
  additionalProperties: false
  properties:
    __loom: {}
  required: [__loom]
```

### 5.2 `__task`

- **Mirror:** [../schemas/task-meta.yaml](../schemas/task-meta.yaml) /
  `TaskMeta` (in `scripts/loom/loom/engine/reserved.py`).
- **Fields:** `id`, `kind`, `iter`, `namespace`, `workdir`.
- **Template access:** `{{ input.__task.id }}`.
- **Tool access:** aliased to `task`, typed `TaskMeta` — `inp.task.id`.

**Narrowing note.** The previous ambient `task` dict was
`dataclasses.asdict(Task)` over all 15 Task fields. The new `__task` object
exposes four identity/metadata fields plus `workdir`; anything else (e.g.
`status`, `depends_on_all`, `inlined_from_subgraph`, `pinned_version`) is
engine-internal state and intentionally out of scope. Extending the surface
is a two-file commit: add the field to
[../schemas/task-meta.yaml](../schemas/task-meta.yaml) AND to `TaskMeta` in
`scripts/loom/loom/engine/reserved.py` in the same change.

Declaration is bare, as with `__loom` — write `__task: {}` under
`input.properties`.

## 6. Rules

RFC-2119 shall-language:

1. `io.yaml` MUST list every field a template references (top-level
   name `input` plus every attribute chain read off it).
2. `$ref` MUST be either a relative filesystem path (resolved against
   the io.yaml's OWN folder) or an in-file JSON Pointer (`#/$defs/...`).
   Absolute URIs are NOT supported.
3. Reserved names (`__loom`, `__task`) MUST NOT appear as
   `graph.yaml` `input:` mapping keys, because the engine owns
   those values.
4. `version` MUST bump whenever the shape of `input` or `output`
   changes.

## 7. See also

- [../schemas/io.yaml](../schemas/io.yaml) — self-describing meta-schema.
- [../schemas/loom-meta.yaml](../schemas/loom-meta.yaml) — reserved
  `__loom` object shape.
- [../schemas/task-meta.yaml](../schemas/task-meta.yaml) — reserved
  `__task` object shape.
- [`engine/reserved.py`](../scripts/loom/loom/engine/reserved.py)
  — `LoomMeta` / `TaskMeta` dataclasses and `build_reserved_values`.
- [guide.md §3](guide.md#3-agent-task) — walkthrough of an agent task
  that opts into `__loom`.
