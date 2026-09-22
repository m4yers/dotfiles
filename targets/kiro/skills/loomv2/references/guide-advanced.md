# Building a Loom Skill — Advanced

Continuation of [guide.md](guide.md). Sections 1–6 there cover the base recipe
(scaffold → tool → agent → human → wire graph.yaml → run). This file picks up
at loops and continues through subgraphs, contract evolution, host drive-loop
rendering, and task instancing. Cross-refs: [grammar.md](grammar.md), the
meta-schemas under `../schemas/`, and the reference skill at `hello-graph/`.

## Contents

- [7. Add a loop](#7-add-a-loop)
- [8. Embed a subgraph](#8-embed-a-subgraph)
- [9. Evolve a contract](#9-evolve-a-contract)
- [10. Render host drive-loop text](#10-render-host-drive-loop-text)
- [11. Task instancing via `ref`](#11-task-instancing-via-ref)

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
countdown per round) and `while_` (predicate string) — at least one MUST be set.
The loop body sees per-round outputs via the `${...@<k>}` and `${...@prev}`
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
cross-skill embed; it loads the child's default `graph.yaml`. To embed a
specific child variant instead, set `graph:` (exactly one of `root`/`graph`)
with a path to the graph FILE — the child loom root is derived as the file's
parent directory:

```yaml
  - id: review-docs
    kind: subgraph
    version: 1
    graph: ../child/loom/graph-s.yaml
```
 Child tasks are inlined under the instance id, so a task
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
subgraph `root` paths, task ordering) and only restamps each entry's `version`
from the referenced task folder. Any parent skill embedding this loom root as a
subgraph MUST also re-run `$LOOM graph new` against its own graph so the
subgraph entry picks up the new pin.

## 10. Render host drive-loop text

Host SKILL.md drive-loop wording is rendered from `../templates/`, not
hand-written:

```bash
RENDER=~/.kiro/skills/home/template/scripts/render.sh
for t in step-ingest step-drive-loop helper-dispatch-agent helper-drive-human-gate; do
    $RENDER --template ~/.kiro/skills/home/loomv2/templates/$t.md.j2 \
        --var prefix=SB --var shim=LOOM \
        --var skill_name=my-skill --var target='<op>' --allow-unused
done
```

Variables shared by every partial: `prefix` (shell-var prefix), `shim` (the
wrapper-script var), `skill_name`, and `target` (the primary parameter name).

`step-ingest.md.j2` renders as `### Step 1: Ingest`, just before
`### Step 2: Drive the loop`. It takes `loom_root_var` (a shell-var name
holding the absolute path to the loom skill's `loom/` folder) and
`set_assignments` (a pre-rendered list of `--set K=V` fragments to seed the
entry task) alongside the shared variables. Output is the DEFAULT auto-workdir
ingest — the rendered `WD=$($LOOM runtime init --loom-root "$LOOM_ROOT" {{
set_assignments }})` line lets the engine pick a fresh `/tmp/<skill>/<uuid>/`
workdir, wipe and recreate it unconditionally, and seed the entry task's
`input.yaml` in one call; the host captures the printed path via `$( )`.
Consumer skills MUST NOT re-implement the workdir-naming/wipe/init/seed logic in
per-skill Python, because forking it drifts from the canonical sequence rendered
by the partial.

`step-drive-loop` renders as `### Step 2: Drive the loop`; each `helper-*`
template's Jinja comment states its placement (`## Helper:` sections after
`## Workflow`).

## 11. Task instancing via `ref`

Sometimes one task-folder definition should back several distinct graph entries
— the same "research a question" agent running for `q1`, `q2`, `q3` in parallel,
or the same "score a candidate" tool applied per row. That is what the optional
`task_entry.ref` field is for.

```yaml
# loom/graph.yaml
tasks:
  - {id: seed, kind: tool, version: 1}
  - id: research-q1
    kind: agent
    version: 1
    ref: research
    depends_on_all: [seed]
    input: {question: "${task:seed:q1}"}
  - id: research-q2
    kind: agent
    version: 1
    ref: research
    depends_on_all: [seed]
    input: {question: "${task:seed:q2}"}
  - id: research-q3
    kind: agent
    version: 1
    ref: research
    depends_on_all: [seed]
    input: {question: "${task:seed:q3}"}
  - id: aggregate
    kind: tool
    version: 1
    depends_on_all: [research-q1, research-q2, research-q3]
    input:
      a1: "${task:research-q1:answer}"
      a2: "${task:research-q2:answer}"
      a3: "${task:research-q3:answer}"
```

Only one folder — `loom/research/` — exists on disk, carrying the one
`io.yaml`, `prompt.md.j2`, and version pin. `research-q1`, `research-q2`, and
`research-q3` each become a distinct graph node with:

- Its own `id`, which is the canonical address for every downstream
  reference (`${task:research-q1:answer}`), for the CLI (`$LOOM output add`
  `<workdir> --task research-q1 …`), and for the workdir path
  (`<workdir>/tasks/NN-research-q1/output.yaml`).
- Its own materialised `input.yaml`, resolved from that entry's own `input:`
  mapping — so `research-q1` sees `{question: <q1 value>}` and
  `research-q2` sees `{question: <q2 value>}`, drawn from the same shared
  `research/io.yaml/input` schema.
- Its own status, per-round `iter-NN/`, and (if the entry participates in a
  loop) its own latch fuel and `while_` state.

**Rules.**

- `ref` MUST be a bare kebab-cased folder name (`^[a-z][a-z0-9-]*$`) sitting
  directly under the same loom root as `graph.yaml`. Cross-loom-root reuse is
  a non-goal — that is what `kind: subgraph` covers.
- `ref` is valid on `kind ∈ {tool, agent, human}`. It MUST NOT appear on
  `kind: subgraph`, because `kind: subgraph` already carries its own `root:`
  field for cross-graph reuse — the schema and `validate/composition.py` both
  fail closed with `TaskRefError` if you try.
- The referenced folder's detected kind (from the body file — `tool.py`,
  `tool.sh`, `prompt.md.j2`, `message.md.j2`) MUST match the entry's declared
  `kind`. Composition validation rejects mismatches with `TaskRefError`.
- `$LOOM graph new` restamp mode preserves authored `ref` fields verbatim
  and re-pins each entry's `version` against the SHARED folder's current
  `io.yaml/version`, so all instances stay locked to one contract.
- Loop latches attach to the graph entry's `id`, not to the shared folder,
  so two instances of the same folder MAY carry independent latches.

**When to use `ref` vs `subgraph`.** Prefer `ref` for a single-task fan-out —
one folder, N graph entries with different inputs. Prefer `subgraph` (§8) when
the fan-out spans a whole graph, so the child skill's `loom/graph.yaml` becomes
reusable as a single dependency edge. `ref` keeps its scope inside one loom
root; `subgraph` crosses skill boundaries.

Cross-refs: [`../schemas/graph.yaml`](../schemas/graph.yaml) for the
`task_entry.ref` field and the instancing example; [§5 in guide.md](guide.md#5-wire-graphyaml)
for the base `graph.yaml` shape; [§8](#8-embed-a-subgraph) for the contrast
with subgraph embedding.

## 12. Multiple graph variants in one loom root

A loom root may carry several static graph files (e.g.
`graph-s.yaml`, `graph-m.yaml`, `graph-l.yaml`) sharing the same
task folders. Select one at init:

```bash
$LOOM runtime init --loom-root ./loom --graph graph-l.yaml ...
$LOOM validate <skill-root> --graph ./loom/graph-l.yaml
```

The graph file is read ONCE at `runtime init`; the composed plan is
persisted to `plan.yaml`, so no other command needs the flag.

Rules of the shape:

1. Every variant is a complete, static, independently valid graph —
   variants differ in fan-out arity (how many `ref:` instances of a
   shared definition they declare) and in literal input values,
   never in the behavior of shared tasks.
2. Contracts are SHARED: `io.yaml` lives in the task folder, so one
   schema serves every variant. Size producer fixed-slot arrays to
   the LARGEST arity any variant wires (static projection of
   `arr[i]` requires `minItems > i`). Consumer fields above the
   smallest variant's arity leave `required` — a smaller graph
   simply does not wire them, and templates guard them with
   `| default('')`.
3. Per-variant capacity flows as literal graph inputs (e.g.
   `max_questions: "3"` in graph-m vs `"5"` in graph-l), so shared
   prompts read their cap from input instead of hardcoding it.
4. Drift is the failure mode: a wiring edit must land in EVERY
   variant. Put a sync-warning comment at the top of each file and
   run `$LOOM validate --graph` for each variant in CI/pre-commit.
5. When no `graph.yaml` exists (variants only), every `runtime
   init` MUST pass `--graph`; bare `validate <skill-root>` will
   fail — validate each variant explicitly.
