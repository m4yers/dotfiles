---
name: curator
type: workflow
description: Curates an Obsidian vault as an LLM wiki. Use when the user says "ingest", "curate", or provides a URL or source path to add to ~/Obsidian/MahVault. Do NOT use for writing personal zettels — those are human-only.
---

# Curator

Drives sub-agents to ingest a source into an Obsidian vault. Every
mechanical step (workdir lifecycle, plan/state, tool tasks, prompt
rendering) happens inside `curator.sh`. The orchestrator's job is to
dispatch sub-agents on the batches `curator next` yields.

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
           | yq '.workdir')
   ```
5. If `ingest` fails: NEEDS_CONTEXT.

### Step 2: Drive the loop

1. Set tiling activity:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh activity set "curator($TARGET): Drive the loop"
   ```
2. Loop: call `curator next` and break when it reports done:
   ```bash
   while true; do
       action=$($SKILLS/home/curator/scripts/curator.sh next "$WD")
       [ "$(echo "$action" | yq '.done')" = "true" ] && break
       # See "Helper: Dispatch agent task" / "Helper: Drive human gate"
       ...
   done
   ```
3. For each ready task in the batch, dispatch per kind. Tasks in one
   `.ready` batch have no inter-dependencies — dispatch all
   extractor/judge sub-agents in parallel, then complete them as
   their results land. See **Helper: Dispatch agent task** and
   **Helper: Drive human gate** below.
4. Mark each task done:
   ```bash
   for id in $(echo "$action" | yq '.ready[].id'); do
       $SKILLS/home/curator/scripts/curator.sh complete "$WD" "$id"
   done
   ```
5. If `next` or `complete` errors: BLOCKED with the failed task id.

`curator next` only yields `kind=agent` and `kind=human` tasks. Tool
tasks run inside `next` and never reach the orchestrator.

### Step 3: Report outcome

1. Set tiling activity to Done:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh activity set "curator($TARGET): Done"
   ```
2. Run the status oracle and report its verdict:
   ```bash
   $SKILLS/home/curator/scripts/curator.sh status "$WD"
   ```
   The script aggregates verdicts and emits
   `{status: DONE|DONE_WITH_CONCERNS|BLOCKED|NEEDS_CONTEXT, ...}`.

## Helper: Dispatch agent task

Each agent task is a single attempt. `next` has already rendered the
extractor and judge prompts; the action spec carries their paths:

```yaml
- id: extract-keywords
  kind: agent
  task_workdir: .../tasks/extract-keywords
  output_path:           .../output.yaml
  extractor_prompt_path: .../extractor-prompt.md
  judge_prompt_path:     .../judge-prompt.md
  verdict_path:          .../verdict.yaml
```

1. Read `extractor_prompt_path`; dispatch the extractor via the
   `subagent` tool with that prompt and `agent: <task.agent>`. The
   prompt tells the agent to write its result to `output_path`.
2. Read `judge_prompt_path`; dispatch the judge (`task.judge.agent`).
   The prompt tells the judge to write its verdict to `verdict_path`.
3. Optionally read `verdict_path` to decide DONE vs
   DONE_WITH_CONCERNS at the final report. The task always completes
   regardless of verdict.

## Helper: Drive human gate

The `gate` task: render the report from `metadata.report_from_task`'s
output, STOP and wait for user input, collect per-item decisions,
write a YAML decisions file, and emit its path as the task's
`output.yaml`:

```yaml
approved_path: <path to decisions YAML>
decisions:
  - id: kw-1
    action: approve
  - id: kw-2
    action: edit
    override_body_file: ...
```

## Rules

- Use the `subagent` MCP tool only for kind=agent tasks. Never
  dispatch tool tasks — engine runs them.
- The `gate` task MUST be human-driven. Auto-approving silently
  removes the user's veto.
- Source binary files and `*.assets/` folders are immutable.

## Completion

| Status               | Criteria                                         |
|----------------------|--------------------------------------------------|
| `DONE`               | `next` returned done; all verdicts ACCEPT/REVIEW |
| `DONE_WITH_CONCERNS` | `next` returned done; ≥1 verdict REJECT          |
| `BLOCKED`            | `next` / `complete` errored, or 3 task failures  |
| `NEEDS_CONTEXT`      | `ingest` rejected the input                      |
