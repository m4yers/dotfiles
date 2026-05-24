---
name: loom-curator
type: workflow
description: Curator on top of loom. Ingests a source (URL or file) into an Obsidian vault via LLM-driven extraction. Plan is derived at runtime from quintet.yaml and the templates/extractors/ directory layout, then executed by loom. Use when the user says "loom-curator", "loom-ingest", or provides a URL or local file path to add to ~/Obsidian/MahVault. Do NOT use for the legacy curator skill — that has its own SKILL.md. Do NOT use for personal zettels — those are human-only.
---

# Loom-curator

Drives sub-agents to ingest a source into an Obsidian vault. Identical
purpose to the legacy `curator` skill, but the entire execution plan is
declared statically up front (derived from `quintet.yaml` rules + the
`templates/extractors/` directory layout) and driven by `loom`. Every
agent task pairs with an independent judge agent task. The plan is
frozen at ingest time — no runtime extension or transitions.

## Parameters

- **url-or-path** (required): http(s) URL or local file path.

## Workflow

### Step 1: Ingest

1. Set tiling activity:
   ```bash
   SKILLS=~/.kiro/skills
   TARGET=$(basename "<url-or-path>")
   $SKILLS/home/tiling/scripts/run-ttm.sh activity set "loom-curator($TARGET): Ingest"
   ```
2. Record invocation:
   ```bash
   $SKILLS/home/skill-analytics/scripts/add-invocation.sh \
       loom-curator user:$(whoami)
   ```
3. Build layout:
   ```bash
   eval "$($SKILLS/home/tiling/scripts/run-ttm.sh layout build)"
   ```
4. Run ingest and capture the workdir:
   ```bash
   WD=$(~/.kiro/skills/home/loom-curator/scripts/curator.sh \
            ingest "<url-or-path>" \
        | ~/.kiro/skills/home/loom-curator/scripts/yq.sh .workdir)
   ```
5. If `ingest` fails (validation or fetch handler error): NEEDS_CONTEXT.

On completion: proceed to Step 2.

### Step 2: Drive the loop

1. Set tiling activity:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh activity set "loom-curator($TARGET): Drive the loop"
   ```
2. Loop: call `curator.sh next "$WD"` and break when it reports done.
   Each call returns either `{done: true}`, `{done: false, ready: [...]}`,
   or `{done: false, stuck: true, summary: ...}`. The engine runs all
   ready tool tasks inline and yields agent + human tasks for the
   orchestrator to dispatch.

   ```bash
   while true; do
       SH=~/.kiro/skills/home/loom-curator/scripts/curator.sh
       YQ=~/.kiro/skills/home/loom-curator/scripts/yq.sh

       if ! $SH next "$WD" > /tmp/next.yaml 2> /tmp/next.err; then
           echo "BLOCKED: curator next failed"
           cat /tmp/next.err
           exit 1
       fi
       done=$($YQ .done < /tmp/next.yaml)
       [ "$done" = "true" ] && break
       stuck=$($YQ '.stuck // false' < /tmp/next.yaml)
       if [ "$stuck" = "true" ]; then
           echo "BLOCKED: plan is stuck"
           cat /tmp/next.yaml
           exit 1
       fi
       # Dispatch each ready external task — see "Helper: Dispatch agent
       # task" / "Helper: Drive human gate" below.
       for id in $($YQ '.ready[].id' < /tmp/next.yaml); do
           # ... per-id dispatch (see helpers) ...
           # then mark done:
           $SH complete "$WD" "$id"
       done
   done
   ```

On loop exit: proceed to Step 3.

### Step 3: Report outcome

1. Set tiling activity:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh activity set "loom-curator($TARGET): Report outcome"
   ```
2. Run the status oracle and report its verdict:
   ```bash
   ~/.kiro/skills/home/loom-curator/scripts/curator.sh status "$WD"
   ```
   Aggregates judge verdicts across the run.
3. Set tiling activity to Done:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh activity set "loom-curator($TARGET): Done"
   ```

## Helper: Dispatch agent task

Each `next` response yields a list of `ready` agent and human tasks.
Loom has already rendered each task's prompt to `<task_workdir>/prompt.md`
before yielding. The task spec carries:

```yaml
- id: extract-keywords
  kind: agent
  task_workdir:    .../tasks/26-extract-keywords
  output_path:     .../tasks/26-extract-keywords/output.yaml
  prompt_path:     .../tasks/26-extract-keywords/prompt.md
```

For each agent task in the ready batch:

1. Pick the agent role from the task id:
   - `classify`, `judge-classify` → `curator-extractor` / `curator-judge`
   - `extract-<kind>` → `curator-extractor`
   - `judge-<kind>` → `curator-judge`
   - `synthesis` → `curator-composer`
   - `judge-synthesis` → `curator-judge`
2. Dispatch via the `subagent` MCP tool. Pass the rendered prompt path
   in the prompt_template (instructing the sub-agent to `fs_read` it
   and follow it). Use `role: <picked above>`.
3. The agent writes its output via `curator.sh builders init/add` calls
   (the prompt itself instructs the agent how). Output lands at
   `output_path`.
4. After dispatch returns, call `curator.sh complete "$WD" "<id>"` to
   validate the output against the task's `output_schema` and mark
   the task `done`. On schema failure, `complete` raises
   `OutputSchemaError` and the task is marked `failed`.

Multiple agent tasks in one batch are independent — fan out via the
`subagent` tool's `stages` array with no `depends_on` between them.

## Helper: Drive human gate

The `gate` task is a human kind. Loom yields it but does not render a
prompt (gate has no template). The orchestrator drives gate review.

1. Set tiling activity and ensure layout:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh activity set "loom-curator($TARGET): Human gate"
   eval "$($SKILLS/home/tiling/scripts/run-ttm.sh layout build)"
   ```
2. List gate review targets via `gate-list`:
   ```bash
   ~/.kiro/skills/home/loom-curator/scripts/curator.sh \
       gate-list "$WD"
   ```
   Emits TSV records (one per file): `report` | `manifest-create` |
   `manifest-modify` | `synthesis-create` | `synthesis-modify`. Use
   the editor skill to show diffs for `*-modify` records and content
   for `report`.
3. Drive the editor:
   ```bash
   EDITOR=$SKILLS/home/editor/scripts/run-editor.sh
   $EDITOR reset
   ~/.kiro/skills/home/loom-curator/scripts/curator.sh gate-list "$WD" \
       | while IFS=$'\t' read -r kind a b; do
           case "$kind" in
               report)   $EDITOR show file "$a" ;;
               *-modify) $EDITOR show diff "$a" "$b" ;;
               # *-create entries are surfaced in the report's
               # "Modifying existing vault pages" section, not opened
               # individually
           esac
       done
   ```
4. STOP and wait for the user to review. The user may edit any replica
   file in `<workdir>/global/vault-replica/` or `rm` files they want to
   reject — replica state at apply time is the authoritative decision.
5. When the user signals proceed/abort, write the gate's `output.yaml`:
   ```yaml
   # to apply the replica
   proceed: true
   # OR to abort
   proceed: false
   ```
   Save to `<task_workdir>/output.yaml`, then call:
   ```bash
   ~/.kiro/skills/home/loom-curator/scripts/curator.sh \
       complete "$WD" gate
   ```
6. The downstream `strip-dead-links` and `apply-replica` tasks are
   gated on `task."gate".proceed == true`. If the user set
   `proceed: false`, both are skipped via `when:` predicate and the
   plan finishes without writing to the vault.

## How the plan is shaped

Loom-curator's plan has 58 task slots regardless of source. The active
set depends on the quintet:

```
fetch (tool)
└── convert (tool)
    └── security_scan (tool)
        └── classify (agent)
            └── judge-classify (agent)
                ├── extract-summary (agent, always run)
                ├── extract-keywords (agent, always run)
                └── 20 conditional extract-<kind> tasks
                    └── each pairs with judge-<kind>
                        ├── (cascade: extractor skipped → judge auto-skipped)
                        └── (after all judges) build-replica (tool)
                            └── synthesis (agent)
                                └── judge-synthesis (agent)
                                    └── prune-replica (tool)
                                        └── report (tool)
                                            └── gate (human)
                                                ├── strip-dead-links (tool, when proceed)
                                                └── apply-replica (tool, when proceed)
```

The 20 conditional extractors fire based on `quintet.yaml`'s rule
table. For an `(article, blog, non_fiction, cs, professional)` source,
4 extractors run + summary + keywords = 6 agent extractor tasks (12
counting their judges). The remaining 17 extractor pairs auto-skip via
`when:` predicates and cascade-skip.

## Rules

1. Use the `subagent` MCP tool for kind=agent tasks. Tool tasks run
   inside `next` (engine subprocess); orchestrator does not see them.
2. The `gate` task MUST be human-driven. Auto-approving silently
   removes the user's veto.
3. Source binary files and `*.assets/` folders are immutable.
4. Atomic page filenames use natural item names (no kebab-casing).
   Obsidian wikilinks like `[[Item Name]]` resolve against these
   directly.
5. Synthesis pages go through `templates/vault/wiki.j2` rather than
   direct markdown authoring. The template enforces the layout; the
   agent fills structured fields.
6. Plan extension is NOT used — every task is declared at ingest
   time. If a future feature needs runtime task addition, use
   `loom.extend` explicitly from the orchestrator.

## Completion

| Status               | Criteria                                              |
|----------------------|-------------------------------------------------------|
| `DONE`               | `next` returned done; no judge verdict was REJECT     |
| `DONE_WITH_CONCERNS` | `next` returned done; ≥1 verdict was REJECT          |
| `BLOCKED`            | `next` / `complete` errored, or stuck plan reported   |
| `NEEDS_CONTEXT`      | `ingest` rejected the input (validation or fetch fail) |
