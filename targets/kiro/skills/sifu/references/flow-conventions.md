# Flow Skill Conventions

Conventions for `type: flow` skills: workflows written as prose steps in
SKILL.md, executed by the agent, and adaptable while running. Supplements
`authoring.md`.

## Contents

- [1. Definition](#1-definition)
- [2. Structure](#2-structure)
- [3. Adaptation](#3-adaptation)
- [4. State and Scripts](#4-state-and-scripts)
- [5. Flow or Workflow](#5-flow-or-workflow)
- [6. Forbidden Shapes](#6-forbidden-shapes)

## 1. Definition

1. A flow skill MUST describe its process as numbered prose steps in
   SKILL.md, with no loom graph driving it.
2. The agent MAY adapt, reorder, repeat, or extend steps at the operator's
   request; the steps describe the default path, not a contract.
3. Example: `live-journal` (topic loop driven by the conversation).

## 2. Structure

1. New flow SKILL.md files MUST be rendered from sifu's
   `templates/skill/flow.md.j2`. Section order: Dependencies, Parameters,
   Aliases, Invariants, Workflow, Rules, Completion.
2. `## Workflow` MUST hold `### Step N: <name>` headings, each opening
   with a one-line goal, then at most 5 sub-steps. (check:
   `autochecks/flow_conventions.py:rule_2_2_workflow_section`)
3. `## Invariants` MUST list the rules that hold across every adaptation,
   placed above `## Workflow` so they are read first, e.g. "Commit the
   vault after every journal edit". (check:
   `autochecks/flow_conventions.py:rule_2_3_invariants_section`)
4. Every step SHOULD start with a tiling `activity set` naming the step,
   so the operator can see where the flow is.

## 3. Adaptation

1. Adaptations MUST stay inside the skill's purpose and its invariants; a
   request that breaks an invariant MUST be confirmed with the operator
   first.
2. The agent MUST announce each adaptation in one line before acting
   ("Skipping Step 3, the doc already has a summary").
3. Pauses for operator input MUST be explicit ("STOP and wait for user").

## 4. State and Scripts

1. Durable state SHOULD live in a user-visible artifact (a doc, a
   journal, a branch), not in agent memory, so the operator can resume or
   redirect from it.
2. Deterministic operations (file layout, commits, validation) MUST be
   scripts invoked through named aliases, per `script-conventions.md`;
   only judgement stays in prose.
3. A flow MAY delegate a fixed sub-pipeline to a loomv2 graph or another
   workflow skill; the flow itself stays prose.

## 5. Flow or Workflow

| Need                                               | Type       |
| -------------------------------------------------- | ---------- |
| Operator steers the next step turn by turn         | `flow`     |
| State lives in a user-visible artifact             | `flow`     |
| Resume after crash, schema-validated handoffs      | `workflow` |
| Parallel sub-agent fan-out, review loops with fuel | `workflow` |
| Fixed sequence, no interaction                     | `tool`     |

When two rows conflict, default to `workflow`, because a graph can still host
the human gates where an operator steers.

## 6. Forbidden Shapes

1. A flow MUST NOT be a fixed, non-interactive sequence, because that is
   a `tool`.
2. A flow MUST NOT reimplement task ordering, validation, or resume
   bookkeeping in prose, because that is a `workflow` and belongs in loom.
3. A flow MUST NOT contain API tables, because that is an `interface`.
