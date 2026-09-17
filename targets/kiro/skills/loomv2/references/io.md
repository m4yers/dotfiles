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

Reserved names (`__loom`, `__task`) do NOT use `$ref` — see §5. Any `$ref` on
a reserved-name property is rejected.

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
BARE — as the empty mapping `{}` — and the io.yaml loader substitutes in the
meta-schema (`schemas/loom-meta.yaml` / `schemas/task-meta.yaml`). Any non-empty
declaration (`$ref`, inline `type`, or extra keys) is rejected via `IOYamlError`
because reserved shapes are not author-editable.

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
5. Producer/consumer contracts MUST be sound: the engine NEVER
   inserts defaults. If a field is unconditionally present, list it
   in `required` and the producer MUST produce it. If the underlying
   data may be absent, the field STAYS in `required` and the producer
   MUST emit an explicit empty value (`[]`, `""`, `null` — via
   `output add --set-json`); a task prompt MUST NOT tell the producer
   to omit a required field, because a silent omission would let
   undeclared "missing" satisfy the consumer schema and defeat the
   alignment guarantee that `loom.validate.subtype` relies on. Fields
   a consumer can genuinely work without are the only ones that may
   leave `required`.
6. The root of both `input` and `output` MUST declare
   `additionalProperties: false`. The meta-schema hard-enforces this
   at load; a missing declaration raises `IOYamlError`. Rule (5)'s
   soundness rests on it — an open producer surface would let
   undeclared fields silently satisfy a consumer wiring, defeating
   the alignment guarantee that `loom.validate.subtype` provides.

## 6b. Static alignment: subtype projection + required wiring

Two static passes run at `$LOOM runtime init` (and any subsequent `extend`),
immediately after `validate_references` and `validate_mapping`:

**`validate_subtype`** — for every task's `input_mapping` entry `field:
${task:X[@<selector>][:PATH]}`, project `PATH` through task `X`'s
`io.yaml/output` schema and check that the projected schema is a subtype of
the consumer's `io.yaml/input.properties[field]`. The walk propagates a
`may-be-absent` presence bit whenever a step lands on a non-required property
or the round selector points at the previous round (nullable on round 0); the
subtype check then rejects `may-be-absent` projections into required
non-nullable consumer fields. Rules used by the check:

- type-set inclusion (with `may-be-absent` injecting `null` into
  the producer's type set),
- enum subset, const equality, numeric-bound tightening
  (`minimum` / `maximum` on the producer must be at least as
  restrictive as the consumer's),
- object: producer `required ⊇` consumer `required`, covariant
  property subtyping, `additionalProperties: false` on the consumer
  requires the same on the producer,
- array: covariant items and tightened `minItems` / `maxItems`,
- unions: every producer branch subtypes some consumer branch (or
  the consumer union covers every producer branch).

**`validate_required_wiring`** — for every consumer task with an
`input_mapping`, every name in the consumer's `io.yaml/input.required` list
MUST be wired in the mapping, except reserved engine-provided names (`__loom`
/ `__task`). Entry tasks seeded via `runtime init --set` have `input_mapping
is None` and are exempt because `--set` is strict-validated against the same
schema at init.

### Statically-projectable JMESPath subset

Only these placeholder shapes admit static projection:

- `${task:<addr>}` and `${task:<addr>@<sel>}` — plain address /
  round-selected address; the projected schema is the whole producer
  output schema (or its round-0 nullable variant).
- `${task:<addr>[@<sel>]:PATH}` where `PATH` is a dot-separated
  chain of identifiers, each optionally followed by any number of
  integer bracket-indices — `foo.bar[0].baz[2][1]`.

Anything outside that subset — JMESPath filters (`items[?x > \`5\`]`), wildcards
(`items[*].x`), functions, quoted keys, arithmetic — is statically ambiguous
and **fails closed** with `TypeMismatchError` at init. So do schemas that carry
`not`, `if`, `then`, or `else` on the projected path, and `oneOf` / `anyOf`
where more than one branch admits the next projection step. The engine never
falls back to runtime here; the alignment guarantee only holds when the
projection is provably sound.

Subgraph-inlined child tasks re-anchor through `source_root` so subtype loads
the child skill's `io.yaml`, not the composed plan's root — matching
`validate_references`.

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
