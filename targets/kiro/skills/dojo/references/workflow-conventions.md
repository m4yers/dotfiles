# Workflow Skill Conventions

Conventions specific to skills with `type: workflow`. These supplement the
general authoring rules in `authoring.md`.

## Contents

- [1. Definition](#1-definition)
- [2. Structure](#2-structure)
- [3. Execution Driver](#3-execution-driver)
- [4. Task and File Naming](#4-task-and-file-naming)
- [5. Constructing Task Output](#5-constructing-task-output)
- [6. Prompt Templates](#6-prompt-templates)
- [7. Shell Variable Prefixing](#7-shell-variable-prefixing)
- [8. Step Rules](#8-step-rules)
- [9. User Interaction Points](#9-user-interaction-points)
- [10. Forbidden Shapes](#10-forbidden-shapes)
- [11. Anti-Gaming Success Criteria](#11-anti-gaming-success-criteria)

## 1. Definition

1. A workflow skill MUST be multi-step and often interactive, with steps
   containing sub-steps that MAY loop or wait for user input.
2. A fixed sequence with no interaction is a `tool`, not a `workflow`.
3. Steps are the unit of progress; sub-steps are the unit of work, and each
   sub-step MUST be a single indivisible action.

## 2. Structure

1. New workflow skills MUST be generated from
   `~/.kiro/skills/home/dojo/templates/skill/workflow.md.j2`, which encodes the
   required section order, the Step 1 (Ingest) skeleton, the loom-driven Step 2
   (Drive the loop), the dispatch-agent and human-gate helpers, and the
   activity-tracking pattern.

2. Hand-edited or pre-existing workflow SKILL.md files MUST conform to that
   template's section order, required sections, and activity-tracking pattern.
   (check: `autochecks/workflow_conventions.py:rule_2_2_activity_pattern`)

3. Reviews of a workflow SKILL.md MUST diff its rendered structure against the
   template, flagging any missing required section, divergent section order, or
   absent activity tracking.

## 3. Execution Driver

1. Workflow skills MUST use `loom` to drive execution; see
   `~/.kiro/skills/home/loom/SKILL.md` for its API and usage.
2. The orchestrator's per-step responsibility is bounded to: running `next` to
   obtain ready tasks, dispatching `agent` tasks via the `subagent` MCP tool,
   driving `human` gates conversationally, and calling `complete` when each task
   body finishes.
3. Skills MUST NOT reimplement task ordering, predicate evaluation, schema
   validation, or persistence in prose-driven steps, because every
   reimplementation drifts from the loom contract and breaks resumability.

## 4. Task and File Naming

1. A task and its bound resources MUST share the same base name. For task
   `<name>`: the output schema MUST be `schemas/<name>.yaml`, the agent or human
   prompt MUST be `templates/prompts/<name>.md.j2`, and any other per-task
   artefact MUST follow the same `<name>` convention. Aligned names make the
   task-resource graph visible by ls. (check:
   `autochecks/workflow_conventions.py:rule_4_1_name_alignment`)
2. Task ids, schema filenames, and prompt filenames MUST be domain-prefixed
   kebab-case (`<domain>-<action>`) so related tasks group visibly.
3. Every task id MUST match `^[a-z][a-z0-9]*(-[a-z0-9{}]+)+$` (at least one
   hyphen → a domain prefix); bare single-word ids (`build`, `lint`) MUST be
   prefixed (`build-compile`, `build-test`).
4. A schema or prompt shared by several tasks MUST take the shared domain prefix
   (e.g., `schemas/ws-clean.yaml` for `ws-clean-pre` / `ws-clean-post`).
5. Schema and prompt filename prefixes MUST be drawn from the task domain
   vocabulary; orphan prefixes are rejected by `dojo.sh check naming` before
   materialization.

## 5. Constructing Task Output

1. Agent tasks MUST construct schema-bound `output.yaml` via loom's writer
   (`loom output init` / `loom output add`), not via free-form `fs_write`,
   because eager schema validation surfaces violations at construction time and
   the writer normalises YAML shape.
2. `loom output add` MUST use dotted-path assignments — `[]` to append to
   arrays, `[-1]` to target the last appended entry, `.` for nested objects.
3. The `output.yaml` rule applies only to the loom task's own output; agent
   bodies MAY use `fs_write` for skill files (SKILL.md, scripts, schemas) they
   are creating.
4. Human gates that copy an upstream YAML verbatim MAY skip the writer, because
   the copy is schema-equivalent to the upstream YAML.

```bash
LOOM=~/.kiro/skills/home/loom/scripts/loom.sh
WD=<loom workdir>

$LOOM output init "$WD" --task <task-id>
$LOOM output add  "$WD" --task <task-id> \
    --set path.to.scalar=value \
    --set 'array_field[].sub_path=value' \
    --set 'array_field[-1].sibling=value'
```

## 6. Prompt Templates

1. Workflow skills with agent or human tasks MUST ship one Jinja prompt per task
   at `templates/prompts/<task-id>.md.j2`.
2. Each prompt MUST be terse, because fluff dilutes the agent's attention and
   inflates the workdir transcript.
3. Prompts MUST contain: a single H1 title naming the task, inputs (paths to
   upstream task outputs) at the top, a `## Task` (or per-step) section with
   imperative sentences, and a `## Output` section with the
   `loom output init`/`output add` example tailored to the task's schema.
4. Prompts MAY include type-specific or domain-specific guidance the agent
   cannot infer from the schema or shared conventions.
5. Prompts MUST NOT contain self-introductions ("You are the X agent…"), because
   the agent knows its role from its dispatch context.
6. Prompts MUST NOT restate field constraints already encoded in the JSON
   schema, because the writer rejects violations.
7. Prompts MUST NOT include meta-asides about why a thing is the way it is,
   unless the reasoning changes what the agent should do, because background
   context that does not alter the action is overhead.
8. Prompts MUST NOT duplicate fields between an intro list and per-section
   subsections, because duplication forces the agent to reconcile two sources of
   truth.

## 7. Shell Variable Prefixing

1. Caller-state variables (operation, name, tag, workdir, etc.) defined in
   SKILL.md MUST use a skill-specific 2–4 character prefix derived from the
   skill name (`dojo` → `DOJO_`, `cr-review` → `CR_`, `brazil-build` → `BB_`),
   because unprefixed names like `WD` or `OP` clobber each other when the user
   follows two skills' workflows back-to-back.
2. When two skills would collide on initials, authors MUST append a
   disambiguator (`swim-builder` → `SWB_`).
3. Script aliases keep bare names matching the target skill (`$DOJO`,
   `$TILING`); they never collide because each skill exposes a single shim under
   its own name. (See `script-conventions.md` § Script Invocation Paths.)
4. Reference files and scripts are exempt from the prefix rule, because they
   execute in their own process namespace, not pasted into the user's shell.

```bash
DOJO=~/.kiro/skills/home/dojo/scripts/dojo.sh
TILING=~/.kiro/skills/home/tiling/scripts/run-ttm.sh

DOJO_OP=create
DOJO_NAME=my-skill
DOJO_WD=$($DOJO ingest --op "$DOJO_OP" --name "$DOJO_NAME")

$DOJO next "$DOJO_WD"
$TILING activity set "dojo($DOJO_OP:$DOJO_NAME): ..."
```

## 8. Step Rules

1. Each step MUST have a descriptive name after the number (e.g., "Setup &
   Checkout", not just "Setup"). (check:
   `autochecks/workflow_conventions.py:rule_8_1_descriptive_step_name`)

2. Each step MUST have at most 5 numbered sub-steps, because longer steps are
   skipped or partially executed; split into more steps instead. (check:
   `autochecks/workflow_conventions.py:rule_8_2_max_substeps`)

3. A step MAY loop (e.g., "Repeat from sub-step 2 until all comments are
   addressed") or stop to wait for user input (e.g., "STOP and wait for user to
   review the diffs").

4. Transitions between steps MUST be explicit, stating what triggers moving to
   the next step.

5. Script invocations MUST appear as actual commands in fenced bash blocks, not
   as prose describing the call, because prose invocations hide arguments and
   drift from the real CLI. Exception: sibling skills referenced by name when
   the full command is documented in the other skill's SKILL.md.

## 9. User Interaction Points

1. Workflow pauses for user input MUST be explicit; phrase them as "STOP and
   wait for user", "Ask the user", or "On approval: proceed to Step N".
2. Inputs gathered before Step 1 (from the user's invocation message) MUST NOT
   be classified as interaction points, because they happen outside the numbered
   workflow.

## 10. Forbidden Shapes

1. Workflow skills MUST NOT be a single flat list of steps, because that is a
   `tool`.
2. Workflow skills MUST NOT contain API tables, because that is an `interface`.
3. Workflow skills MUST NOT be a passive rule set, because that is a
   `reference`.

## 11. Anti-Gaming Success Criteria

1. Success criteria that reference measurable outcomes (test count, coverage
   thresholds, lint clean, file presence) MUST include anti-gaming guards that
   prevent the LLM from trivially satisfying them, because the model can satisfy
   a criterion without satisfying its intent (deleting failing tests, writing
   no-op assertions, hard-coding expected values, relaxing the threshold).
2. Each measurable criterion MUST state what it checks (the surface measure) and
   the underlying intent (what the criterion proxies for).
3. Each measurable criterion MUST add a guard that closes the gap, e.g.:

| Surface measure         | Guard                                    |
| ----------------------- | ---------------------------------------- |
| tests pass              | test count did not decrease versus base  |
| lint clean              | lint config unchanged versus base        |
| expected output matches | expected file is the design fixture, not |
|                         | regenerated this run                     |
