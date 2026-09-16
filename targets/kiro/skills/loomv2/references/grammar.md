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
| `${task:<addr>@prev}` | Loop body: the round before the latest completed round. |
| `${task:<addr>:<jmespath>}` | Upstream task output projected via JMESPath. |
| `${task:<addr>}` | Latest completed round of upstream task's `output.yaml`. |
| `${task_path:<addr>}` | Absolute path to upstream task folder. |
| `${input:<jmespath>}` | Current task's `input.yaml` projected via JMESPath. |

`${input:...}` applies to the current task's own materialised input.yaml — it
is the only form that reads task-local state and is available inside Jinja
bodies for convenience. Every other `${task:...}` form is a cross-task ref and
must appear in a mapping value or a predicate; the static validator rejects
mapping refs that target tasks not declared in
`depends_on_all` / `depends_on_any`.

Escape rule: `$${...}` survives resolution and is rewritten to literal `${...}`
after all other tokens are substituted. Unknown placeholders are left untouched
so downstream validation can flag them.
