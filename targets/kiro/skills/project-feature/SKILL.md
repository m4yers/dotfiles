---
name: project-feature
type: workflow
description: Loomv2-driven feature development pipeline — composes project-overview (workspace intelligence), project-design (research/design/review), and project-engineering (tasks/implementation/code-review) as sibling subgraphs in one graph. Use when the user says "project feature", "tinker" (legacy alias), "full dev loop", or wants an end-to-end feature pipeline in any repo. Do NOT use for the PADB-specific pipeline — use feature-make instead. Do NOT use for skill creation — use dojo instead.
---

# Project Feature

A PURE COMPOSER: drives a feature end-to-end by wiring three
independent sibling skills in one loomv2 graph — `overview`
(project-overview: workspace intelligence, cached per
workspace+commit) → `design` (project-design: research → design →
review panel → human design gate) → `engineering`
(project-engineering: tasks → branch → implementation pool →
verify → diff review → human final gate). The skills do not know
each other; this graph is the only connection point, wiring each
sibling's publish-output fields into the next sibling's
ingest-input parameters.

The human touches the run at `design/design-gate` (always),
`engineering/branch-gate` (dirty tree only), and
`engineering/final-gate` (always).

## Dependencies

- `loomv2` — DAG execution engine.
- `project-overview`, `project-design`, `project-engineering` —
  the composed sibling skills.
- `tiling` — activity tracking during the run.

## Parameters

- **description** (required): free-text feature request.
- **workspace** (required): absolute path to the target workspace.
- **build-system** / **test-system** (optional): family overrides
  that win over manifest detection.
- **cache-mode** (optional): `read-write` (default), `read-only`,
  `write-only`, or `bypass`.
- **scale** (optional): `s`, `m` (default), or `l` — selects
  `loom/graph-<scale>.yaml`; each sibling is embedded at the same
  scale (research questions 2/3/5, reviewer panels 1 SWE + 2/4/6).

## Commands

```bash
TK_SKILLS=~/.kiro/skills
TK_LOOM_ROOT=$TK_SKILLS/home/project-feature/loom
TK_TILING=$TK_SKILLS/home/tiling/scripts/run-ttm.sh
TK_EDITOR=$TK_SKILLS/home/editor/scripts/run-editor.sh
TK_LOOM=$TK_SKILLS/home/loomv2/scripts/loom.sh
eval "$($TK_TILING layout build)"
```

## Rules

1. This graph carries NO tasks of its own — only the three
   subgraph instances and their wiring. Stage behavior, latches,
   and gates live in the sibling skills; fix them there.
2. The graph variants (`loom/graph-{s,m,l}.yaml`) differ only in
   which scale variant of each sibling they embed; validate all
   three after any wiring change.
3. Skill-taught build/test verbs win over the static fallback
   matrix. Brazil and other AWS-internal build systems enter only
   via `--build-system <name>`, never manifest detection.

## Workflow

### Step 1: Ingest

1. `$TK_TILING activity set "project-feature(<workspace>): Ingest"`
2. ```bash
   TK_WD=$($TK_LOOM runtime init \
       --loom-root "$TK_LOOM_ROOT" \
       --graph "graph-<scale>.yaml" \
       --set "description=<description>" \
       --set "workspace=<absolute-workspace-path>" \
       --set "build_system_override=<name-or-empty>" \
       --set "test_system_override=<name-or-empty>" \
       --set "cache_mode=<mode-or-read-write>")
   ```
3. `$TK_TILING activity set "project-feature(<workspace>): Ingest done"`

If `runtime init` fails: NEEDS_CONTEXT.

### Step 2: Drive the loop

1. `$TK_TILING activity set "project-feature(<workspace>): Drive"`
2. Loop until done:
   - `$TK_LOOM runtime next "$TK_WD"`; non-zero exit → BLOCKED.
   - `done: true` → break.
   - Dispatch ready `kind: agent` entries in parallel via the
     `subagent` tool (`role: trusted`; forward any `model` hint);
     drive `kind: human` entries sequentially; after each,
     `$TK_LOOM runtime complete "$TK_WD" <task-address>`.
   - Tasks surface under sibling namespaces
     (`overview/detect-domains`, `design/design-gate`,
     `engineering/impl-round`); dispatch and complete them by that
     canonical address. Unused fan-out slots never surface
     (`when:` + `skip_output`).
   - After every wave: verify each dispatched agent's declared
     `output_path` exists on disk before completing; re-dispatch
     silent failures.
3. `$TK_TILING activity set "project-feature(<workspace>): Done"`

## Helper: Drive human gate

Human tasks are conversational: read `message_path`, follow it,
write schema-valid YAML to `output_path`, then complete. Gate
behavior (always-stop vs auto-proceed) is defined by each sibling
skill's SKILL.md:

- `design/design-gate`: ALWAYS STOP (see project-design).
- `engineering/branch-gate`: auto-proceed when clean (see
  project-engineering).
- `engineering/final-gate`: ALWAYS STOP (see project-engineering).

## Completion

| Status               | Criteria                                                             |
| -------------------- | -------------------------------------------------------------------- |
| `DONE`               | `engineering/final-gate.decision == 'accept'`.                       |
| `DONE_WITH_CONCERNS` | Any sibling review latch exhausted its fuel.                         |
| `BLOCKED`            | Any gate aborted/abandoned, or `runtime next` exit non-zero.         |
| `NEEDS_CONTEXT`      | Missing description/workspace, or workspace path does not exist.     |
