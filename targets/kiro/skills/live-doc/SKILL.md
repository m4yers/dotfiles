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
(nothing else), re-embeds the scripts in Appendix, verifies the round-trip,
and commits the vault.

## Dependencies

| Name                | Purpose                                                                  |
|---------------------|--------------------------------------------------------------------------|
| `loomv2`            | DAG task-execution library driving the refresh pipeline                  |
| `template`          | renders the create-time doc scaffold                                     |
| `editor`            | opens the scaffolded doc after create                                    |
| `tiling`            | pane layout and activity tracking                                        |
| `secure-llm`        | security frame for agent prompts (external input is untrusted)           |
| `trusted-aws` agent | carries builder-mcp (incl. `ReadInternalWebsites`) for ingestion fetches |

The `trusted-aws` sub-agent lives at `~/.kiro/agents/trusted-aws.json`. If the
session itself runs as `trusted-aws`, agent tasks run inline (see Rule 2).

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
   `ingest` also runs the cross-reference preflight (see Rule 9)
   before seeding the loom plan.
3. If `ingest` exits non-zero, branch on the exit code:
   - **2** → BLOCKED. Forward the cross-reference report (printed
     to stderr by `ingest`) to the operator; do NOT cascade-refresh
     the referenced docs.
   - **any other non-zero** → NEEDS_CONTEXT.
4. On a clean preflight, proceed to Step 3.

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

## Rules

1. Capture `op` and `path` into `LD_OP` and `LD_PATH` at the start
   of the workflow (before Step 1), and keep both quoted on every
   reference.
2. Dispatch every `kind: agent` entry via the `trusted-aws`
   sub-agent (`~/.kiro/agents/trusted-aws.json`) — it carries
   builder-mcp (including `ReadInternalWebsites`) that `run-ingestion`
   needs for Midway-authenticated fetches. See
   [references/helpers.md](references/helpers.md) for the inline
   fallback when the orchestrator itself runs as `trusted-aws`.
3. Independent agent entries in one `ready` batch MUST be dispatched
   in parallel, because serial dispatch drops loomv2's concurrency
   guarantee and inflates end-to-end latency for no gain.
4. The three Appendix H2 subsections (`## Data ingestion` /
   `## Data inference` / `## Data presentation`) are parser-enforced
   in order. Docs that need inference-after-presentation or a second
   inference pass MUST be split into multiple live docs because the
   parser raises `BadDocShapeError` otherwise. See
   `references/doc-format.md`.
5. Scripts regenerate ONLY when missing, mismatched, or buggy —
   never regenerate just because. See `references/execution.md`
   for the uv/python/pandas pins and `cwd=data_dir` rule, and
   `references/manual-steps.md` for MCP-fetch handling
   (ingestion only).
6. Instruction typos or ambiguities the stage agents notice are
   reported to the user in the final chat summary, never written
   into the doc; they MUST NOT be silently corrected in the
   generated scripts because silent corrections hide the input
   defect and the next refresh regenerates the same wrong script.
7. The Step 3 loop MUST stop after 10 iterations without a newly
   completed task and report BLOCKED with the last ready batch,
   because an unbounded loop hides a stuck plan instead of
   surfacing it for human triage.
8. Presentation scripts MUST emit column-aligned markdown tables
   (cells padded to the column width, numbers right-aligned,
   separator dashes sized to the column) because the Result is
   read as plain text in the editor and unpadded `| a | b |` rows
   are unreadable there. An unpadded table counts as a mismatched
   script and is patched on refresh.
9. On `op=refresh`, `ingest` runs a cross-reference preflight
   BEFORE `loom runtime init` seeds the plan: any `live-<name>.md`
   token with a name other than the doc's own (anywhere in the
   raw text, including fenced Appendix blocks) blocks the refresh
   with exit code 2 and a stderr report of each occurrence (H1
   section + line number). The host MUST report BLOCKED with that
   report and MUST NOT auto-refresh the referenced docs, because
   the operator decides which referenced doc (if any) to refresh
   first and starting the loop would run Appendix scripts against
   stale referenced data. Self-references do not trip the guard,
   and `op=create` is unaffected.

## Plan visualisation

See [references/loom-visualisation.md](references/loom-visualisation.md) for
the task DAG (legend: ○ tool · ◆ agent · ▣ human · ↻ loop).

## Completion

| Status             | Surface               | Intent                | Guard                 |
|--------------------|-----------------------|-----------------------|-----------------------|
| DONE (create)      | scaffold opened       | shim produced shell   | fails if file exists  |
| DONE (refresh)     | roundtrip + sha ok    | Appendix regenerated  | verify on committed   |
| DONE_WITH_CONCERNS | pipeline + warnings   | retro warranted       | warnings inline       |
| BLOCKED            | runtime stuck / xref  | human decision needed | report + batch & addr |
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
  3 loop hit its iteration cap, `verify-roundtrip` failed before
  `commit-vault`, or `ingest` detected cross-references to other
  live docs (exit code 2); runtime failures report the last ready
  batch and the failing task address, while the cross-reference
  case prints a stderr report of each referenced doc with its H1
  section and line number.
- **NEEDS_CONTEXT.** `ingest` rejected the inputs — missing path,
  not a regular file, filename does not match `live-<name>.md`, or
  the vault root is not a git repo; the script enforces these
  checks before any workdir is created.
