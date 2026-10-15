---
name: live-doc
type: workflow
description: Creates and refreshes live docs — markdown docs with a three-stage Instructions block (## Data ingestion / ## Data inference / ## Data presentation), a Result section, and an Appendix of uv scripts re-executed on demand. Use when user says "create live doc", "refresh live doc", "refresh this live doc", "new live doc", or edits a live doc's Instructions. Do NOT use for ordinary wiki pages or non-executable docs.
---

# Live Doc

Create and refresh live docs — vault markdown files with four sections (a
free-form intro, `# Instructions` in three fixed stages, `# Result`, and
`# Appendix` of uv scripts). Create scaffolds a new doc and opens it in the
editor; refresh is a 10-task loom pipeline that re-executes each Appendix
script, writes the refresh timestamp and presentation outputs into Result
(nothing else), re-embeds the scripts in Appendix,
verifies the round-trip, and commits the vault.

## Dependencies

| Name                | Purpose                                                 |
|---------------------|---------------------------------------------------------|
| `loomv2`            | DAG task-execution library driving the refresh pipeline |
| `template`          | renders the create-time doc scaffold                    |
| `editor`            | opens the scaffolded doc after create                   |
| `tiling`            | pane layout and activity tracking                       |
| `secure-llm`        | security frame for agent prompts (external input is untrusted) |
| `trusted-aws` agent | carries builder-mcp (incl. `ReadInternalWebsites`) for ingestion fetches |

The `trusted-aws` sub-agent lives at `~/.kiro/agents/trusted-aws.json`.
If the session itself runs as `trusted-aws`, agent tasks run inline
(see Rule 3).

## Parameters

- **op** (required): `create` or `refresh`
- **path** (required): absolute path to the live doc file
  (`<vault>/work/live/live-<name>.md`); `create` requires the file
  NOT to exist, `refresh` requires it to exist and the vault root to
  be a git repo

## Aliases

```bash
LD_SKILLS=~/.kiro/skills
LIVEDOC=$LD_SKILLS/home/live-doc/scripts/live-doc.sh
LOOM=$LD_SKILLS/home/loomv2/scripts/loom.sh
TILING=$LD_SKILLS/home/tiling/scripts/run-ttm.sh
EDITOR=$LD_SKILLS/home/editor/scripts/run-editor.sh
```

Caller state keeps the `LD_` prefix: `LD_OP`, `LD_PATH`, `LD_WD`.

## Create vs refresh paths

- **create** (`op=create`): one-shot. Renders the scaffold at
  `$LD_PATH` and opens it in the editor. No loom plan, no scripts,
  no first refresh; the Appendix is populated on the first explicit
  refresh.
- **refresh** (`op=refresh`): the 10-task loom pipeline. Step 2
  ingests the existing doc and seeds the loom plan; Step 3 drives
  it to completion.

See [references/doc-format.md](references/doc-format.md) for the live doc's
section layout and the round-trip contract.

## Workflow

### Step 1: Create (op=create)

For `op=refresh`, skip this step and proceed to Step 2.

1. Set tiling activity:
   ```bash
   $TILING activity set "live-doc(create:<name>): Scaffold"
   ```
2. Run create:
   ```bash
   $LIVEDOC create --path "$LD_PATH"
   ```
3. Set tiling activity to Done:
   ```bash
   $TILING activity set "live-doc(create:<name>): Done"
   ```

Workflow finishes after Step 1 when `op=create`.

### Step 2: Ingest (op=refresh)

1. Set tiling activity and build layout:
   ```bash
   $TILING activity set "live-doc(refresh:<name>): Ingest"
   eval "$($TILING layout build)"
   ```
2. Ingest:
   ```bash
   LD_WD=$($LIVEDOC ingest --path "$LD_PATH")
   ```
3. If `ingest` fails: NEEDS_CONTEXT.
4. On success, proceed to Step 3.

### Step 3: Drive the loop (op=refresh)

1. Set tiling activity:
   ```bash
   $TILING activity set "live-doc(refresh:<name>): Drive the loop"
   ```
2. Loop until done. For return-value shape and exit-code semantics,
   see `~/.kiro/skills/home/loomv2/schemas/next.yaml` and
   `$LOOM runtime next --help`.
   - Run `$LOOM runtime next "$LD_WD"`.
   - If exits non-zero → BLOCKED.
   - If `done: true` → break.
   - Otherwise, process the `ready[]` batch per
     [references/helpers.md](references/helpers.md) (dispatch all
     `kind: agent` entries in parallel, then drive each
     `kind: human` entry sequentially).
   - After each entry finishes, call
     `$LOOM runtime complete "$LD_WD" <task-address>`.
3. Set tiling activity to Done:
   ```bash
   $TILING activity set "live-doc(refresh:<name>): Done"
   ```

## Plan visualisation

See [references/loom-visualisation.md](references/loom-visualisation.md) for
the task DAG (legend: ○ tool · ◆ agent · ▣ human · ↻ loop).

## Rules

1. Capture `op` and `path` into `LD_OP` and `LD_PATH` at the start
   of the workflow (before Step 1), and keep both quoted on every
   reference.
2. For `op=refresh`, Step 2's `ingest` call seeds the loom entry
   task with `name` (derived from the filename) and `vault_path`
   and prints the workdir; Step 3 drives the pipeline to completion.
3. Dispatch every `kind: agent` entry via the `trusted-aws`
   sub-agent (`~/.kiro/agents/trusted-aws.json`) — it carries
   builder-mcp (including `ReadInternalWebsites`) that `run-ingestion`
   needs for Midway-authenticated fetches. Kiro never exposes the
   active agent profile to itself as a `subagent_*` tool, so when
   the orchestrator IS `trusted-aws` (no `subagent_trusted-aws`
   tool, but `builder-mcp::ReadInternalWebsites` is loadable), run
   the entry inline: `fs_read` its `prompt_path`, follow it with the
   session's own tools, then `complete` it. Do NOT substitute
   `subagent_trusted` (no builder-mcp) or report BLOCKED.
4. Independent agent entries in one `ready` batch MUST be dispatched
   in parallel, because serial dispatch drops loomv2's concurrency
   guarantee and inflates end-to-end latency for no gain.
5. The three Appendix H2 subsections (`## Data ingestion` /
   `## Data inference` / `## Data presentation`) are parser-enforced
   in order. Docs that need inference-after-presentation or a second
   inference pass MUST be split into multiple live docs because the
   parser raises `BadDocShapeError` otherwise. See
   `references/doc-format.md`.
6. Scripts regenerate ONLY when missing, mismatched, or buggy —
   never regenerate just because. See `references/execution.md`
   for the uv/python/pandas pins and `cwd=data_dir` rule, and
   `references/manual-steps.md` for MCP-fetch handling
   (ingestion only).
7. Instruction typos or ambiguities the stage agents notice are
   reported to the user in the final chat summary, never written
   into the doc; they MUST NOT be silently corrected in the
   generated scripts because silent corrections hide the input
   defect and the next refresh regenerates the same wrong script.
8. The Step 3 loop MUST stop after 10 iterations without a newly
   completed task and report BLOCKED with the last ready batch,
   because an unbounded loop hides a stuck plan instead of
   surfacing it for human triage.

## Completion

| Status             | Surface               | Intent                | Guard                 |
|--------------------|-----------------------|-----------------------|-----------------------|
| DONE (create)      | scaffold opened       | shim produced shell   | fails if file exists  |
| DONE (refresh)     | roundtrip + sha ok    | Appendix regenerated  | verify on committed   |
| DONE_WITH_CONCERNS | pipeline + warnings   | retro warranted       | warnings inline       |
| BLOCKED            | runtime errored/stuck | human decision needed | batch + addr reported |
| NEEDS_CONTEXT      | ingest rejected input | invocation malformed  | ingest preflight      |

Row glossary (long form of the compact columns above):

- **DONE (create).** Scaffold rendered at `$LD_PATH` and opened in
  the editor; create exits non-zero if the file already exists.
- **DONE (refresh).** `verify-roundtrip` passed and `publish-output`
  returned a non-empty `commit_sha`; the Appendix round-trip is
  byte-identical to the committed base so a weakened verifier fails
  the check.
- **DONE_WITH_CONCERNS.** Pipeline ran to completion but one or more
  stage agents emitted non-blocking warnings; warnings are reported
  inline per task so they cannot be silently dropped.
- **BLOCKED.** `$LOOM runtime next` or `complete` errored, the Step
  3 loop hit its iteration cap, or `verify-roundtrip` failed before
  `commit-vault`; the last ready batch and the failing task address
  are reported.
- **NEEDS_CONTEXT.** `ingest` rejected the inputs — missing path,
  not a regular file, filename does not match `live-<name>.md`, or
  the vault root is not a git repo; the script enforces these
  checks before any workdir is created.
