---
name: curator
type: workflow
description: Curates an Obsidian vault as an LLM wiki. Use when the user says "ingest", "curate", or provides a URL or source path to add to ~/Obsidian/MahVault. Do NOT use for writing personal zettels — those are human-only.
---

# Curator

Drives sub-agents to ingest a source into an Obsidian vault. Every mechanical
step (workdir lifecycle, plan/state, tool tasks, prompt rendering, page
rendering) happens inside `curator.sh`. The orchestrator's job is to dispatch
sub-agents on the batches `curator next` yields and to drive the human gate.

## Parameters

- **url-or-path** (required): http(s) URL or local file path.

## Workflow

### Step 1: Ingest

1. Set tiling activity:
   ```bash
   SKILLS=~/.kiro/skills
   TARGET=$(basename "<url-or-path>")
   $SKILLS/home/tiling/scripts/run-ttm.sh activity set "curator($TARGET): Ingest"
   ```
2. Record invocation:
   ```bash
   $SKILLS/home/skill-analytics/scripts/add-invocation.sh \
       curator user:$(whoami)
   ```
3. Build layout:
   ```bash
   eval "$($SKILLS/home/tiling/scripts/run-ttm.sh layout build)"
   ```
4. Run ingest and capture the workdir:
   ```bash
   WD=$($SKILLS/home/curator/scripts/curator.sh ingest "<url-or-path>" \
           | $SKILLS/home/curator/scripts/yq.sh .workdir)
   ```
5. If `ingest` fails: NEEDS_CONTEXT.

On completion: proceed to Step 2.

### Step 2: Drive the loop

1. Set tiling activity:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh activity set "curator($TARGET): Drive the loop"
   ```
2. Loop: call `curator next` and break when it reports done.
   Save each batch to a file because subsequent calls don't
   re-yield until each task in the current batch is marked
   complete:
   ```bash
   while true; do
       if ! $SKILLS/home/curator/scripts/curator.sh next "$WD" \
                > /tmp/next.yaml 2> /tmp/next.err; then
           echo "BLOCKED: curator next failed"
           cat /tmp/next.err
           exit 1
       fi
       done=$($SKILLS/home/curator/scripts/yq.sh .done < /tmp/next.yaml)
       [ "$done" = "true" ] && break
       # See "Helper: Dispatch agent task" / "Helper: Drive
       # human gate" below for the per-kind protocol.
       for id in $($SKILLS/home/curator/scripts/yq.sh '.ready[].id' < /tmp/next.yaml); do
           if ! $SKILLS/home/curator/scripts/curator.sh complete "$WD" "$id"; then
               echo "BLOCKED: curator complete $id failed"
               exit 1
           fi
       done
   done
   ```
3. If `next` or `complete` errors: BLOCKED with the failed
   task id (printed to stderr by the script).

On loop exit: proceed to Step 3.

### Step 3: Report outcome

1. Set tiling activity:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh activity set "curator($TARGET): Report outcome"
   ```
2. Run the status oracle and report its verdict:
   ```bash
   $SKILLS/home/curator/scripts/curator.sh status "$WD"
   ```
   Aggregates judge verdicts across the run.
3. Set tiling activity to Done:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh activity set "curator($TARGET): Done"
   ```

## Helper: Dispatch agent task

Each agent task is a single attempt. `next` has already rendered the extractor
and judge prompts; the action spec carries their paths:

```yaml
- id: extract-keywords
  kind: agent
  task_workdir:          .../tasks/05-extract-keywords
  output_path:           .../output.yaml
  extractor_prompt_path: .../extractor-prompt.md
  judge_prompt_path:     .../judge-prompt.md
  verdict_path:          .../verdict.yaml
```

For each agent task in the ready batch:

1. Dispatch the extractor via the `subagent` MCP tool. Pass the
   prompt as the stage's `prompt_template` (instructing the
   sub-agent to read the prompt file with `fs_read` and follow
   it). Use `role: <task.agent>` (typically `curator-extractor`,
   `curator-composer`, or `curator-judge`).
2. After the extractor stage completes, dispatch the judge in a
   stage that depends on it. The judge's prompt tells the agent
   to write its verdict to `verdict_path`.
3. Multiple extract-`<kind>` tasks in one batch are independent
   — fan out the extractor+judge pairs in parallel using the
   `subagent` tool's `stages` array with `depends_on` between
   each kind's extractor and its judge.

The synthesis agent task is structurally identical but its prompt instructs
the agent to:

- Read upstream extractor outputs + verdicts directly (paths
  passed in the prompt's `extraction_paths` / `verdict_paths`
  vars).
- Build a structured JSON file per hub at `/tmp/<slug>.json`.
- Render each hub against the wiki template, piping the
  rendered markdown into `<replica_root>/21 WIKI/<Title>.md`.
- The renderer uses StrictUndefined and refuses to render if
  any required field is missing — this is the layout-
  enforcement mechanism.
- Record the written paths back into the synthesis output.

Verdicts are read by the orchestrator at Step 3 to decide DONE vs
DONE_WITH_CONCERNS. The task always completes regardless of verdict; REJECT
findings surface in the gate's report.

## Helper: Drive human gate

The `gate` task drives human review of the replica directory at
`<workdir>/vault-replica/`. By the time gate is ready, the
replica contains:

- Atomic pages (one file per artifact-mode item) at the
  vault-relative paths listed in `manifest.yaml`. Filenames are
  the natural item names (e.g. `Claude's C Compiler.md`) so
  Obsidian wikilinks resolve directly.
- Synthesis hub pages under `21 WIKI/` written by the
  synthesis agent and not tracked in the manifest.
- `_REPORT.md` at the replica root — gate operator's
  TL;DR overview.
- `manifest.yaml` — engine state, skipped by apply.

Gate driver protocol:

1. Set tiling activity and build the layout:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh activity set "curator($TARGET): Human gate"
   eval "$($SKILLS/home/tiling/scripts/run-ttm.sh layout build)"
   ```
2. Drive the editor by consuming `curator.sh gate-list <wd>`, which
   emits one tab-separated record per file in protocol order
   (report → manifest entries → synthesis pages). Only open the
   report and entries that overwrite existing vault pages — new
   files are surfaced in the report's "Modifying existing vault
   pages" section, not via the editor:

   ```bash
   EDITOR=$SKILLS/home/editor/scripts/run-editor.sh
   $EDITOR reset
   $SKILLS/home/curator/scripts/curator.sh gate-list "$WD" \
       | while IFS=$'\t' read -r kind a b; do
           case "$kind" in
               report)   $EDITOR show file "$a" ;;
               *-modify) $EDITOR show diff "$a" "$b" ;;
               # *-create entries: not opened in editor — see report
           esac
       done
   ```

   - `kind` ∈ `report`, `manifest-create`, `manifest-modify`,
     `synthesis-create`, `synthesis-modify`.
   - Two-field records (`report`, `*-create`) carry the file path
     in `a`. Three-field records (`*-modify`) carry the original
     vault path in `a` and the replica path in `b`.
   - `*-create` records are emitted by `gate-list` but the gate
     driver intentionally skips them — new pages are reviewed via
     the report's listing rather than opened individually. The
     report enumerates every modification so the user knows which
     existing vault files would be overwritten before approving.
   - The engine warns to stderr and skips manifest entries whose
     replica file is missing on disk; the orchestrator MUST NOT
     synthesize its own iteration over `manifest.yaml` (vault
     paths contain spaces and apostrophes — naive shell loops
     break).
3. STOP and wait for the user to review. The user may edit any
   replica file in place or `rm` files they want to reject —
   the replica state at apply time is the authoritative
   decision.
4. When the user signals proceed/abort, write the gate's
   `output.yaml`:

   ```yaml
   proceed: true
   ```

   Or `proceed: false` to abort the run before applying.

The downstream `apply-replica` task walks the replica + manifest: manifest
entries become vault writes, replica files outside the manifest under
`21 WIKI/` are validated + applied as synthesis pages, deleted manifest
entries become `skipped: user_deleted`. No separate decisions YAML is needed.

## Rules

- Use the `subagent` MCP tool only for kind=agent tasks —
  `tool` tasks run inside `next`.
- The `gate` task MUST be human-driven. Auto-approving silently
  removes the user's veto.
- Source binary files and `*.assets/` folders are immutable.
- Atomic page filenames use natural item names (no kebab-
  casing). Obsidian wikilinks like `[[Item Name]]` resolve
  against these directly.
- Synthesis pages go through `render.sh + templates/vault/wiki.j2`
  rather than direct markdown authoring. The template enforces
  the layout; the agent fills structured fields.

## Completion

| Status               | Criteria                                         |
|----------------------|--------------------------------------------------|
| `DONE`               | `next` returned done; all verdicts ACCEPT/REVIEW |
| `DONE_WITH_CONCERNS` | `next` returned done; ≥1 verdict REJECT          |
| `BLOCKED`            | `next` / `complete` errored                      |
| `NEEDS_CONTEXT`      | `ingest` rejected the input                      |
