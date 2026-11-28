# Design Guidance: tool

What `design-author` populates for a `tool` skill. Rules live in
`tool-conventions.md`.

- `sections` — typically one numbered Steps section.
- `files` — `scripts/*` (shim plus helpers) and any reference files.
- `cli_surface` — the main shim's subcommands, when it has any.
- `tasks` — empty.
- `rationale` — at most ~5 bullets: script layout, error handling,
  alternatives rejected.
