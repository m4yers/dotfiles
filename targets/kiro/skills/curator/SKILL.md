---
name: curator
type: workflow
description: Curator. Ingests a URL or file into an Obsidian vault. Use when the user says "curator", "curator-ingest", or provides a URL or local file path to add to ~/Obsidian/MahVault. Do NOT use for personal zettels — those are human-only.
---

# Loom-curator

Drives sub-agents to ingest a source into an Obsidian vault. The
orchestrator's job: drive `$CURATOR next/complete`, dispatch each
yielded agent task, and run the human gate. Loom handles plan,
rendering, validation, and skip logic.

## Parameters

- **url-or-path** (required): http(s) URL or local file path.

## Workflow

### Step 1: Ingest

1. Set up tooling aliases:
   ```bash
   SKILLS=~/.kiro/skills
   CURATOR=$SKILLS/home/curator/scripts/curator.sh
   YQ=$SKILLS/home/curator/scripts/yq.sh
   TILING=$SKILLS/home/tiling/scripts/run-ttm.sh
   EDITOR=$SKILLS/home/editor/scripts/run-editor.sh
   ANALYTICS=$SKILLS/home/skill-analytics/scripts/add-invocation.sh
   ```
2. Set tiling activity, record invocation, build layout:
   ```bash
   TARGET=$(basename "<url-or-path>")
   $TILING activity set "curator($TARGET): Ingest"
   $ANALYTICS curator user:$(whoami)
   eval "$($TILING layout build)"
   ```
3. Ingest:
   ```bash
   WD=$($CURATOR ingest "<url-or-path>")
   ```
4. If `ingest` fails: NEEDS_CONTEXT.

### Step 2: Drive the loop

```bash
$TILING activity set "curator($TARGET): Drive the loop"
```

Loop until done:

1. Run `$CURATOR next "$WD"`. Parse the YAML response.
2. If `done: true` → break.
3. If `stuck: true` → BLOCKED.
4. Otherwise, for each `ready[].id`:
   - If `id == gate` → drive the human gate (see helper).
   - Else → dispatch the agent (see helper).
   - Then `$CURATOR complete "$WD" <id>`.

Independent ids in one batch can be dispatched in parallel.

### Step 3: Report outcome

```bash
$TILING activity set "curator($TARGET): Report outcome"
$CURATOR status "$WD"
$TILING activity set "curator($TARGET): Done"
```

## Helper: Dispatch agent task

`$CURATOR next` yields ready agent tasks with their `prompt_path`
already rendered. For each id, dispatch via the `subagent` MCP tool
with `role:` picked by id prefix:

| Task id          | role               |
|------------------|--------------------|
| `classify`       | `curator-extractor` |
| `extract-<kind>` | `curator-extractor` |
| `merge-<kind>`   | `curator-extractor` |
| `judge-<kind>`   | `curator-judge`     |
| `synthesis`      | `curator-composer`  |
| `judge-synthesis`| `curator-judge`     |

The sub-agent's `prompt_template` should instruct it to `fs_read` the
`prompt_path` and follow it. The agent writes its own output (the
prompt instructs how). After dispatch returns, call
`$CURATOR complete "$WD" "<id>"`.

Dispatch independent ids in parallel via the `subagent` `stages`
array with no `depends_on`.

## Helper: Drive human gate

`gate` is a human kind task. Loom renders the report template as
the gate's prompt (using upstream report data as context).

1. Set tiling activity and ensure layout:
   ```bash
   $TILING activity set "curator($TARGET): Human gate"
   eval "$($TILING layout build)"
   ```
2. Open the gate's `prompt_path` in the editor — this is the
   rendered report:
   ```bash
   $EDITOR show file "<prompt_path>"
   ```
3. STOP and wait for the user. They may edit or `rm` files in
   `<workdir>/global/vault-replica/`; replica state at apply time
   is the authoritative decision.
4. When the user signals proceed/abort:
   ```bash
   echo "proceed: true" > "$WD/tasks/56-gate/output.yaml"  # or false
   $CURATOR complete "$WD" gate
   ```

`strip-dead-links` and `apply-replica` are gated on `proceed == true`
via loom's `when:` predicates — `false` skips both.

## Rules

1. Dispatch kind=agent tasks via `subagent`. Tool/human tasks the
   orchestrator never sees in `ready`; loom runs tools inline and
   yields humans for the gate driver.
2. The gate MUST be human-driven. Auto-approving removes the user's
   veto.
3. Source binary files and `*.assets/` folders are immutable.
4. Atomic page filenames use natural item names (no kebab-casing) so
   `[[Item Name]]` wikilinks resolve directly.

## Completion

| Status               | Criteria                                              |
|----------------------|-------------------------------------------------------|
| `DONE`               | `next` reported done; no judge verdict was REJECT     |
| `DONE_WITH_CONCERNS` | `next` reported done; ≥1 verdict was REJECT          |
| `BLOCKED`            | `next` / `complete` errored, or stuck plan reported   |
| `NEEDS_CONTEXT`      | `ingest` rejected the input                           |
