# Building a Loom Skill

Step-by-step recipe. `$LOOM` = `~/.kiro/skills/home/loomv2/scripts/loom.sh`.
The complete reference skill built by these steps lives at `hello-graph/`
alongside this file (all task kinds plus an embedded subgraph) and is executed
by the test suite. Cross-refs: [grammar.md](grammar.md) and the meta-schemas
under `../schemas/`. Sections 1–6 below cover the base recipe (scaffold → tool
→ agent → human → wire graph.yaml → run); the advanced recipes (loops,
subgraphs, contract evolution, host drive-loop rendering, task instancing) live
in [guide-advanced.md](guide-advanced.md) — split out to keep each reference
file under the length cap.

## Contents

- [1. Scaffold the loom root](#1-scaffold-the-loom-root)
- [2. Tool task](#2-tool-task)
- [2a. Shell shim (`tool.sh`)](#2a-shell-shim-toolsh)
- [3. Agent task](#3-agent-task)
- [4. Human task](#4-human-task)
- [5. Wire graph.yaml](#5-wire-graphyaml)
- [6. Run the graph](#6-run-the-graph)

Advanced topics (see [guide-advanced.md](guide-advanced.md)):

- 7\. Add a loop
- 8\. Embed a subgraph
- 9\. Evolve a contract
- 10\. Render host drive-loop text
- 11\. Task instancing via `ref`

## 1. Scaffold the loom root

```bash
mkdir -p my-skill/loom && cd my-skill
$LOOM task new greet-user --loom-root ./loom
$LOOM task new summarise  --loom-root ./loom
$LOOM task new confirm    --loom-root ./loom
```

`task new` creates an empty folder per task; no files are seeded. For each
folder, author `io.yaml` by hand (see `../schemas/io.yaml` for the shape), then:

- For a **tool** task: run `$LOOM task io-python <name>` to generate
  `io_types.py`, then write `tool.py` importing the generated dataclasses.
- For an **agent** task: write `prompt.md.j2`.
- For a **human** task: write `message.md.j2`.

Once all task folders have their `io.yaml`, generate `graph.yaml`:

```bash
$LOOM graph new --loom-root ./loom
```

`graph new` discovers task folders, guesses `kind` from the body file
present, and pins each entry to the current `io.yaml/version`.

**Choosing a task kind.** Prefer `tool` for anything a Python body can do
deterministically — arithmetic, file IO, deterministic parsing, HTTP calls with
fixed shape. Reserve `agent` for work that genuinely needs reasoning or
synthesis (summarising free-text, judging quality, choosing alternatives).
Spawning a sub-agent for a job a tool can do burns tokens and adds latency for
no gain; sections 2, 3, and 4 below cover each kind in turn.

## 2. Tool task

Author `io.yaml` first:

```yaml
# loom/greet-user/io.yaml — authored by you
version: 1
input:
  type: object
  additionalProperties: false
  properties:
    name: {type: string}
  required: [name]
output:
  type: object
  additionalProperties: false
  properties:
    greeting: {type: string}
  required: [greeting]
```

Generate `io_types.py`:

```bash
$LOOM task io-python greet-user --loom-root ./loom
# -> wrote io_types.py (v1)
```

```python
# loom/greet-user/io_types.py  (abbreviated — fully generator-owned)
# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class GreetUserInput:
    VERSION: ClassVar[int] = 1
    name: str
    # from_dict / to_dict helpers ...


# GreetUserOutput follows the same shape with fields from io.yaml/output.
```

Write `tool.py` by hand — user-owned, imports the generated dataclasses:

```python
# loom/greet-user/tool.py — authored by you
from io_types import GreetUserInput, GreetUserOutput


def greet_user(inp: GreetUserInput) -> GreetUserOutput:
    return GreetUserOutput(greeting=f"Hello, {inp.name}!")
```

Regenerate `io_types.py` after every `io.yaml` change (whole file is
overwritten). Dispatch loads `io_types.py` (missing → `ToolTaskError` with a
`$LOOM task io-python <id>` remedy), version-checks
`<TaskName>Input.VERSION == <TaskName>Output.VERSION == io.yaml/version`
(drift → `ToolIOVersionMismatchError`), then loads `tool.py` with `io_types`
temporarily registered in `sys.modules`. Function name MUST equal
`snake_case(<task-id>)`. Tool tasks run internally in `runtime next` and
never appear in the `ready` batch.

### 2a. Shell shim (`tool.sh`)

Tool tasks that need third-party Python dependencies (mdformat, requests, …)
are packaged as uv projects and dispatched via a `tool.sh` shim placed at the
task folder root. `tool.sh` is an **alternative entry point** to `tool.py` —
the two are mutually exclusive; if both are present in the same task folder,
validate/init fail with `AmbiguousToolEntryError`. `io.yaml` is authored exactly
as for a `tool.py` task and lives next to `tool.sh`.

**Dispatch contract (single source of truth).** The engine invokes the shim as

```
tool.sh <input.yaml> <output.yaml>
```

— positional argv, in that order — with `cwd = <task workdir for the round>`,
the same folder the two argv paths live in. No `LOOM_*` environment variables
are passed: argv is the whole contract. The shim reads the materialised
`input.yaml` from `$1`, writes `output.yaml` at `$2`, and exits 0. Non-zero
exit surfaces as `ToolTaskError` carrying the task id and the last 2000
characters of the shim's stderr; the engine also writes `error.yaml` and
`stderr.yaml` alongside the task workdir, matching the `tool.py` failure
surface.

`$LOOM runtime complete` runs the same output-schema validation on the shim's
`output.yaml` as it does for `tool.py` tasks; the engine never parses or
reshapes what the shim wrote.

**Rules.**

- `tool.sh` MUST be executable (`chmod +x tool.sh`) and MUST start with
  a `#!` shebang line (e.g. `#!/usr/bin/env bash`) — validate rejects
  either violation with `ToolShimNotExecutableError`.
- `$LOOM task io-python <name>` stays entry-kind-agnostic: it operates
  on `io.yaml` and writes `io_types.py` next to whichever entry file
  exists. A packaged shell tool's Python project MAY import the
  generated types if it wants; dispatch never requires them for shell
  tools.
- `tool.py` and `tool.sh` MUST NOT both live in the same task folder, because
  dispatch cannot choose between two entry points and static validation would
  fail closed.

`references/hello-graph/loom/banner-sh/` is the canonical example — a
minimal shim that reads `greeting` from `$1` and writes
`banner: "*** <greeting> ***"` to `$2` using stdlib-only YAML I/O.

## 3. Agent task

```yaml
# loom/summarise/io.yaml
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

```jinja
{# loom/summarise/prompt.md.j2 #}
Summarise this greeting in one line: {{ input.greeting }}

Write your answer:

```
$LOOM output add {{ workdir }} --task summarise \
    --set summary='<one-line summary>'
```
```

Jinja context: only `input` (the validated `input.yaml`). Two reserved default
objects (`__loom`, `__task`) are engine-provided; declare them in the task's
`io.yaml/input` to use as `{{ input.__loom.workdir }}` and
`{{ input.__task.id }}` (see [io.md](io.md)). Inside non-Jinja surfaces
(`input.yaml`, `when` predicates, `--set` values) use the placeholder grammar
instead — for example `${input:greeting}` projects into the current task's own
input via JMESPath. Full table in [grammar.md](grammar.md).

## 4. Human task

```jinja
{# loom/confirm/message.md.j2 #}
Please confirm this summary:

{{ input.summary }}

Ask the user for `decision` (accept | revise) and optional `reason`:

```
$LOOM output add {{ workdir }} --task confirm \
    --set decision='accept' --set reason='<user reason>'
```
```

Render context matches agent tasks. Human tasks surface `message_path` in the
`ready` batch: the caller presents the file to the user, writes `output.yaml`
via `$LOOM output add`, then calls `$LOOM runtime complete`.

## 5. Wire graph.yaml

```yaml
# loom/graph.yaml
tasks:
  - {id: greet-user, kind: tool,  version: 1}
  - {id: summarise,  kind: agent, version: 1, depends_on_all: [greet-user]}
  - {id: confirm,    kind: human, version: 1, depends_on_all: [summarise]}
```

Each entry pins the `io.yaml/version` seen at authoring time; drift raises
`TaskVersionMismatchError` at `$LOOM runtime init`. Use `depends_on_all` (AND)
or `depends_on_any` (OR) to declare edges. A graph MUST have exactly one entry
task and exactly one exit task — those two schemas are the graph's own IO
contract, which is what lets it embed as a subgraph.

## 6. Run the graph

```bash
LOOM=~/.kiro/skills/home/loomv2/scripts/loom.sh
WORKDIR=$($LOOM runtime init --loom-root ./loom \
    --set name=Alice)
while true; do
    yaml=$($LOOM runtime next "$WORKDIR")    # schemas/next.yaml
    [ "$(echo "$yaml" | yq '.done')" = "true" ] && break
    # Agent entries in `ready` are independent by DAG construction and MUST
    # be dispatched IN PARALLEL — see `templates/step-drive-loop.md.j2` for
    # the authoritative host-skill fan-out pattern; the loop below is
    # bookkeeping only.
    for id in $(echo "$yaml" | yq '.ready[].id'); do
        # kind=agent → dispatch prompt_path to sub-agent (parallel across ids)
        # kind=human → present message_path to the user
        $LOOM output add "$WORKDIR" --task "$id" --set <field>=<value>
        $LOOM runtime complete "$WORKDIR" "$id"
    done
done
```

The auto-workdir `runtime init --loom-root ... --set K=V ...` form is the
DEFAULT ingest pattern: the engine picks a fresh `/tmp/<skill_name>/<uuid>/`
workdir, wipes and recreates it unconditionally, seeds the entry task's
`input.yaml` in one call, and prints the path on stdout so `$( )` captures it.
Escape hatch: when the entry has a mapping-bound input or a hand-written seed is
easier, pass an explicit workdir path (`$LOOM runtime init "$WORKDIR"
--loom-root ./loom`) and write `<workdir>/tasks/<NN>-<entry>/input.yaml` by hand
before the first `runtime next`.

`$LOOM runtime next` runs tool tasks internally and prints a
[`schemas/next.yaml`](../schemas/next.yaml) document to stdout; parse it, then
for every entry in `ready` write `output.yaml` and call
`$LOOM runtime complete`. On abort, exit is non-zero and stderr carries
`{failed_task, error_path}`.


______________________________________________________________________

Continue with advanced recipes (loops, subgraphs, contract evolution, host
drive-loop rendering, task instancing) in
[guide-advanced.md](guide-advanced.md).
