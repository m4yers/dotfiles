# Workflow Skill Conventions

Conventions specific to skills with `type: workflow`. These
supplement the general conventions in `conventions.md`.

## Contents

- [What a Workflow Skill Is](#what-a-workflow-skill-is)
- [Execution Driver: Loom](#execution-driver-loom)
- [Constructing Task Output](#constructing-task-output)
- [Prompt Templates](#prompt-templates)
- [Shell Variable Prefixing](#shell-variable-prefixing)
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

## Execution Driver: Loom

Workflow skills MUST use `loom` (`~/.kiro/skills/home/loom/`) to
drive execution. Loom provides DAG scheduling, predicate-gated
skip logic, schema-validated outputs, Jinja prompt rendering, and
crash-resumable workdir state — exactly the machinery a workflow
needs. Prose-driven steps without a loom plan cannot reliably
encode dependencies, validate outputs, or resume mid-run, so they
fail silently when the workflow is interrupted or extended.

Two acceptable shapes:

1. **Wrapper-script driver.** The skill ships a Python module
   that builds a loom plan via `loom.init` / `loom.resume`,
   exposed through a `scripts/<name>.sh` shim with subcommands
   like `ingest`, `next`, `complete`, `report`, `pipeline`. The
   workflow steps in `SKILL.md` call the shim. The orchestrator
   (the LLM) drives the `next → dispatch → complete` loop.
2. **Inline loom driver.** For small workflows, the skill calls
   loom directly from a `scripts/run.py`, and `SKILL.md` walks
   the user through invoking it. Still requires a static plan
   built with `make_plan`.

The orchestrator's per-step responsibility is bounded:

- Run `next` to obtain ready tasks.
- Dispatch `agent` tasks via the `subagent` MCP tool.
- Drive `human` gates conversationally.
- Call `complete` when the task body finishes.

Loom owns task ordering, predicate evaluation, schema validation,
and persistence. The skill MUST NOT reimplement these in
prose-driven steps because every reimplementation drifts from the
loom contract and breaks resumability.

See `~/.kiro/skills/home/cr-review/SKILL.md` for an example
workflow that uses loom via a wrapper script
(`scripts/cr-review.sh`).

## Constructing Task Output

Agent tasks in a workflow MUST construct their schema-bound
`output.yaml` via loom's writer, not via free-form `fs_write`:

```bash
LOOM=~/.kiro/skills/home/loom/scripts/loom.sh
WD=<loom workdir>

$LOOM output init "$WD" --task <task-id>
$LOOM output add  "$WD" --task <task-id> \
    --set path.to.scalar=value \
    --set 'array_field[].sub_path=value' \
    --set 'array_field[-1].sibling=value'
```

`init` embeds the task's `output_schema` and seeds required
arrays/objects. `add` applies dotted-path assignments and
validates after every call, so a malformed value fails fast
with the violating path. `[]` appends to an array; `[-1]`
targets the last appended entry; nested objects use `.`.

Why this is required:

- Eager validation surfaces schema violations at construction
  time rather than at `loom complete`, where the failure
  message is more abstract.
- The emitted YAML is normalized (key order, indentation, no
  flow style), so downstream tasks and renderers see a
  predictable shape.
- Sub-agents dispatched via the `subagent` MCP tool can call
  the writer through the loom shim and produce schema-valid
  output.yaml without hand-writing YAML.

Exceptions:

- Skill-file writes inside the agent's task body — `fs_write`
  is correct for SKILL.md, scripts, schemas the agent is
  *creating* under the skill directory. Only the loom task's
  own `output.yaml` must go through `loom output`.
- Human gates that copy an upstream YAML verbatim into the
  gate's output (e.g. design-review). The copy semantics are
  schema-equivalent to the upstream YAML; loom's writer is
  unnecessary.

## Prompt Templates

Workflow skills with agent or human tasks ship one Jinja
prompt per task under `templates/prompts/<task-id>.md.j2`.
Each prompt MUST be terse — fluff dilutes the agent's
attention and inflates the workdir transcript.

Keep:

- The single H1 title naming the task.
- Inputs (paths to upstream task outputs) at the top.
- A `## Task` (or per-step) section stating what to do, in
  imperative sentences.
- A `## Output` section with the loom `output init`/`output
  add` example tailored to the task's `output_schema`.
- Type-specific or domain-specific guidance the agent
  cannot infer from the schema or shared conventions.

Cut:

- Self-introductions ("You are the X agent ..."). The agent
  knows its role from its dispatch context.
- Restating field constraints already encoded in the JSON
  schema (the writer will reject violations).
- Meta-asides about why a thing is the way it is, unless the
  reasoning changes what the agent should do.
- Numbered "produce a design covering" lists when the loom-
  output bash example already shows the same fields.
- Repetition between an intro list and per-section
  subsections.
- Pointers to ancillary documentation the agent does not
  need to make a correct decision.

Affirmative wording (see steering) and the verbatim
guidance in `~/.kiro/skills/home/dojo/references/conventions.md`
apply.

## Shell Variable Prefixing

Every shell variable defined in SKILL.md MUST use a
skill-specific prefix derived from the skill name (typically
the initials, e.g. `DOJO_` for `dojo`, `CR_` for
`cr-review`). Both the assignment and every reference
use the prefix.

Why: SKILL.md snippets are often pasted into a single shell
session. Without prefixes, two skills that both define
`WD`, `SKILLS`, `EDITOR`, etc. clobber each other when the
user follows their workflows back-to-back.

Example:

```bash
SB_SKILLS=~/.kiro/skills
DOJO_SH=$DOJO_SKILLS/home/dojo/scripts/dojo.sh
SB_TILING=$SB_SKILLS/home/tiling/scripts/run-ttm.sh
SB_WD=$($SB_BUILDER ingest --op create)
$SB_BUILDER next "$SB_WD"
```

Choose a 2–4 character prefix:

- For most skills, the initials of the kebab-case name
  (`dojo` → `DOJO_`, `cr-review` → `CR_`,
  `brazil-build` → `BB_`).
- If two skills would collide on initials, append a
  disambiguator (`dojo` → `DOJO_`,
  `swim-builder` → `SWB_`).

The prefix is documented implicitly by usage — every
variable in the skill's SKILL.md uses it. Reference files
and scripts are exempt because they execute in their own
process namespace, not pasted into the user's shell.

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
- `dojo(<op>:<skill>): Load Skill`
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

## Anti-Gaming Success Criteria

Success criteria that reference measurable outcomes (test count,
coverage thresholds, lint clean, file presence) MUST include
anti-gaming guards that prevent the LLM from trivially
satisfying them. The model can satisfy a criterion without
satisfying its intent — by deleting the failing tests, writing
no-op assertions, hard-coding expected values, or relaxing the
threshold.

For each measurable criterion:

- State what the criterion checks (the surface measure).
- State the underlying intent (what the criterion is a proxy
  for).
- Add a guard that closes the gap. Examples:
  - "tests pass" + "test count did not decrease versus base"
  - "lint clean" + "lint config unchanged versus base"
  - "expected output matches" + "expected file is the design's
    fixture, not regenerated this run"

A criterion without a guard is a degree of freedom for the
agent to weaken its own oracle.

## Principles

- Steps are the unit of progress. The user should be able to tell
  which step is active from the tiling activity label.
- Sub-steps are the unit of work within a step. Each sub-step is
  one indivisible action.
- Explicit over implicit. Every transition, every stop point,
  every loop condition is written out.
