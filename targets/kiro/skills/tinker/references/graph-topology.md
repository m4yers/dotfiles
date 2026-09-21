# Tinker Graph Topology

Latch mapping and other structural details for `loom/graph.yaml`. The runtime
driver reads `ready[].id` from `runtime next` and does not need this table; it
exists for authors modifying the graph itself.

## Loop Latches

| Latch                 | Header          | Fuel | Predicate                                                       |
| --------------------- | --------------- | ---- | --------------------------------------------------------------- |
| `design-review-merge` | `design-author` | 5    | `${task:design-review-merge:decision} == 'revise'`              |
| `tasks-review-merge`  | `tasks-author`  | 5    | `${task:tasks-review-merge:decision} == 'revise'`               |
| `review-fix`          | `verify-tests`  | 5    | `${task:review-fix:verdict} != 'approved'`                      |

A `review-fix` iteration re-runs `verify-tests`, all three
`review-diffs-{swe,d1,d2}` instances, and `review-diffs-merge`.
