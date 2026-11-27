# Design Guidance: workflow

What `design-author` populates for a `workflow` skill. Rules live in
`workflow-conventions.md`; the graph mechanics in
`~/.kiro/skills/home/loomv2/references/guide.md`.

- `sections` — usually empty; `templates/skill/workflow.md.j2` supplies
  the standard SKILL.md sections. Add a `Rules` section for skill-specific
  rules.
- `files` — every graph file (`loom/graph.yaml` or `graph-<variant>.yaml`),
  one `loom*/<task>/` entry per task folder (outline: `io.yaml` fields plus
  body file), shared `schemas/*.yaml`, reference files, and any
  `scripts/` package that backs `tool.sh` bodies.
- `tasks` — every graph entry in dispatch order: `id`, `kind`,
  `depends_on`, `description` (1-2 sentences: what it consumes, what it
  produces, the one decision it makes). Set `ref` on every instance of a
  shared folder and describe only the first; later instances read
  "Instance N of <first-id>". Set `when` for gated tasks and `latch` on
  loop latches (`header`, `fuel`, `while`).
- `cli_surface` — subcommands of any packaged tool shim; empty when tool
  bodies are plain `tool.py`.
- `rationale` — at most ~5 bullets: DAG shape, fan-out, subgraph reuse,
  determinism, alternatives rejected.

Checklist:

1. Single entry `ingest-input`, single exit `publish-output`.
2. Each loop's outflow leaves through its latch.
3. Each io.yaml field a downstream task needs is in its producer's
   `required` output, or the consumer accepts `null`.
