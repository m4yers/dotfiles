# Interface Skill Conventions

Conventions specific to skills with `type: interface`. These supplement the
general authoring rules in `authoring.md`.

## Contents

- [1. Definition](#1-definition)
- [2. Required Sections](#2-required-sections)
- [3. Argument Consistency](#3-argument-consistency)
- [4. Section Order](#4-section-order)

## 1. Definition

1. An interface skill MUST provide an API consumed by other skills, with no
   user-facing steps.
2. The API table is the contract; if a command is not in the table, the
   interface MUST NOT provide it, because callers rely on the table as the
   exhaustive surface.
3. Callers MUST never need to read the script source — the Invocation, API, and
   Commands sections MUST be sufficient on their own.

## 2. Required Sections

1. An interface skill MUST contain an `## Invocation` section that shows the
   base command or import pattern as a single, complete invocation template that
   callers copy verbatim. (check: `autochecks/interface_conventions.py:rule_2_1_invocation_section`)

2. An interface skill MUST contain an `## API` section with a table summarising
   every operation; columns MUST be command name, arguments, and output, and the
   table MUST be exhaustive. (check: `autochecks/interface_conventions.py:rule_2_2_api_section`)

3. An interface skill MUST contain a `## Commands` section with one subsection
   per command listed in the API table, showing full invocation examples,
   argument descriptions, and behaviour notes. (check:
   `autochecks/interface_conventions.py:rule_2_3_commands_section`)

4. Every entry in the API table MUST have a corresponding `### Commands`
   subsection, because the API table is the contract and the Commands section is
   the manual. (check: `autochecks/interface_conventions.py:rule_2_4_api_commands_match`)

5. An interface skill MAY contain `## Defaults` (when commands have implicit
   defaults), `## Rules` (cross-command constraints), and `## References` (when
   detailed material lives in files) sections.

6. When the interface has multiple command groups (e.g., `layout`, `pane`,
   `activity`), commands SHOULD be grouped under subheadings in the API table.

```markdown
## Invocation

\`\`\`bash
TILING=~/.kiro/skills/home/tiling/scripts/run-ttm.sh
$TILING <group> <command> [options]
\`\`\`

## API

### group-name

| Command | Args    | Output             |
|---------|---------|--------------------|
| `cmd`   | `-t ID` | result description |

## Commands

### group cmd

Description of what the command does.

\`\`\`bash
$TILING group cmd -t $TARGET
\`\`\`

- `-t TARGET` — description (required)
- `-n` — description (optional)
```

## 3. Argument Consistency

1. Identical-looking flags across commands MUST mean the same thing, because
   inconsistent flag semantics force callers to memorise per-command quirks and
   break shell completion and scripting.
2. A flag MUST NOT accept different value types across commands (e.g., `-t`
   accepting a target id in one command and a file path in another), because
   shared flag semantics are the basis of caller intuition.
3. A flag that is required on most commands MAY be optional only on commands
   that operate over a default scope; the default MUST be explicitly documented.

## 4. Section Order

```
(description)
## Invocation
## API
## Commands
## Defaults        (optional)
## Rules           (optional)
## References      (optional)
## Completion
```
