---
name: loom-curator
type: workflow
description: Curator. Ingests a URL or file into an Obsidian vault. Use when the user says "loom-curator", "loom-ingest", or provides a URL or local file path to add to ~/Obsidian/MahVault. Do NOT use for the legacy curator skill — that has its own SKILL.md. Do NOT use for personal zettels — those are human-only.
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
   CURATOR=$SKILLS/home/loom-curator/scripts/curator.sh
   YQ=$SKILLS/home/loom-curator/scripts/yq.sh
   TILING=$SKILLS/home/tiling/scripts/run-ttm.sh
   EDITOR=$SKILLS/home/editor/scripts/run-editor.sh
   ANALYTICS=$SKILLS/home/skill-analytics/scripts/add-invocation.sh
   ```
2. Set tiling activity, record invocation, build layout:
   ```bash
   TARGET=$(basename "<url-or-path>")
   $TILING activity set "loom-curator($TARGET): Ingest"
   $ANALYTICS loom-curator user:$(whoami)
   eval "$($TILING layout build)"
   ```
3. Ingest:
   ```bash
   WD=$($CURATOR ingest "<url-or-path>" | $YQ .workdir)
   ```
4. If `ingest` fails: NEEDS_CONTEXT.

### Step 2: Drive the loop

```bash
$TILING activity set "loom-curator($TARGET): Drive the loop"

while true; do
    $CURATOR next "$WD" > /tmp/next.yaml 2> /tmp/next.err \
        || { echo "BLOCKED: next failed"; cat /tmp/next.err; exit 1; }

    [ "$($YQ .done < /tmp/next.yaml)" = "true" ] && break
    if [ "$($YQ '.stuck // false' < /tmp/next.yaml)" = "true" ]; then
        echo "BLOCKED: plan stuck"; cat /tmp/next.yaml; exit 1
    fi

    # Per-id dispatch — see helpers below.
    for id in $($YQ '.ready[].id' < /tmp/next.yaml); do
        # ... dispatch agent / drive gate ...
        $CURATOR complete "$WD" "$id"
    done
done
```

### Step 3: Report outcome

```bash
$TILING activity set "loom-curator($TARGET): Report outcome"
$CURATOR status "$WD"
$TILING activity set "loom-curator($TARGET): Done"
```

## Helper: Dispatch agent task

`$CURATOR next` yields ready agent tasks with their `prompt_path`
already rendered. For each id, dispatch via the `subagent` MCP tool
with `role:` picked by id prefix:

| Task id          | role               |
|------------------|--------------------|
| `classify`       | `curator-extractor` |
| `extract-<kind>` | `curator-extractor` |
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

`gate` is a human kind task. Loom yields it without a prompt; the
orchestrator drives review:

```bash
$TILING activity set "loom-curator($TARGET): Human gate"
eval "$($TILING layout build)"

$EDITOR reset
$CURATOR gate-list "$WD" \
    | while IFS=$'\t' read -r kind a b; do
        case "$kind" in
            report)   $EDITOR show file "$a" ;;
            *-modify) $EDITOR show diff "$a" "$b" ;;
            # *-create entries surface in the report; not opened individually
        esac
    done
```

STOP and wait for the user. They may edit or `rm` files in
`<workdir>/global/vault-replica/`; replica state at apply time is the
authoritative decision.

When the user signals proceed/abort, write the gate's output and
complete:

```bash
echo "proceed: true"  > "$WD/tasks/56-gate/output.yaml"  # or false
$CURATOR complete "$WD" gate
```

`strip-dead-links` and `apply-replica` are gated on
`proceed == true` via loom's `when:` predicates — `false` skips both.

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
