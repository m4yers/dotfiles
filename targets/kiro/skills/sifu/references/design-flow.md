# Design Guidance: flow

What `design-author` populates for a `flow` skill. Rules live in
`flow-conventions.md`.

- `sections` — `Invariants` (rules that hold across every adaptation),
  `Workflow` (one entry per `### Step N`: goal, default sub-steps, where
  the operator may redirect), `Rules`. Dependencies, Parameters, Aliases,
  and Completion come from `templates/skill/flow.md.j2`.
- `files` — `scripts/*` for every deterministic operation the steps call,
  plus reference files for content needed only in some steps.
- `tasks` — empty.
- `rationale` — at most ~5 bullets: why `flow` over `workflow`, where
  state lives, which operations are scripted.
