# Tool Skill Conventions

Conventions specific to skills with `type: tool`. These supplement
the general conventions in `conventions.md`.

## What a Tool Skill Is

A fixed sequence of numbered steps executed without user interaction
or iteration. A tool has one implicit phase — it runs start to
finish. If the skill needs user input mid-execution or loops back
to earlier steps, it is a `workflow`, not a `tool`.

## Required Sections

### 1. Steps

A single `## Steps` section containing a numbered list. Each step
is one indivisible action. Steps run in order without interruption.

```markdown
## Steps

1. Detect workspace root:
   \`\`\`bash
   eval "$(~/.kiro/skills/dev/brazil-workspace/scripts/detect-workspace.sh)"
   \`\`\`
2. Query Gerrit for CR metadata using
   `~/.kiro/skills/dev/gerrit/scripts/gerrit.py change info --cr <CR>`.
3. Build dependency tree by walking parent commits.
4. Write output to `/tmp/cr-tree.md`.
5. Open in editor pane.
```

Rules for steps:
- Each step MUST be a single action, not a sub-workflow
- Steps MUST be numbered, not bulleted
- Steps MUST NOT branch ("if X then do Y, else do Z") because
  conditional logic belongs in a workflow
- Steps MAY include code blocks showing the exact command
- Error handling (e.g., "if step 2 fails, report BLOCKED") goes
  in the Completion section, not inline

### 2. Parameters

A `## Parameters` section listing the skill's inputs. Parameters
are either provided in the user's invocation message or the skill
MUST ask for them explicitly.

```markdown
## Parameters

- **name** (required): kebab-case skill name
- **category** (optional): `dev`, `diagnostics`, or
  `util` — searches all if not given
```

### 3. Dependencies (when needed)

List skills or tools this tool depends on, before Steps.

## Optional Sections

| Section    | When to include                         |
|------------|-----------------------------------------|
| `Output`   | When the tool produces a file or report |
| `Rules`    | When callers must follow constraints    |

## Section Order

```
(description)
## Dependencies     (optional)
## Parameters
## Steps
## Output           (optional)
## Rules            (optional)
## Completion
```

## What Does NOT Belong

- Multiple phases — use `workflow`
- User interaction mid-execution — use `workflow`
- Loops or iteration — use `workflow`
- API tables — use `interface`

## Principles

- A tool is a recipe. Read it top to bottom, execute it, done.
- If you need to ask the user something after step 1, it's not a
  tool.
- Inputs are gathered before step 1 (from the user's invocation
  message or from parameters). Steps only execute.
