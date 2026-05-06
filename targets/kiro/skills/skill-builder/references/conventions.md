# Skill Conventions

Conventions for skills in `~/.kiro/skills/`. Derived from existing
skills — follow these patterns for consistency.

## Contents

- [Directory Structure](#directory-structure)
- [Categories](#categories)
- [Frontmatter](#frontmatter)
- [Skill Types](#skill-types)
- [Style Guide](#style-guide)
- [Script APIs](#script-apis)
- [Degrees of Freedom](#degrees-of-freedom)
- [Token Budget](#token-budget)
- [Completion Status](#completion-status)
- [Skill Usage Analytics](#skill-usage-analytics)
- [Handle Policy](#handle-policy)
- [Python Scripts](#python-scripts)

## Directory Structure

Top-level layout:

```
~/.kiro/skills/
├── dev/           # Build, test, and development workflows
├── diagnostics/   # Cluster diagnostics, log tools, and RCA
└── util/          # Meta-skills, vault, retro, utilities
```

Each skill directory:

```
~/.kiro/skills/{category}/{skill-name}/
├── SKILL.md              # Required — main skill definition
├── references/           # Optional — reference docs, guides
│   └── queries.md
├── templates/            # Optional — fill-in templates,
│   └── example.md        #   examples, scoring rubrics
└── scripts/              # Optional — executable scripts
    ├── script.py
    └── pyproject.toml    # Optional — Python deps
```

`references/` holds docs the model reads for guidance
(algorithms, schemas, merge procedures, select criteria).
`templates/` holds files that are copied and filled in
(artifact templates, example outputs, stage templates).
If a file has placeholders or is used as a starting
point, it belongs in `templates/`.

## Categories

| Category       | Purpose                            |
|----------------|------------------------------------|
| `dev/`         | Build, test, development workflows |
| `diagnostics/` | Cluster diagnostics, logs, and RCA |
| `util/`        | Meta-skills, vault, utilities      |

Decision guide:
- Does it build or test code? → `dev/`
- Does it connect to a live cluster, fetch logs, or
  investigate issues? → `diagnostics/`
- Is it a tool for managing the Kiro setup? → `util/`

## Frontmatter

Required fields:

```yaml
---
name: skill-name
type: interface
description: What it does. Use when [trigger phrases].
---
```

- `name`: 1-64 chars, lowercase, hyphens only
- `type`: one of `interface`, `tool`, `workflow`, `reference`
- `description`: max 1024 chars, must include trigger
  keywords for routing. Write in third person ("Extracts
  text from PDFs") not first/second person ("I help you
  extract" or "Use this to extract")

## Skill Types

| Type        | Definition                              |
|-------------|-----------------------------------------|
| `interface` | Provides an API consumed by other       |
|             | skills. No user-facing steps. Examples: |
|             | tiling, editor, template                |
| `tool`      | Fixed sequence of indivisible steps.    |
|             | No iteration or user interaction mid-   |
|             | execution. Examples: cr-tree, cr-push   |
| `workflow`  | Multi-step, often interactive. Steps    |
|             | contain multiple sub-steps and may loop.|
|             | Examples: cr-review, make, rca          |
| `reference` | Passive rule set loaded as context when |
|             | triggered. No invocation, API, or       |
|             | steps. Examples: writing-cpp, obsidian  |

A step is a numbered workflow section (e.g., "Gather
Requirements"). A sub-step is a single indivisible
action within a step. Only workflows have steps.

## Style Guide

Based on patterns in existing skills:

1. **Concise over verbose** — tables for reference data
2. **Aliases and commands up front** — users need the "how"
3. **No README.md** — SKILL.md is the single source of truth
4. **Constraints use RFC2119** — MUST, SHOULD, MAY,
   MUST NOT + reason
5. **SQL queries in references/** — keeps SKILL.md scannable
6. **Scripts in scripts/** — in a `scripts/` subfolder, not
   loose in the skill directory
7. **Tables whitespace-formatted** — align columns with
   spaces for readability
8. **Prose wrapped at 80 chars** — lines MUST fill to at
   least 75 chars before wrapping, unless the sentence
   naturally ends before that. Tables may extend to 100
   chars if needed for readability
9. **Frontmatter on single lines** — name and description
   stay on one line each
10. **Positive framing over negation** — describe the
    desired behavior, not the forbidden one. Prefer
    "Always validate input before proceeding" over "Do
    NOT skip validation." Reserve MUST NOT for hard
    safety boundaries only.
11. **Plain RFC2119, no emphasis stacking** — RFC2119
    keywords (MUST, SHOULD, MAY) are sufficient on their
    own. Do not add ALL-CAPS prefixes like "CRITICAL",
    "IMPORTANT", or "ALWAYS" before them, and do not
    use exclamation marks. The model overtriggers on
    amplified language.
12. **Challenge every token** — before adding content,
    ask: "Does the model really need this explanation?"
    and "Can I assume it already knows this?" Only add
    context the model does not already have.
13. **One default, not many options** — when multiple
    approaches exist, provide one recommended default
    with an escape hatch for edge cases. Do not list
    alternatives unless the choice depends on context
    the model cannot infer.
14. **References reachable from SKILL.md** — every file
    under `references/` MUST be reachable from SKILL.md
    through the markdown link graph. Chained references
    (SKILL.md → A.md → B.md) are allowed as long as every
    reference file is reachable. Unreachable reference
    files are dead weight.
15. **TOC for long references** — reference files over
    100 lines should start with a table of contents so
    the model can see the full scope even when previewing
    with partial reads.

## Script APIs

See `references/script-conventions.md` for script APIs,
executable oracles, and Python script packaging rules.

## Degrees of Freedom

Match the specificity of instructions to the task's
fragility:

| Freedom | When to use                       | Example              |
|---------|-----------------------------------|----------------------|
| High    | Multiple valid approaches, context| Code review criteria |
|         | determines the best path          |                      |
| Medium  | Preferred pattern exists but some | Report templates     |
|         | variation is acceptable           |                      |
| Low     | Operations are fragile, sequence  | DB migrations, build |
|         | matters, consistency is critical  | scripts              |

High freedom: text-based guidance, let the model decide.
Medium freedom: pseudocode or parameterized scripts.
Low freedom: exact scripts with no modification allowed.

## Token Budget

Every artifact has a context cost:

| Artifact        | When loaded          | Cost   |
|-----------------|----------------------|--------|
| Steering file   | Every conversation   | High   |
| Skill name+desc | Every conversation   | Low    |
| SKILL.md body   | When skill activated | Medium |
| Reference file  | When explicitly read | Low    |

Implication: a rule in steering burns tokens in every
conversation. A rule in a skill only burns tokens when that
skill fires. A rule in a reference file only burns tokens
when explicitly loaded.

**Before adding a steering rule:** Would it be useful in the
majority of conversations? If not, it belongs in a skill.
Can it be folded into an existing steering file?

**Before creating a new skill:** Can an existing skill's
scope be broadened instead? Every new skill adds routing
cost. The bar for "new skill" should be higher than "new
feature."

**Before adding content to SKILL.md:** Is this reference
material only needed in specific steps? Move it to
`references/` and load on demand.

## Completion Status

Every skill MUST end with a `## Completion` section that
defines terminal states. Use these four statuses:

| Status               | Meaning                              |
|----------------------|--------------------------------------|
| `DONE`               | All steps completed, evidence shown  |
| `DONE_WITH_CONCERNS` | Completed but with caveats listed    |
| `BLOCKED`            | Cannot proceed, state what blocks    |
| `NEEDS_CONTEXT`      | Missing info, state what is needed   |

The section MUST define what DONE means for this specific
skill. Generic "task completed" is not sufficient — state
the concrete evidence (e.g., "report saved to /tmp",
"drafts published to Gerrit", "root cause identified and
fix verified").

Include an escalation rule when the skill involves
iteration or investigation:

```markdown
- You MUST stop after 3 failed attempts and report
  status BLOCKED with what was tried
```

Example:

```markdown
## Completion

| Status               | Criteria                            |
|----------------------|-------------------------------------|
| `DONE`               | Review report saved, drafts posted  |
| `DONE_WITH_CONCERNS` | Report saved, some files unreadable |
| `BLOCKED`            | CR checkout failed or no diff found |
| `NEEDS_CONTEXT`      | CR URL not provided                 |
```

## Skill Usage Analytics

Every skill MUST log its activation per the
`skill-analytics` skill
(`~/.kiro/skills/home/skill-analytics/SKILL.md`).

## Script Invocation Paths

Script invocations in SKILL.md and reference files MUST use
the `$SKILLS` shell variable, set once at the top of Step 1
(`SKILLS=~/.kiro/skills`). Hardcoded `~/.kiro/skills/.../scripts/`
paths inside fenced code blocks are rejected by
`skill-lint.py`. Full rule and rationale:
`script-conventions.md` § Script Invocation Paths.

## Template Rendering

Any text generated from a parameterized template — sub-agent
prompts, config files, generated markdown, report fragments —
MUST be rendered via the `template` skill:

```bash
$SKILLS/home/template/scripts/render.sh \
    --template <path> --var k=v [--var ...]
```

Skills MUST NOT vendor `jinja2`, implement ad-hoc placeholder
substitution (f-strings with `%s`/`{}`, `sed` pipelines,
`envsubst`), or write per-skill render wrappers. Templates
live under `<skill>/templates/<name>.j2`. The renderer
validates that every template variable is supplied and every
supplied variable is used — typos and missing values fail
fast instead of producing silently-wrong prompts.

## Handle Policy

Skill files (SKILL.md, references, examples) MUST NOT
contain other people's aliases because it exposes PII. If
a handle is needed in an example, use the user's own handle
or a generic placeholder (e.g., `userA`, `userB`).

## Python Scripts

See `references/script-conventions.md` for Python script
packaging rules (stdlib-only vs. with dependencies).
