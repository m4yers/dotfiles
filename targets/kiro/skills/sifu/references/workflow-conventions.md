# Workflow Skill Conventions

**Code:** WFL
**Applies:** type:workflow

Conventions for `type: workflow` skills. Loomv2 is the default and only
supported driver; legacy-loom skills SHOULD migrate. Supplements
`authoring.md`.

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

1. (rule: WFL-1-1, severity: 80) A workflow skill MUST be multi-step and often
   interactive, executed as a loomv2 graph of tool, agent, and human tasks.
2. (rule: WFL-1-2, severity: 10) A fixed sequence with no interaction is a
   `tool`; prose steps the agent adapts while running are a `flow` (see
   `flow-conventions.md`).
3. (rule: WFL-1-3, severity: 10) Steps in SKILL.md are the unit of progress for
   the orchestrator; graph tasks are the unit of work.

## 2. Structure

1. (rule: WFL-2-1, severity: 70) New workflow SKILL.md files MUST be rendered
   from sifu's `templates/skill/workflow.md.j2`, which composes the loomv2 host
   templates (`step-drive-loop`, `helper-dispatch-agent`,
   `helper-drive-human-gate`) with skill-specific frontmatter, parameters,
   rules, and completion. Step 1 is the template's own because the loomv2
   `step-ingest` partial carries no alias, caller-state, or layout setup.
2. (rule: WFL-2-2, severity: 80) Every `### Step N` MUST start with a tiling
   `activity set` whose label carries the target, `skill(<target>): Step`.
   (check: `autochecks/workflow_conventions.py:rule_2_2_activity_pattern`)
3. (rule: WFL-2-3, severity: 70) Reviews MUST diff an existing SKILL.md against
   the template's section order and flag missing sections or absent activity
   tracking.

Layout:

```
<skill>/
├── SKILL.md
├── loom/                   # loom root (one per graph family)
│   ├── graph.yaml          # or graph-<variant>.yaml
│   └── <task>/
│       ├── io.yaml         # IO contract (input/output JSON Schema)
│       └── tool.py | tool.sh | prompt.md.j2 | message.md.j2
├── loom-<sub>/             # optional subgraph root, same shape
├── schemas/                # shared `$ref` targets for io.yaml
├── references/             # `{% raw %}{% include %}{% endraw %}` targets for prompts
└── scripts/                # packaged tool bodies (tool.sh -> shim)
```

## 3. Execution Driver

1. (rule: WFL-3-1, severity: 90) Workflow skills MUST be driven by a loomv2
   graph under a `loom*/` root; see `~/.kiro/skills/home/loomv2/SKILL.md`.
   Skills still on legacy loom SHOULD migrate. (check:
   `autochecks/workflow_conventions.py:rule_3_1_loomv2_driver`)
2. (rule: WFL-3-2, severity: 90) SKILL.md MUST call the loomv2 CLI directly:
   `runtime init` (auto workdir, `--graph` per variant, `--set` to seed the
   entry), then `runtime next` / `runtime complete`. A per-skill drive shim MUST
   NOT be added, because it forks the loomv2 API surface.
3. (rule: WFL-3-3, severity: 35) The orchestrator's job is bounded to: `runtime
   next`, executing the surfaced agent and human tasks, and `runtime complete`
   per task. When a `ready` batch holds exactly one agent task, the orchestrator
   MAY run it inline: read `prompt_path`, follow it, write the output, then
   complete. A batch with two or more agent tasks MUST be dispatched as parallel
   sub-agents, because serial dispatch drops the DAG's concurrency.
4. (rule: WFL-3-4, severity: 90) Every graph file MUST pass `$LOOM validate
   <skill> --graph <abs path>`; run it after every graph or `io.yaml` edit.
   (check: `autochecks/workflow_conventions.py:rule_3_4_graphs_validate`)
5. (rule: WFL-3-5, severity: 85) Skills MUST NOT reimplement ordering,
   predicates, schema validation, or persistence in prose, because loom owns
   them and drift breaks resume.
6. (rule: WFL-3-6, severity: 90) Loop outflow MUST leave through the latch. When
   downstream tasks need a loop-body value (a design, a plan), make the latch a
   pass-through tool that carries it out of the region.

## 4. Task and File Naming

1. (rule: WFL-4-1, severity: 90) Every task folder MUST back a graph entry (by
   `id` or `ref`), hold an `io.yaml`, and hold exactly one body file for its
   kind: `tool.py` or `tool.sh` (tool), `prompt.md.j2` (agent), `message.md.j2`
   (human). (check:
   `autochecks/workflow_conventions.py:rule_4_1_task_folder_alignment`)
2. (rule: WFL-4-2, severity: 50) The entry task SHOULD be `ingest-input` and the
   exit `publish-output`, per the naming conventions in loomv2's grammar
   reference.
3. (rule: WFL-4-3, severity: 70) Other task ids MUST be domain-prefixed kebab
   (`<domain>-<action>`, matching `^[a-z][a-z0-9]*(-[a-z0-9{}]+)+$`) so related
   tasks group.
4. (rule: WFL-4-4, severity: 70) Fan-out of one task definition MUST use `ref`
   instances of one folder; reuse of a whole sub-pipeline MUST use a `kind:
   subgraph` entry.
5. (rule: WFL-4-5, severity: 10) Shared schemas live in top-level `schemas/` and
   are pulled into `io.yaml` via relative `$ref` (`../../schemas/<name>.yaml`).

## 5. Constructing Task Output

1. (rule: WFL-5-1, severity: 90) Agent and human tasks MUST write `output.yaml`
   via `$LOOM output init` and `$LOOM output add`, not free-form writes, because
   the writer validates each assignment against `io.yaml`.
2. (rule: WFL-5-2, severity: 10) `output add --set` takes dotted paths (`[]`
   append, `[-1]` last entry); `--set-json` takes JSON values and nested
   objects.
3. (rule: WFL-5-3, severity: 90) When data may be absent, the producer MUST emit
   the explicit empty value (`[]`, `""`, `null`) rather than omit a required
   field, because omission defeats loomv2's static alignment check.
4. (rule: WFL-5-4, severity: 20) Agent bodies MAY use direct file writes for
   skill files they create.
5. (rule: WFL-5-5, severity: 90) `--set` coerces numeric-looking values to int
   or float, at `runtime init` and in `output add`. An entry field that may be
   given as a bare number (a CR number, a ticket id) MUST accept `type: [string,
   integer]`, because a string-only schema rejects it.

```bash
LOOM=~/.kiro/skills/home/loomv2/scripts/loom.sh
$LOOM output init "$WD" --task <task-address>
$LOOM output add  "$WD" --task <task-address> \
    --set 'items[].name=a' --set 'items[-1].size=3' \
    --set-json 'tags=[]'
```

## 6. Prompt Templates

1. (rule: WFL-6-1, severity: 90) Each agent task MUST ship `prompt.md.j2`, each
   human task `message.md.j2`, in its task folder; they render against
   `input.yaml` as `input.<field>`.
2. (rule: WFL-6-2, severity: 90) Prompts MUST read the loom CLI and workdir from
   `input.__loom.runtime` and `input.__loom.workdir`, and their own address from
   `input.__task.id`; declare `__loom: {}` / `__task: {}` in `io.yaml`.
3. (rule: WFL-6-3, severity: 65) Each prompt MUST be terse: H1 naming the task
   (after the security-frame include when WFL-6-5 applies), inputs at the top,
   a `## Task` section in imperative sentences, and a `## Output` section with
   the `output init` / `output add` call for its schema.
4. (rule: WFL-6-4, severity: 85) Prompts MUST NOT contain self-introductions,
   restate schema constraints, or carry meta-asides that do not change the
   action, because each one dilutes the instruction the agent must follow.
5. (rule: WFL-6-5, severity: 95) Prompts consuming external content MUST start
   with `{% raw %}{% include 'security-frame.md.j2' %}{% endraw %}`; see
   `secure-llm-conventions.md`.

## 7. Shell Variable Prefixing

1. (rule: WFL-7-1, severity: 70) Caller-state variables in SKILL.md MUST use a
   2–4 character prefix from the skill name (`sifu` → `SIFU_`, `cr-review` →
   `CR_`), because bare names like `WD` clobber each other across skills.
2. (rule: WFL-7-2, severity: 10) On a prefix collision, append a disambiguator
   (`swim-builder` → `SWB_`).
3. (rule: WFL-7-3, severity: 10) Script aliases are named per SCR-3-1: the
   caller prefix plus the target name (`$SIFU_LOOM`, `$SIFU_TILING`).
4. (rule: WFL-7-4, severity: 10) Reference files and scripts are exempt; they
   run in their own process.

```bash
SIFU_LOOM=~/.kiro/skills/home/loomv2/scripts/loom.sh
SIFU_OP=create
SIFU_WD=$($SIFU_LOOM runtime init --loom-root "$SIFU_ROOT/loom" \
    --graph "graph-$SIFU_OP.yaml" --set op="$SIFU_OP" --set name=my-skill)
```

## 8. Step Rules

1. (rule: WFL-8-1, severity: 65) Each step MUST have a descriptive name after
   the number. (check:
   `autochecks/workflow_conventions.py:rule_8_1_descriptive_step_name`)
2. (rule: WFL-8-2, severity: 80) Each step MUST have at most 5 numbered
   sub-steps, because longer steps are skipped or partially executed. (check:
   `autochecks/workflow_conventions.py:rule_8_2_max_substeps`)
3. (rule: WFL-8-3, severity: 20) A step MAY loop or stop for user input.
4. (rule: WFL-8-4, severity: 80) Transitions between steps MUST be explicit.
5. (rule: WFL-8-5, severity: 80) Script invocations MUST appear as commands in
   fenced bash blocks.

## 9. User Interaction Points

1. (rule: WFL-9-1, severity: 80) Pauses for user input MUST be explicit ("STOP
   and wait for user"). Human gates MUST be driven by the user, never
   auto-completed.
2. (rule: WFL-9-2, severity: 10) Inputs from the invocation message are not
   interaction points.

## 10. Forbidden Shapes

1. (rule: WFL-10-1, severity: 85) A workflow MUST NOT be a single flat list of
   steps, because that is a `tool`.
2. (rule: WFL-10-2, severity: 85) A workflow MUST NOT contain API tables,
   because that is an `interface`.
3. (rule: WFL-10-3, severity: 85) A workflow MUST NOT be a passive rule set,
   because that is a `reference`.
4. (rule: WFL-10-4, severity: 85) A workflow MUST NOT be prose-only steps with
   no graph, because that is a `flow`.

## 11. Anti-Gaming Success Criteria

1. (rule: WFL-11-1, severity: 80) Measurable success criteria (tests pass, lint
   clean, file present) MUST carry a guard against trivial satisfaction, because
   the model can meet a criterion without meeting its intent.
2. (rule: WFL-11-2, severity: 80) Each criterion MUST state its surface measure
   and its intent.

| Surface measure         | Guard                                       |
| ----------------------- | ------------------------------------------- |
| tests pass              | test count did not decrease versus base     |
| lint clean              | lint config unchanged versus base           |
| expected output matches | expected file is the fixture, not rewritten |
