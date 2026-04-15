# Skill Conventions

Conventions for skills in `~/.kiro/skills/`. Derived from
existing skills — follow these patterns for consistency.

## Directory Structure

```
~/.kiro/skills/{category}/{skill-name}/
├── SKILL.md              # Required — main skill definition
├── references/           # Optional — queries, templates
│   └── queries.md
└── scripts/              # Optional — executable scripts
    ├── script.py
    └── pyproject.toml    # Optional — Python deps
```

## Categories

| Category      | Purpose                                    |
|---------------|--------------------------------------------|
| `tools/`      | Single-purpose utilities                   |
| `workflows/`  | Multi-phase interactive skills             |

Decision guide:
- Does it serve a single purpose with minimal
  interaction? → `tools/`
- Does it require multiple phases, user feedback,
  or orchestrate other skills? → `workflows/`

## Frontmatter

Required fields only:

```yaml
---
name: skill-name
description: What it does. Use when [trigger phrases].
---
```

- `name`: 1-64 chars, lowercase, hyphens only
- `description`: max 1024 chars, must include trigger
  keywords for routing

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

## Handle Policy

Skill files (SKILL.md, references, examples) MUST NOT
contain other people's Amazon aliases. If a handle is
needed in an example, use the user's own handle or a
generic placeholder (e.g., `userA`, `userB`).

## Python Scripts

Two rules based on whether the script has external deps:

### No dependencies (stdlib only)

Run directly:
```bash
python3 ~/.kiro/skills/{category}/{name}/scripts/script.py
```

No `pyproject.toml` needed.

### With dependencies

Create `pyproject.toml` in the `scripts/` directory:
```toml
[project]
name = "skill-name"
version = "0.1.0"
requires-python = ">=3.7"
dependencies = ["package>=version"]
```

Run via uv:
```bash
uv run \
  --project ~/.kiro/skills/{category}/{name}/scripts \
  python ~/.kiro/skills/{category}/{name}/scripts/script.py
```

uv creates a `.venv/` inside the `scripts/` directory
(next to `pyproject.toml`). This directory is auto-generated
and should be gitignored.
