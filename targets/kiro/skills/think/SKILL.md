---
name: think
type: workflow
description: Best-of-N thinking workflow for hard questions. Decomposes the question into a session-aware weighted 1-10 rubric, fans out to 3 sub-agents to answer independently, runs 3 pair-wise comparisons that score each side 1-5 per dimension with cited evidence, and aggregates results into a weighted ranking with informational confidence signals (confidence_gap, intransitivity_cycles, rejected_judgments) and links to the full reports. Use when the user says "think", "think hard", "deep think", "best of N", or otherwise asks for a deeply considered answer to a complex question. Do NOT use for routine lookups, single-file edits, or quick factual questions.
---

# Think

Drive a best-of-N reasoning workflow for a complex question. Builds a
session-aware 1-10 rubric, fans out to three independent answer agents, scores
the answers pair-wise (1-5 per dimension with cited evidence) against the
rubric, and emits a weighted ranking with informational confidence signals and
links back to the full reports. Use when the user wants depth and is willing to
trade latency and tokens for it.

## Dependencies

- `loom` — DAG execution library
- `tiling` — pane layout and activity tracking
- `skill-analytics` — activation logging
- `template` — renders the user-facing report from rank output

## Parameters

- **question** (required): the complex question to answer.
  Passed as a single quoted argument to `ingest --question`.
- **context** (optional): a short summary of the active
  session (recent files, prior turns, error logs, tickets)
  used to bias rubric weights toward what matters for THIS
  question. The orchestrator should construct this from the
  current session state, not ask the user for it.

## Workflow

### Step 1: Ingest

1. Bind aliases and parameters, set tiling activity, record
   invocation, and build layout. Replace `user:think_hard`
   with the concrete trigger that activated this skill:
   ```bash
   SKILLS=~/.kiro/skills
   THINK=$SKILLS/home/think/scripts/think.sh
   TILING=$SKILLS/home/tiling/scripts/run-ttm.sh
   ANALYTICS=$SKILLS/home/skill-analytics/scripts/add-invocation.sh
   TH_QUESTION="<the question parameter>"
   TH_CONTEXT="<the context parameter, or empty>"
   $TILING activity set "think($TH_QUESTION): Ingest"
   $ANALYTICS think user:think_hard
   eval "$($TILING layout build)"
   ```
2. Ingest. Add `--context "$TH_CONTEXT"` only when the
   orchestrator has session context to pass:
   ```bash
   TH_WD=$($THINK ingest --question "$TH_QUESTION")
   ```
3. If the command exits non-zero or `TH_WD` is empty, stop with
   NEEDS_CONTEXT.

### Step 2: Drive the loop

1. Set tiling activity:
   ```bash
   $TILING activity set "think($TH_QUESTION): Drive the loop"
   ```
2. Loop until done:
   - Run `$THINK next "$TH_WD"`. Parse the YAML response.
   - If `done: true` → break.
   - If `stuck: true` → BLOCKED.
   - Otherwise, for each `ready[].id` dispatch the sub-agent
     (see helper) and then call `$THINK complete "$TH_WD" <id>`.
   - Dispatch independent ids in one batch in parallel.
3. Render the user-facing report and surface it inline:
   ```bash
   $THINK report "$TH_WD"
   $TILING activity set "think($TH_QUESTION): Done"
   ```
   The `report` command writes `$TH_WD/report.md` and prints
   the path. Read the file and present its contents in the
   chat session — do not open an external editor.

## Helper: Dispatch agent task

`$THINK next` yields ready agent tasks with their `prompt_path` already
rendered. For each id, dispatch via the `subagent` MCP tool with `role: trusted`
(grants file-read/write access).

The sub-agent's `prompt_template` should instruct it to `fs_read` the
`prompt_path` and follow it. The agent writes its output to the `output_path`
(also in the `next` response). After the dispatch returns, call `$THINK complete
"$TH_WD" "<id>"`.

Dispatch independent ids in parallel via the `subagent` `stages` array with no
`depends_on`.

## Rules

1. The orchestrator MUST dispatch agent tasks via `subagent`,
   because each answer agent must run in an isolated context
   so that inlining cannot defeat the independence the DAG
   was built to enforce.
2. The three `answer-*` agents MUST NOT see the rubric or each
   other's drafts, because the DAG enforces independence by
   keeping `answer-1/2/3` as siblings of `rubric` with no
   dependency edge. Adding a convenience edge would let answer
   agents tailor their responses to the rubric weights.
3. `rank` is a deterministic tool task. Do not replace it with
   an agent — the determinism is what makes the pair-wise
   judging trustworthy.
4. A failed task aborts the entire run. Loom's `next()`
   raises `RunAborted`; the orchestrator emits a run-level
   error. If `rubric` or any answer fails, stop and report
   BLOCKED rather than re-running in a loop.

## Schemas

Each task in the DAG has a versioned output schema:

- [`rubric`](schemas/rubric.yaml) — weighted 1-10 dimensions
  with rationale and what-better/what-worse anchors
- [`answer-{1,2,3}`](schemas/answer.yaml) — headline, body,
  key_claims with evidence, assumptions
- [`compare-*`](schemas/compare.yaml) — per-dimension a_score
  and b_score (1-5) with required evidence_a / evidence_b and a winner
  field used only for cycle detection
- [`rank`](schemas/rank.yaml) — weighted aggregation plus the
  informational confidence_gap, intransitivity_cycles, and
  rejected_judgments signals

## Completion

| Status               | Criteria                                                                  |
|----------------------|---------------------------------------------------------------------------|
| `DONE`               | `rank` succeeded, `report` rendered, path shown to the user               |
| `DONE_WITH_CONCERNS` | `rank` succeeded; intransitivity_cycles>0 or rejected_judgments non-empty |
| `BLOCKED`            | `next`/`complete` errored, or `rubric`/`compare-*`/`rank` failed          |
| `NEEDS_CONTEXT`      | `--question` was not provided or was empty                                |

The informational signals (`confidence_gap`, `intransitivity_cycles`,
`rejected_judgments`) are surfaced in the report and never block
promotion. There are no human gates: the ranking is always emitted.

Loom workdirs live under `/tmp/think/<slug>/`. Re-running `ingest` for the same
question wipes the workdir; previous runs are not auto-resumed. The `report.md`
inside the workdir is the user-facing artifact — it links back to the three
answer reports and the rubric so the user can audit the ranking.
