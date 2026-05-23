---
name: loom-curator
type: workflow
description: >-
  Curator on top of loom. Drives sub-agents to ingest a source into
  an Obsidian vault. The execution plan is derived from quintet.yaml
  and the templates/extractors/ directory layout, then driven by loom.
  Use when the user says "loom-curator", "loom-ingest", or wants to
  ingest a source via the loom-based curator. Do NOT use for the
  legacy curator skill — that has its own SKILL.md.
---

# Loom-curator

Identical purpose to legacy curator — ingest a source (URL or file)
into an Obsidian vault via LLM-driven extraction — but plan derivation
and execution are loom-driven. The plan is derived at runtime from
`quintet.yaml` + `templates/extractors/` directory layout.

## Status

Under construction (Phase A scaffold complete; Phase B–H pending).

## Parameters

TODO: Phase C will define CLI parameters for `ingest`, `next`,
`complete`, `status`.

## Workflow

TODO: Phase C will document the loom-driven workflow steps.

## Helpers

- `scripts/curator.sh` — CLI entry point
- `scripts/yq.sh` — YAML query helper

## Rules

- All extraction is loom-driven; no manual stage transitions.
- Plan is frozen at `ingest` time; no runtime extension.
- Every agent task pairs with a separate judge task.

## Completion

TODO: Phase C will define completion criteria.
