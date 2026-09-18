# Commands

Per-command contract for the CLI (`$LOOM` =
`~/.kiro/skills/home/loomv2/scripts/loom.sh`). Summary tables live in
SKILL.md `## API`; sections below are ordered to match those tables:
`runtime init` → `next` → `complete` → `fail` → `reset` → `status`;
`task new` → `task io-python`; `graph new`; `output init` → `output add`;
`validate`; `visualise`.

## Contents

- [runtime init](#runtime-init)
- [runtime next](#runtime-next)
- [runtime complete](#runtime-complete)
- [runtime fail](#runtime-fail)
- [runtime reset](#runtime-reset)
- [runtime status](#runtime-status)
- [task new](#task-new)
- [task io-python](#task-io-python)
- [graph new](#graph-new)
- [output init](#output-init)
- [output add](#output-add)
- [validate](#validate)
- [visualise](#visualise)

## runtime init

Two equivalent shapes.

**Default (auto workdir)** — omit the workdir positional, let the
engine name and create it under `/tmp`, capture the printed path:

```bash
WD=$($LOOM runtime init --loom-root "$LOOM_ROOT" [--set K=V ...])
```

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
  [io.md §6b](io.md#6b-static-alignment-subtype-projection--required-wiring).

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

  See `## runtime reset` below for the caller-seeded-preservation
  semantics that carry through when the entry is re-run after seeding.

- Non-zero exit on any `LoomPlanError`; nothing is written when validation
  fails.

## runtime next

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
contract documented in [guide.md §2a](guide.md#2a-shell-shim-toolsh):
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

## runtime complete

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

## runtime fail

```bash
$LOOM runtime fail "$WORKDIR" "$TASK_ADDRESS" --message "human reason"
```

Marks the task failed and writes `<task_workdir>/error.yaml` with the given
message. Used by callers to surface human/agent failures the CLI cannot detect
on its own (a human refuses, an external agent returns a fault). Prints `ok`.
The next `runtime next` raises `RunAborted`.

## runtime reset

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

## runtime status

```bash
$LOOM runtime status "$WORKDIR"
```

Emits a YAML document with `total`, `is_done`, `is_stuck`, and per-status counts
(`pending`/`ready`/`running`/`done`/`failed`/`skipped`). Read-only.

## task new

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

## task io-python

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

## graph new

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

## output init

```bash
$LOOM output init "$WORKDIR" --task greet-user
```

Seeds `<workdir>/tasks/<task-address>/output.yaml` from the task's
`io.yaml/output` schema with the schema defaults.

- `<workdir>` — the run's workdir.
- `--task <task-address>` — canonical task address.
- Non-zero exit if the task or workdir is missing.

## output add

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

## validate

```bash
$LOOM validate <skill-root> [--graph PATH]
```

Runs the static validation set (see the `Rules` section) against a skill's
`loom/` folder without touching a workdir. The set includes the
subtype-projection and required-wiring passes described in the io.md section
[6b](io.md#6b-static-alignment-subtype-projection--required-wiring) alongside
composition, DAG, single-entry/exit, reference, mapping-reserved-shadow,
template, loop-admission, and tool-entry (`validate_tool_entry`) checks.

- `<skill-root>` — the skill root.
- `--graph PATH` — optional path to a `graph.yaml` to validate; when omitted,
  validates `<skill-root>/loom/graph.yaml`. Named `--graph` (not `--plan`)
  because the file is a `graph.yaml`; `visualise --plan` targets a
  `plan.yaml`, so the two flags name their two distinct schemas.
- Exits non-zero on any `LoomPlanError`; every message quotes the schema field
  description or the exception `remedy`.

## visualise

```bash
$LOOM visualise <workdir>
```

Renders `plan.yaml` as an ASCII DAG with statuses, loop glyphs, and subgraph
child tasks under their subgraph header.

- `<workdir>` — run workdir; must contain `plan.yaml`.
