# Tool Skill Conventions

Conventions specific to skills with `type: tool`. These supplement the general
authoring rules in `authoring.md`.

## Contents

- [1. Definition](#1-definition)
- [2. Required Sections](#2-required-sections)
- [3. Step Rules](#3-step-rules)
- [4. Section Order](#4-section-order)
- [5. Forbidden Shapes](#5-forbidden-shapes)
- [6. Anti-Gaming Success Criteria](#6-anti-gaming-success-criteria)

## 1. Definition

1. A tool skill MUST be a fixed sequence of numbered steps executed without user
   interaction or iteration.
2. A tool has one implicit phase — it runs start to finish.
3. If the skill needs user input mid-execution or loops back to earlier steps,
   it is a `workflow`, not a `tool`.
4. Inputs MUST be gathered before step 1 (from the user's invocation message or
   from parameters); steps only execute.

## 2. Required Sections

1. A tool skill MUST contain a single `## Steps` section with a numbered list of
   indivisible actions that run in order without interruption. (check:
   `autochecks/tool_conventions.py:rule_2_1_steps_section`)

2. A tool skill MUST contain a `## Parameters` section listing inputs;
   parameters MUST either be provided in the user's invocation message or the
   skill MUST ask for them explicitly. (check:
   `autochecks/tool_conventions.py:rule_2_2_parameters_section`)

3. A tool skill SHOULD contain a `## Dependencies` section before `## Steps`
   when it depends on other skills or external tools.

4. A tool skill MAY contain `## Output` (when the tool produces a file or
   report) and `## Rules` (cross-step constraints) sections.

```markdown
## Steps

1. Detect workspace root:
   \`\`\`bash
   DETECT=~/.kiro/skills/<ns>/<skill>/scripts/detect-workspace.sh
   eval "$($DETECT)"
   \`\`\`
2. Query upstream service for metadata.
3. Build dependency tree by walking parent commits.
4. Write output to `/tmp/tree.md`.
5. Open in editor pane.
```

## 3. Step Rules

1. Each step MUST be a single action, not a sub-workflow.
2. Steps MUST be numbered, not bulleted. (check:
   `autochecks/tool_conventions.py:rule_3_2_steps_numbered`)
3. Steps MUST NOT branch ("if X then Y else Z"), because conditional logic
   belongs in a `workflow`.
4. Steps MAY include code blocks showing the exact command.
5. Error handling (e.g., "if step 2 fails, report BLOCKED") MUST go in the
   Completion section, not inline in steps.

## 4. Section Order

```
(description)
## Dependencies     (optional)
## Parameters
## Steps
## Output           (optional)
## Rules            (optional)
## Completion
```

## 5. Forbidden Shapes

1. Tool skills MUST NOT have multiple phases, because that is a `workflow`.
2. Tool skills MUST NOT request user interaction mid-execution, because that is
   a `workflow`.
3. Tool skills MUST NOT loop or iterate, because that is a `workflow`.
4. Tool skills MUST NOT contain API tables, because that is an `interface`.

## 6. Anti-Gaming Success Criteria

1. Steps with measurable outcomes (exit code zero, file created, schema
   validates, test passes) MUST include guards that prevent the LLM from
   satisfying the surface measure without satisfying the intent, because the
   model can weaken the oracle to make the step succeed.
2. Each measurable criterion MUST state what it checks (surface measure) and the
   underlying intent.
3. Each measurable criterion MUST add a guard that closes the gap, e.g.:

| Surface measure | Guard                                   |
| --------------- | --------------------------------------- |
| tests pass      | test count did not decrease versus base |
| file created    | content matches schema                  |
| lint clean      | lint config unchanged versus base       |
