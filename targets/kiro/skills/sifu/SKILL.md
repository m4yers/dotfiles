---
name: sifu
type: workflow
description: Creates, updates, or reviews Kiro skills via a loomv2 graph; loomv2 successor to dojo. New workflow skills default to loomv2, with a `flow` type for adaptable prose-step workflows. Use when user says "sifu", "sifu create", "sifu update", "sifu review". Do NOT use for legacy loom skill authoring unless asked — use dojo instead.
---

# Sifu

Creates, updates, or reviews a skill by driving one of three loomv2 graphs,
`loom/graph-<op>.yaml`. Each embeds the `loom-audit/` subgraph: deterministic
autochecks, then the rules of the conventions references the skill's topics
select, judged in waves of 16 shards of at most 3 rules each and ranked by rule
severity and finding confidence ([rule codes](references/rule-codes.md)). Skill
types are `interface`, `tool`, `workflow` (loomv2, the default for multi-step
work), `reference`, and `flow` (prose steps that adapt).

## Dependencies

- `loomv2` — graph execution.
- `tiling` — activity tracking.
- `editor` — file and diff display at human gates.
- `template`, `secure-llm` — prompt rendering and security frame.

## Parameters

- **operation** (required): `create`, `update`, or `review`.
- **name** (required): kebab-case skill name; for `update` and `review`
  an installed skill.

## Rules

1. A `ready` batch with exactly one agent task MAY run inline: read its
   `prompt_path`, follow it, write the output, then `runtime complete`.
   Two or more agent tasks MUST go to parallel sub-agents.
2. Human gates MUST be driven by the user; never auto-complete them.
3. A failed task aborts the run; report BLOCKED with `error_path`, do not
   re-run it.
4. Agent tasks change only what their prompt names; no extra helpers,
   abstractions, or defensive code, because uncommanded additions inflate
   the diff.
5. When a design loop runs out of fuel still on `revise`, materialization
   is skipped and the run is BLOCKED.
6. Agent tasks in one `ready` batch MUST be dispatched in parallel in chunks
   of at most 8 per `subagent` call, completing each chunk before the next,
   because larger fan-outs get throttled; a throttled stage never ran and is
   re-dispatched after a short backoff (30s, 60s, 120s), BLOCKED after 3.
7. `runtime complete` MUST run in a separate tool turn after the agent or
   gate has returned, never in the same batch as the dispatch, because
   `complete` reads whatever output exists and a batched call marks the
   task done on stale or missing data.

## Workflow

### Step 1: Ingest

1. Set caller state and tiling activity:
   ```bash
   SIFU_OP=<create|update|review>
   SIFU_NAME=<skill-name>
   SIFU_TILING=~/.kiro/skills/home/tiling/scripts/run-ttm.sh
   $SIFU_TILING activity set "sifu($SIFU_OP:$SIFU_NAME): Ingest"
   ```
2. Set up aliases and the tiling layout:
   ```bash
   SIFU_SKILLS=~/.kiro/skills
   SIFU_ROOT=$SIFU_SKILLS/home/sifu
   SIFU_LOOM=$SIFU_SKILLS/home/loomv2/scripts/loom.sh
   SIFU_EDITOR=$SIFU_SKILLS/home/editor/scripts/run-editor.sh
   eval "$($SIFU_TILING layout build)"
   ```
3. Init the run (auto workdir under `/tmp/sifu/`):
   ```bash
   SIFU_WD=$($SIFU_LOOM runtime init \
       --loom-root "$SIFU_ROOT/loom" --graph "graph-$SIFU_OP.yaml" \
       --set op="$SIFU_OP" --set name="$SIFU_NAME")
   ```
4. If `runtime init` fails: NEEDS_CONTEXT. On success: proceed to Step 2.

### Step 2: Drive the loop

1. Set tiling activity:
   ```bash
   $SIFU_TILING activity set "sifu($SIFU_OP:$SIFU_NAME): Drive the loop"
   ```
2. Advance the graph:
   ```bash
   $SIFU_LOOM runtime next "$SIFU_WD"
   ```
   Parse the YAML response (shape: loomv2 `schemas/next.yaml`). Non-zero
   exit → BLOCKED; stderr carries `{failed_task, error_path}`. `done: true`
   → go to sub-step 5.
3. Handle the `ready[]` batch (`kind: agent|human`; tool tasks already ran
   inside `runtime next`): dispatch every agent entry per the agent-dispatch
   helper, then drive every human entry per the human-gate helper.
4. After each entry has returned, complete it:
   ```bash
   $SIFU_LOOM runtime complete "$SIFU_WD" <task-address>
   ```
   Pass: it prints `ok`. Non-zero exit → BLOCKED with the task's
   `schema-error.yaml`. A sub-agent that returned without writing its output
   is re-dispatched once, then BLOCKED. Repeat from sub-step 2.
5. Set tiling activity to Done and report the status from
   `publish-output`'s output per `## Completion`:
   ```bash
   $SIFU_TILING activity set "sifu($SIFU_OP:$SIFU_NAME): Done"
   ```

## Helper: Dispatch agent task

`$SIFU_LOOM runtime next` yields ready agent entries with `prompt_path` and
`output_path`. Rules 1 and 6 decide inline versus sub-agents and the chunk
size. Dispatch via the `subagent` MCP tool with `role: trusted` (grants
file-read/write access); the `prompt_template` instructs the sub-agent to
`fs_read` the `prompt_path` and follow it, writing its output only via
`$SIFU_LOOM output init` then `$SIFU_LOOM output add`, never by hand.

Dispatch the entries of one chunk in a single `subagent` `stages` array with
no `depends_on`; complete them afterwards per Rule 7, one `complete` per
returned result.

## Helper: Drive human gate

Human tasks are conversational. Read the rendered prompt at
`message_path`, follow its instructions, STOP and wait for the user, then
write their decision and any edits only via `$SIFU_LOOM output init` then
`$SIFU_LOOM output add`, which validates each assignment against the task's
`io.yaml/output` schema. Complete the task per Rule 7.

For gates that show files, use the editor:

```bash
$SIFU_EDITOR show file <path>
```

## Plan visualisation

Task DAGs per graph, with the legend ○ tool · ◆ agent · ▣ human · ↻ loop:
[references/plan-topology.md](references/plan-topology.md).

## References

- [Rule codes](references/rule-codes.md) — rule codes, severity formula,
  review bands, topics, finding confidence.
- [Authoring rules](references/authoring.md) — layout, categories,
  frontmatter, skill types; [style](references/style.md),
  [completion](references/completion.md), [triggers](references/triggers.md).
- [Workflow conventions](references/workflow-conventions.md) — loomv2
  layout, driver, task naming, prompts.
- [Flow conventions](references/flow-conventions.md) — prose-step
  workflows that adapt while running.
- [Interface](references/interface-conventions.md),
  [tool](references/tool-conventions.md), and
  [reference](references/reference-conventions.md) conventions.
- [Script conventions](references/script-conventions.md),
  [secure-LLM conventions](references/secure-llm-conventions.md),
  [model awareness](references/model-awareness.md).
- Per-type design guidance:
  [interface](references/design-interface.md),
  [tool](references/design-tool.md),
  [workflow](references/design-workflow.md),
  [reference](references/design-reference.md),
  [flow](references/design-flow.md).

## Completion

| Status               | Criteria                                                   |
|----------------------|------------------------------------------------------------|
| `DONE`               | `publish-output` status `DONE`: create/update accepted at  |
|                      | `final-review`; review closed every finding, and each ✅   |
|                      | finding has a written file (guard in `publish-output`)     |
| `DONE_WITH_CONCERNS` | `publish-output` status `DONE_WITH_CONCERNS`: review fix   |
|                      | loop ran out of fuel with findings still open              |
| `BLOCKED`            | `runtime next` non-zero (incl. skill not found), a gate    |
|                      | declined, design loop out of fuel, or fixes claimed with   |
|                      | no file written                                            |
| `NEEDS_CONTEXT`      | `runtime init` rejected the op or name                     |
