# Reference Grammar

Placeholder forms recognised in graph.yaml `input:` mappings and in
`when` / `while_` predicates — the two surfaces where the engine reaches
across task boundaries. Source of truth: the `GRAMMAR` table in
`scripts/loom/loom/engine/resolve.py`. Parse failures raise
`ReferenceError` at `$LOOM runtime init`.

`<addr>` is a task's canonical address: `<namespace-path>/<task-name>`, the
namespace path being the chain of parent-chosen subgraph instance ids (empty
at the root, e.g. `lint`; nested, e.g. `review-docs/lint`).

| Token | Meaning |
|---|---|
| `$${...}` | Literal `${...}`. Escape hatch — resolver leaves this untouched. |
| `${workdir}` | Absolute path to the ROOT workdir. Child tasks share this. |
| `${task_workdir}` | Absolute path to the current task's folder. |
| `${task:<addr>@<k>}` | Loop body: absolute round `k` output. |
| `${task:<addr>@prev}` | Loop body: previous round's output (see below). |
| `${task:<addr>:<jmespath>}` | Upstream task output projected via JMESPath. |
| `${task:<addr>}` | Latest completed round of upstream task's `output.yaml`. |
| `${task_path:<addr>}` | Absolute path to upstream task folder. |
| `${input:<jmespath>}` | Current task's `input.yaml` projected via JMESPath. |

`${task:<addr>@prev}` semantics: the previous iteration's output, relative to
the reading task's round — null on the very first iteration. Inside a latch
`while_`, this is the round before the one that just finished. When read from
outside the loop region, it resolves to the final round.

`${input:...}` applies to the current task's own materialised input.yaml — it
is the only form that reads task-local state and is available inside Jinja
bodies for convenience. Every other `${task:...}` form is a cross-task ref and
must appear in a mapping value or a predicate; the static validator rejects
mapping refs that target tasks not declared in
`depends_on_all` / `depends_on_any`.

Escape rule: `$${...}` survives resolution and is rewritten to literal `${...}`
after all other tokens are substituted. Unknown placeholders are left untouched
so downstream validation can flag them.


## Naming conventions

- The graph's ENTRY task SHOULD be named `ingest-input`: it declares
  the graph's exact input parameters (each field schema'd and
  described in its io.yaml/input). For subgraph-embeddable graphs it
  is typically a pass-through tool so the contract stays explicit.
- The graph's EXIT task SHOULD be named `publish-output`: its
  io.yaml/output IS the graph's contract — every field the parent
  may reference, declared flat (no opaque wrapper objects like an
  "envelope"; parents wire exact fields, the validator projects each
  ref against the schema).
- Rationale: uniform entry/exit names make cross-skill embeds
  scannable (`${task:<instance>:<field>}` always addresses a
  publish-output), and flat contracts keep every dependency visible
  and individually validated.
