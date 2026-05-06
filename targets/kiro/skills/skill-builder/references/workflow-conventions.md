# Workflow Skill Conventions

Conventions specific to skills with `type: workflow`. These
supplement the general conventions in `conventions.md`.

## Contents

- [What a Workflow Skill Is](#what-a-workflow-skill-is)
- [Required Sections](#required-sections)
- [Step Rules](#step-rules)
- [Activity Tracking](#activity-tracking)
- [User Interaction Points](#user-interaction-points)
- [Optional Sections](#optional-sections)
- [Section Order](#section-order)
- [What Does NOT Belong](#what-does-not-belong)
- [Principles](#principles)

## What a Workflow Skill Is

A multi-step, often interactive skill. Steps contain multiple
sub-steps and may loop or wait for user input. If the skill is a
fixed sequence with no interaction, it is a `tool`, not a
`workflow`.

## Required Sections

### 1. Workflow

A single `## Workflow` section containing numbered steps as
`### Step N: Name` subsections. Each step contains numbered
sub-steps.

```markdown
## Workflow

### Step 1: Setup & Checkout

1. Set tiling activity:
   \`\`\`bash
   $SKILLS/home/tiling/scripts/run-ttm.sh \
     activity set "skill-name(<target>): Setup & Checkout"
   \`\`\`
2. Detect workspace root.
3. Fetch CR metadata.

### Step 2: Analysis

1. Set tiling activity:
   \`\`\`bash
   $SKILLS/home/tiling/scripts/run-ttm.sh \
     activity set "skill-name(<target>): Analysis"
   \`\`\`
2. Spawn workers for each comment thread.
3. Collect results and categorize.
```

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

List skills or tools this workflow depends on, before the Workflow
section.

## Step Rules

- Each step MUST start with setting tiling activity
- Each step MUST have a descriptive name after the number (e.g.,
  "Setup & Checkout", not just "Setup")
- Each step MUST have at most 5 numbered sub-steps because longer
  steps are skipped or partially executed — split into more steps
  instead
- Steps are numbered sequentially starting from 1
- Sub-steps within a step are numbered sequentially
- A step MAY loop (e.g., "Repeat from sub-step 2 until all
  comments are addressed")
- A step MAY stop and wait for user input (e.g., "STOP and wait
  for user to review the diffs")
- Transitions between steps MUST be explicit — state what triggers
  moving to the next step
- Sub-step prose MUST NOT restate what a script does internally.
  The agent can read the script when details are needed. Prose is
  for information the agent cannot derive from the script alone:
  which parameter to use, what to do with the result, when to
  STOP, which step to loop back to. A one-line purpose ("render
  the report", "stage changes above the base commit") is fine;
  re-explaining algorithm, edge cases, or return values is not.
  Rationale: duplicated prose rots when the script changes and
  inflates the SKILL.md without adding actionable information.
- Script invocations MUST appear as actual commands in fenced
  bash blocks, not as prose describing the call (e.g. "run
  `reporter.sh strikeout` and reload"). Prose invocations hide
  arguments, force the agent to synthesize the command each run,
  and drift from the real CLI. Exception: sibling skills
  referenced by name (e.g. "build with <build-skill>") where the
  full command is documented in the other skill's SKILL.md.

## Activity Tracking

Every step MUST set tiling activity as its first sub-step. The
label MUST include the skill's target in parentheses so the user
can identify what is being worked on:

```bash
$SKILLS/home/tiling/scripts/run-ttm.sh \
  activity set "<skill-name>(<target>): <Step Name>"
```

The target is the skill's primary parameter — e.g., the skill
name being reviewed, the CR number, the cluster ID. Examples:
- `skill-reviewer(<skill>): Load Skill`
- `cr-review(<CR>): Post comments`
- `rca(<cluster-id>): Gather Data`

The final step MUST set activity to done when the workflow
completes:

```bash
$SKILLS/home/tiling/scripts/run-ttm.sh \
  activity set "<skill-name>(<target>): Done"
```

## User Interaction Points

Workflows often pause for user input. These MUST be explicit:

- Use "STOP and wait for user" when the workflow blocks until the
  user responds
- Use "Ask the user" when input is needed to proceed
- Use "On approval: proceed to Step N" for gated transitions

Inputs gathered before Step 1 (from the user's invocation message)
do not count as interaction points.

## Optional Sections

| Section    | When to include                         |
|------------|-----------------------------------------|
| `Rules`    | Cross-step constraints                  |
| Any helper | Reusable procedures referenced by       |
|            | multiple steps (e.g., "Build & Test",   |
|            | "Striking and Replying")                |

Helper sections sit after the Workflow section and are referenced
by name from within steps. They avoid duplicating sub-steps across
steps.

## Section Order

```
(description)
## Dependencies     (optional)
## Parameters
## Workflow
  ### Step 1: ...
  ### Step 2: ...
  ### Step N: ...
## <helper sections> (optional)
## Rules            (optional)
## Completion
```

## What Does NOT Belong

- A single flat list of steps — use `tool`
- API tables — use `interface`
- Passive rules — use `reference`

## Principles

- Steps are the unit of progress. The user should be able to tell
  which step is active from the tiling activity label.
- Sub-steps are the unit of work within a step. Each sub-step is
  one indivisible action.
- Explicit over implicit. Every transition, every stop point,
  every loop condition is written out.
