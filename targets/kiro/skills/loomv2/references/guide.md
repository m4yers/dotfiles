# Building a Loom Skill

Step-by-step recipe. `$LOOM` = `~/.kiro/skills/home/loomv2/scripts/loom.sh`.
The complete reference skill built by these steps lives at
`../examples/hello-graph/` (all task kinds plus an embedded subgraph) and is
executed by the test suite. Cross-refs: [commands.md](commands.md),
[grammar.md](grammar.md), and the meta-schemas under `../schemas/`.

Contents:

- [1. Scaffold the loom root](#1-scaffold-the-loom-root)
- [2. Tool task](#2-tool-task)
- [3. Agent task](#3-agent-task)
- [4. Human task](#4-human-task)
- [5. Wire graph.yaml](#5-wire-graphyaml)
- [6. Run the graph](#6-run-the-graph)
- [7. Add a loop](#7-add-a-loop)
- [8. Embed a subgraph](#8-embed-a-subgraph)
- [9. Evolve a contract](#9-evolve-a-contract)
- [10. Render host drive-loop text](#10-render-host-drive-loop-text)

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
synthesis (summarising free-text, judging quality, choosing between
alternatives). Spawning a sub-agent for a job a tool can do burns tokens and
adds latency for no gain; sections 2, 3, and 4 below cover each kind in turn.

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
    @classmethod
    def from_dict(cls, d): ...
    def to_dict(self): ...


@dataclass
class GreetUserOutput:
    VERSION: ClassVar[int] = 1
    greeting: str
    ...
```

Write `tool.py` by hand — user-owned, imports the generated dataclasses:

```python
# loom/greet-user/tool.py — authored by you
from io_types import GreetUserInput, GreetUserOutput


def greet_user(inp: GreetUserInput) -> GreetUserOutput:
    return GreetUserOutput(greeting=f"Hello, {inp.name}!")
```

Regenerate `io_types.py` after every `io.yaml` change; the entire file is
overwritten. Dispatch loads `io_types.py` (missing → `ToolTaskError` with a
`$LOOM task io-python <id>` remedy), version-checks
`<TaskName>Input.VERSION == <TaskName>Output.VERSION == io.yaml/version`
(drift → `ToolIOVersionMismatchError`), then loads `tool.py` with `io_types`
temporarily registered in `sys.modules` so the import resolves. Function name
MUST equal `snake_case(<task-id>)`, so the engine's tool dispatcher can find
it. `$LOOM runtime next` runs tool tasks internally; they never appear in the
`ready` batch surfaced to callers.

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
objects (`__loom`, `__task`) are engine-provided. Declare them in the task's
io.yaml/input to use as `{{ input.__loom.workdir }}`, `{{ input.__task.id }}`,
and so on. See [io.md](io.md) for the declaration recipe. Inside non-Jinja
surfaces (`input.yaml`, `when` predicates, `--set` values) use the placeholder
grammar instead — for example `${input:greeting}` projects into the current
task's input via JMESPath. Full table in [grammar.md](grammar.md).

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
WORKDIR=$(mktemp -d)
$LOOM runtime init "$WORKDIR" --loom-root ./loom
while true; do
    yaml=$($LOOM runtime next "$WORKDIR")    # schemas/next.yaml
    done=$(echo "$yaml" | yq '.done')
    [ "$done" = "true" ] && break
    for id in $(echo "$yaml" | yq '.ready[].id'); do
        # kind=agent → dispatch prompt_path to sub-agent
        # kind=human → present message_path to the user
        $LOOM output add "$WORKDIR" --task "$id" --set <field>=<value>
        $LOOM runtime complete "$WORKDIR" "$id"
    done
done
```

`$LOOM runtime next` runs tool tasks internally and prints a
[`schemas/next.yaml`](../schemas/next.yaml) document to stdout; parse it, then
for every entry in `ready` write `output.yaml` and call
`$LOOM runtime complete`. On abort, the command exits non-zero and writes
`{failed_task, error_path}` to stderr.

## 7. Add a loop

```yaml
# loom/graph.yaml
tasks:
  - {id: fetch,   kind: tool,  version: 1}
  - {id: fix,     kind: agent, version: 1, depends_on_all: [fetch]}
  - {id: review,  kind: agent, version: 1, depends_on_all: [fix]}
  - {id: publish, kind: tool,  version: 1, depends_on_all: [review]}
latches:
  - task: review
    header: fix
    fuel: 5
    while_: "${task:review:verdict != 'approved'}"
```

```jinja
{# loom/fix/prompt.md.j2 — diff against the previous round #}
Previous review: {{ '${task:review@prev}' }}
Latest review:   {{ '${task:review}' }}
```

A latch turns `review` into a back-edge onto `fix`, so the natural-loop body
between header and latch reruns each round. Exit controls are `fuel` (positive
countdown per round) and `while_` (predicate string) — at least one MUST be
set. The loop body sees per-round outputs via the `@<k>` and prev-round
placeholders documented in [grammar.md](grammar.md).

## 8. Embed a subgraph

```yaml
# parent/loom/graph.yaml
tasks:
  - {id: fetch, kind: tool, version: 1}
  - id: review-docs
    kind: subgraph
    version: 1
    root: ../child/loom
    depends_on_all: [fetch]
  - id: publish
    kind: tool
    version: 1
    depends_on_all: [review-docs]
```

`root` is resolved relative to the declaring `graph.yaml`, or absolute for a
cross-skill embed. Child tasks are inlined under the instance id, so a task
`lint` inside `review-docs` addresses as `review-docs/lint` — this is the
canonical namespace-path surfaced by `$LOOM runtime next`. The child graph's
entry `input` and exit `output` become the subgraph's own IO contract, so
parents can wire `depends_on_all` against the instance id as if it were a single
task. Reusing the same `root` under distinct instance ids (e.g. `review-code`
and `review-docs`) is allowed and gives each its own private namespace.


## 9. Evolve a contract

```bash
# 1. Bump the task's io.yaml version.
sed -i 's/^version: 1/version: 2/' loom/greet-user/io.yaml
# 2. For tool tasks: regenerate io_types.py from the new io.yaml.
$LOOM task io-python greet-user --loom-root ./loom
# 3. Re-pin every graph.yaml entry to the new version on disk.
$LOOM graph new --loom-root ./loom
# 4. Validate before running.
$LOOM validate .
```

`$LOOM task io-python` overwrites the whole `io_types.py` from the current
`io.yaml`; `tool.py` is user-owned and untouched. `$LOOM graph new` is
idempotent: it preserves every authored field (deps, `when`, latches, and
subgraph `root` paths, task ordering) and only restamps each entry's
`version` from the referenced task folder. Any parent skill embedding this
loom root as a subgraph MUST also re-run `$LOOM graph new` against its own graph
so the subgraph entry picks up the new pin.


## 10. Render host drive-loop text

Host SKILL.md drive-loop wording is rendered from `../templates/`, not
hand-written:

```bash
RENDER=~/.kiro/skills/home/template/scripts/render.sh
for t in step-drive-loop helper-dispatch-agent helper-drive-human-gate; do
    $RENDER --template ~/.kiro/skills/home/loomv2/templates/$t.md.j2 \
        --var prefix=SB --var shim=LOOM \
        --var skill_name=my-skill --var target='<op>' --allow-unused
done
```

Variables: `prefix` (shell-var prefix), `shim` (wrapper-script var),
`skill_name`, `target` (primary parameter). Each template's Jinja comment
states its heading and placement — `step-drive-loop` renders under `##
Workflow`, `helper-*` as `## Helper:` sections after it.
