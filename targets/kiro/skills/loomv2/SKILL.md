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
from the recorded inputs. A single task folder MAY back multiple graph entries
via the optional `task_entry.ref` field — each entry stays a distinct instance
addressed by its own `id`, sharing only the folder's `io.yaml` and body file
(see `references/guide-advanced.md` §11).

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
| `runtime init`     | `[<workdir>] --loom-root PATH [--graph FILE] [--set K=V ...]` | workdir path       |
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
per-flag semantics live under `### visualise` below.

## Commands

Per-command contracts, flags, error paths, and edge-case notes are inlined
below — one ### subsection per API-table row, in the same order.

### runtime init

Two equivalent shapes.

**Default (auto workdir)** — omit the workdir positional, let the engine name
and create it under `/tmp`, capture the printed path:

```bash
WD=$($LOOM runtime init --loom-root "$LOOM_ROOT" [--graph FILE] [--set K=V ...])
```

- `--graph FILE` selects a graph variant: an absolute path, or a
  filename resolved against `--loom-root` (default `graph.yaml`).
  The graph is read once at init and the composed plan persists to
  `plan.yaml`, so no later command needs the flag. Multi-graph loom
  roots (static scale variants sharing task folders) are documented
  in [references/guide-advanced.md](references/guide-advanced.md)
  §12.
- `<skill_name>` is derived from `<loom-root>`: if
  `basename(<loom-root>) == "loom"` (the conventional child folder of
  a skill directory, e.g. `.../skills/aws/diagnostics/rca/loom`),
  `<skill_name>` is the parent directory's basename (`rca`).
  Otherwise `<skill_name>` is `basename(<loom-root>)` itself.
- The auto workdir is `/tmp/<skill_name>/<uuid4.hex[:12]>/`. The
  resolved path is printed on stdout — capture it with `$( )`.
- Init-time failures on the auto form (plan validation,
  `SeedNotAllowedError`, `--set` grammar error, `--set` schema
  error) delete the auto workdir before the CLI exits non-zero, so
  a failed auto init leaves nothing behind.

**Explicit workdir** — for callers that need to name the path themselves (test
harnesses, scripts that stage the workdir elsewhere):

```bash
$LOOM runtime init "$WORKDIR" --loom-root "$LOOM_ROOT" [--set K=V ...]
```

- The caller owns the path; the engine does not clean it up on
  init-time failure.

**Common to both shapes.** Loads the graph via the internal plan API, inlines
subgraphs, runs static validation, then writes `plan.yaml` and per-task folders.
Prints the (resolved) workdir path on success. If the target workdir already
contains files, they are unconditionally wiped (`shutil.rmtree`) and the workdir
is recreated — there is no `--force` flag and no error on pre-existing contents.

Static validation includes the sound-alignment passes `validate_subtype` and
`validate_required_wiring` — every `input_mapping` field projects the producer's
`io.yaml/output` through the placeholder's JMESPath and checks the projection
is a subtype of the consumer's field schema, and every non-reserved required
consumer field MUST be wired. Anything outside the statically-projectable
JMESPath subset fails closed.

- Full contract and subset spec:
  [io.md §6b](references/io.md#6b-static-alignment-subtype-projection--required-wiring).

The DEFAULT ingest pattern is the auto-workdir shape above: workdir naming,
wipe, init, and entry-task input seeding fold into one `runtime init`
invocation, so host skills carry only a trivial bash shim (`WD=$($LOOM runtime
init ...)`). Caller-seeded `input.yaml` (hand-written before the first `runtime
next` when `--set` is omitted) is the supported escape hatch — pair it with the
explicit-workdir shape when a mapping-bound entry blocks `--set`.

- `<workdir>` — target folder (optional; omit to use the auto shape).
- `--loom-root PATH` — folder containing `graph.yaml` and task folders.
- `--set key=value` (repeatable) — after plan validation, resolves the
  plan's single entry task (in-degree 0 in the composed plan; the same
  predicate `validate_single_entry_exit` enforces at init), then:

  1. If the entry task has an `input:` mapping in `graph.yaml`, raises
     `SeedNotAllowedError` (a `LoomPlanError` subclass) — the mapping
     already binds the entry input and `--set` cannot compose with it.
     Remedy: remove the mapping or drop `--set`.
  2. Otherwise, each `key=value` is parsed with the same assignment
     grammar as `output add --set` (imported from `loom.builders` so
     the two commands stay in lock step). Paths support dict keys
     (`meta.tone`), explicit indices (`items.0` or `items[0]`), list
     append (`items[]`), and last-element addressing (`items[-1]`).
     Values are coerced via the shared `_coerce` helper (bool / int /
     float; anything else stays a string) and round-trip through the
     atomic `yaml.safe_dump(sort_keys=False)` emitter unchanged.
  3. The assembled document is strict-validated against the entry
     task's `io.yaml/input` — required fields are enforced (unlike
     `output add`'s partial validation), so typos and missing fields
     fail at init, not mid-run.
  4. Success writes `<workdir>/tasks/<NN>-<entry>/input.yaml`
     atomically; failure writes nothing (auto form: the auto workdir
     itself is wiped as part of the cleanup contract above).

  See `### runtime reset` below for the caller-seeded-preservation
  semantics that carry through when the entry is re-run after seeding.

- Non-zero exit on any `LoomPlanError`; nothing is written when validation
  fails.

### runtime next

```bash
$LOOM runtime next "$WORKDIR"
```

Resumes the workdir, runs every ready tool task internally, and emits a YAML
document to stdout. Parse it per `schemas/next.yaml`: if `done` is `true`
execution is finished; otherwise execute each entry in `ready` — dispatch
`kind: agent` entries to a sub-agent using `prompt_path`, drive `kind: human`
entries from `message_path` — write each task's `output.yaml`, then call
`$LOOM runtime complete`. The surfaced batch is committed to `running` before
`next` returns; tool tasks never appear in `ready`.

Tool tasks whose entry is `tool.sh` are dispatched via subprocess with the argv
contract documented in [guide.md §2a](references/guide.md#2a-shell-shim-toolsh):
`tool.sh <input.yaml> <output.yaml>` (positional argv, in that order), with
`cwd = <task workdir for the round>`. Non-zero exit raises `ToolTaskError`
carrying the last 2000 chars of stderr; the same output-schema validation runs
on the shim's `output.yaml`.

At every dispatch (once per activation; per round for loop bodies):

1. The `when` predicate is evaluated against the current run state. A clean
   false marks the task `skipped` and writes `skip-reason.yaml`
   (`reason_kind: when-false`); an upstream cascade skip writes the same file
   with `reason_kind: cascade-skip`. A predicate that fails to evaluate
   (parse / unresolvable ref) raises `PredicateEvalError` and aborts.
2. If the task carries an `input:` mapping in `graph.yaml`, the mapping is
   resolved and STRICTLY validated against the task's `io.yaml/input`.
   Missing required fields, undeclared extras, unfinished upstream refs, and
   schema failures write `schema-error.yaml` (`phase: input`), mark the task
   `failed`, and abort. Tasks without a mapping keep their caller-seeded
   `input.yaml`.
3. A tool body's stderr is captured (Python-level) and, if non-empty or the
   body fails, written to `<task_workdir>/stderr.yaml`.

- `<workdir>` — run workdir produced by `runtime init`.
- Non-zero exit if the run is aborted. Stderr carries the abort variant of
  `schemas/next.yaml` (`failed_task` + `error_path`).

### runtime complete

```bash
$LOOM runtime complete "$WORKDIR" "$TASK_ADDRESS"
```

Validates `<task-workdir>/output.yaml` against the task's `io.yaml/output`,
marks the task done, and persists the plan. Prints `ok` on success.

- `<workdir>` — the run workdir.
- `<task-address>` — canonical task address as surfaced by `runtime next`.
- Raises `OutputSchemaError` (non-zero exit) if `output.yaml` fails its schema;
  the task is marked failed and the run aborts on the next `runtime next` call.
  A `<task_workdir>/schema-error.yaml` (`phase: output`) is written alongside.

Loop latches: completing a latch task also runs the loop decision. `fuel` is
decremented and persisted on the latch; `while_` is evaluated against the round
that just finished. On continue, the loop body (header through latch) is reset
to pending and the next `runtime next` re-dispatches it — each activation of a
loop-body task gets a fresh `iter-NN/` round dir under its task folder. On stop,
the latch stays done and the region's exit edge releases downstream tasks. The
latest completed round is what `${task:<addr>}` references and downstream
consumers see; earlier rounds stay addressable via `${task:<addr>@<k>}`, and
`${task:<addr>@prev}` gives each round the previous iteration's output (null on
the very first iteration).

### runtime fail

```bash
$LOOM runtime fail "$WORKDIR" "$TASK_ADDRESS" --message "human reason"
```

Marks the task failed and writes `<task_workdir>/error.yaml` with the given
message. Used by callers to surface human/agent failures the CLI cannot detect
on its own (a human refuses, an external agent returns a fault). Prints `ok`.
The next `runtime next` raises `RunAborted`.

### runtime reset

```bash
$LOOM runtime reset "$WORKDIR" "$TASK_ADDRESS"
```

Flips the task back to `pending` and clears its generated artifacts —
`output.yaml`, `error.yaml`, diagnostic YAMLs (`skip-reason.yaml`,
`schema-error.yaml`, `stderr.yaml`), rendered `prompt.md` / `message.md`, and
every `iter-NN/` round dir. Region-aware: resetting any task inside a loop body
resets the whole region so round indexing restarts at `iter-00`. Latch `fuel`
is NOT restored — it reflects rounds already consumed. Caller-seeded
`input.yaml` (entries without an `input:` mapping) is preserved so the entry can
be re-run without rewriting the seed; mapping-driven `input.yaml` is deleted
and re-materialised on the next dispatch.

### runtime status

```bash
$LOOM runtime status "$WORKDIR"
```

Emits a YAML document with `total`, `is_done`, `is_stuck`, and per-status counts
(`pending`/`ready`/`running`/`done`/`failed`/`skipped`). Read-only.

### task new

```bash
$LOOM task new greet-user --loom-root ./loom
```

Creates `<loom-root>/<name>/` — folder only, no files inside. The authoring
agent then writes `io.yaml` by hand (see `schemas/io.yaml` for the shape) and
the body file appropriate to the task kind: tool → run `$LOOM task io-python
<name>` then write `tool.py` importing the generated `<TaskName>Input` /
`<TaskName>Output`; agent → write `prompt.md.j2`; human → write
`message.md.j2`.

- `<name>` — kebab-case, matches `^[a-z][a-z0-9-]*$`.
- `--loom-root PATH` — override the default (`./loom`).
- Raises `TaskFolderError` on bad name or when the folder already exists.

### task io-python

```bash
$LOOM task io-python greet-user --loom-root ./loom
```

Reads `<loom-root>/<name>/io.yaml` and (re)writes
`<loom-root>/<name>/io_types.py` — a generator-owned file with a header comment
`# generated from io.yaml vN by $LOOM task io-python — do not edit` carrying
`<TaskName>Input` / `<TaskName>Output` dataclasses. Each dataclass has
`VERSION: ClassVar[int] = <io.yaml version>`, fields derived from top-level
`properties` via the JSON→Python type map (`string→str`,
`integer→int`, `number→float`, `boolean→bool`, `array→list`,
`object→dict`), and `from_dict` / `to_dict` helpers. The whole file is
overwritten on every regenerate; prints `wrote io_types.py (vN)`.

- Only meaningful for tool tasks; not gated on kind.
- Entry-kind-agnostic — the command reads `io.yaml` and writes
  `io_types.py` next to whichever entry file exists (`tool.py` or
  `tool.sh`). Dispatch treats `io_types.py` as optional for shell tools
  (`tool.sh` fulfils its io contract by reading `input.yaml` and writing
  `output.yaml` directly via the argv contract), so a packaged shell
  tool's Python project may import the generated types if it wants
  but the engine never requires them for the shell branch.
- `--loom-root PATH` — override the default (`./loom`).
- Raises `TaskFolderError` if the task folder is missing; `IOYamlError` if
  `io.yaml` is missing or fails the meta-schema.

### graph new

```bash
$LOOM graph new
```

Idempotent. Two modes:

- **Absent `<loom-root>/graph.yaml`** — scaffolds a starter by discovering
  task folders and pinning each entry to the current `io.yaml` version.
  Prints `scaffolded <path> with N task(s)`.
- **Present `<loom-root>/graph.yaml`** — loads the existing file, preserves
  every authored field (task entries, `depends_on_all` / `any`, `when`,
  latches, subgraph entries and their `root` paths, ordering, extra fields),
  and restamps each entry's `version` from the referenced task folder's
  current `io.yaml`. Subgraph entries follow the pinning logic in
  `plan.to_graph_yaml`. Writes atomically. Prints `repinned N task(s)` or
  `unchanged`.

- `--loom-root PATH` — override the default (`./loom`).
- Raises `GraphYamlError` if the existing file fails the meta-schema.

### output init

```bash
$LOOM output init "$WORKDIR" --task greet-user
```

Seeds `<workdir>/tasks/<task-address>/output.yaml` from the task's
`io.yaml/output` schema with the schema defaults.

- `<workdir>` — the run's workdir.
- `--task <task-address>` — canonical task address.
- Non-zero exit if the task or workdir is missing.

### output add

```bash
$LOOM output add "$WORKDIR" --task greet-user \
    --set greeting='Hello' \
    --set meta.tone='cheerful'
```

Applies dotted-path assignments to the task's `output.yaml`, coerces each value,
validates, and writes atomically. Validation is PARTIAL: wrong field names
(`additionalProperties`) and wrong types fail immediately, but `required`
obligations are deferred so a document can be built across multiple calls —
completeness is enforced by `runtime complete`.

- `--set path=value` — repeatable; supports `field`, `field.sub`, explicit
  indices (`field.0` / `field[0]`), and `field[]` for list append
  (`field[-1]` targets the last element — e.g. `items[].name=a` then
  `items[-1].size=3`).
- `--set-json path=value` — same path grammar, but the value is parsed as
  JSON. Use it for explicit empty values (`items=[]`, `note=""`,
  `owner=null`) and nested structures the scalar grammar cannot express.
  Required by the io.md contract-soundness rule (when data may be absent,
  the producer emits the explicit empty value — it never omits a required
  field). `--set` / `--set-json` apply in CLI order and mix safely.
- Non-zero exit on schema failure, malformed path, or malformed JSON; the
  file on disk is not modified.

### validate

```bash
$LOOM validate <skill-root> [--graph PATH]
```

Runs the static validation set against a skill's `loom/` folder without
touching a workdir. The set includes the subtype-projection and required-wiring
passes described in the io.md section
[6b](references/io.md#6b-static-alignment-subtype-projection--required-wiring)
alongside composition, DAG, single-entry/exit, reference,
mapping-reserved-shadow, template, loop-admission, and tool-entry
(`validate_tool_entry`) checks.

- `<skill-root>` — the skill root.
- `--graph PATH` — optional path to a `graph.yaml` to validate; when omitted,
  validates `<skill-root>/loom/graph.yaml`. Named `--graph` (not `--plan`)
  because the file is a `graph.yaml`; `visualise --plan` targets a
  `plan.yaml`, so the two flags name their two distinct schemas.
- Exits non-zero on any `LoomPlanError`; every message quotes the schema field
  description or the exception `remedy`.

### visualise

```bash
$LOOM visualise <workdir>
```

Renders `plan.yaml` as an ASCII DAG with statuses, loop glyphs, and subgraph
child tasks under their subgraph header.

- `<workdir>` — run workdir; must contain `plan.yaml`.
- `--plan PATH` — stand-alone `plan.yaml` path (mutually exclusive with
  `<workdir>`).
- `-o PATH` — write output to a file instead of stdout.
- `--no-when` / `--no-loops` — omit `when` / loop-latch annotations.
- `--ascii-only` — 7-bit output (drops Unicode box-drawing glyphs).

## Defaults

| Command family                            | `--loom-root` default |
|-------------------------------------------|-----------------------|
| `task new`, `task io-python`, `graph new` | `./loom`              |
| `runtime init`                            | required (no default) |

`runtime init` has no default because the initial workdir MUST be pinned to an
explicit source graph — the flag is unbracketed in the API table. Auto-workdir
path derivation and the unconditional wipe-and-recreate contract live under
`### runtime init` above.

## References

- `references/guide.md` — step-by-step guide for building a loom skill;
  `references/hello-graph/` is the finished reference skill it builds.
- `references/guide-advanced.md` — advanced recipes (loops, subgraphs,
  contract evolution, host drive-loop rendering, task instancing via
  `ref`) split out from `guide.md` to keep each file under the
  reference-length cap. §11 covers task instancing via `ref` (one
  shared folder → many distinct graph entries).
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

Every command has a concrete DONE phrase so authoring, ingest, runtime, and
diagnostic callers all know when to move on.

| Status               | Criteria                                                              |
|----------------------|-----------------------------------------------------------------------|
| `DONE` (`runtime`)   | `next` returned `done: true` and `plan.yaml` validates                |
| `DONE` (task new)    | Task folder exists (empty; author writes bodies next)                 |
| `DONE` (task io-py)  | `io_types.py` regenerated at the current `io.yaml/version`            |
| `DONE` (graph new)   | Prints `scaffolded ...`, `repinned ...`, or `unchanged`               |
| `DONE` (output *)    | Task `output.yaml` validates against `io.yaml/output`                 |
| `DONE` (validate)    | Exit 0 with no `LoomPlanError`                                        |
| `DONE` (visualise)   | Exit 0 with the ASCII DAG printed                                     |
| `DONE_WITH_CONCERNS` | Task body wrote a non-empty `stderr.yaml` (tool ran, warnings logged) |
| `BLOCKED`            | Any `LoomPlanError` raised; nothing was written                       |
| `NEEDS_CONTEXT`      | Missing `<workdir>` / `<name>` / `<skill-root>` / `--loom-root`       |

Escalation: any failure surfaces the exception unchanged; there is no retry.
