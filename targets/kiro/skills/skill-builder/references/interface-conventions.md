# Interface Skill Conventions

Conventions specific to skills with `type: interface`. These
supplement the general conventions in `conventions.md`.

## Contents

- [Required Sections](#required-sections)
- [Optional Sections](#optional-sections)
- [Section Order](#section-order)
- [Principles](#principles)

## Required Sections

Every interface skill MUST have these three sections after the
introductory description:

### 1. Invocation

How callers invoke the interface. Shows the base command or import
pattern. Callers copy this verbatim — it MUST be a single, complete
invocation template.

```markdown
## Invocation

\`\`\`bash
~/.kiro/skills/util/tiling/scripts/run-ttm.sh \
  <group> <command> [options]
\`\`\`
```

For script-based interfaces, show the script path and argument
structure.

### 2. API

A table summarizing every operation the interface exposes. One row
per command. Columns: command name, arguments, and output. Callers
scan this table to find what they need — it MUST be exhaustive.

```markdown
## API

### group-name

| Command | Args    | Output              |
|---------|---------|---------------------|
| `cmd`   | `-t ID` | result description  |
```

Group related commands under subheadings when the interface has
multiple command groups (e.g., `layout`, `pane`, `activity`).

### 3. Commands

Detailed documentation for each command listed in the API table.
Shows full invocation examples, argument descriptions, and behavior
notes. One subsection per command.

```markdown
## Commands

### group cmd

Full description of what the command does.

\`\`\`bash
~/.kiro/skills/util/example/scripts/run.sh group cmd \
  -t $TARGET
\`\`\`

- `-t TARGET` — description (required)
- `-n` — description (optional)
```

## Optional Sections

| Section      | When to include                        |
|--------------|----------------------------------------|
| `Defaults`   | When commands have implicit defaults   |
| `Rules`      | When callers must follow constraints   |
| `References`  | When detailed material lives in files |

## Section Order

```
(description)
## Invocation
## API
## Commands
## Defaults        (optional)
## Rules           (optional)
## Completion
```

## Principles

- The API table is the contract. If it's not in the table, the
  interface doesn't provide it.
- Commands section is the manual. Every API entry MUST have a
  corresponding Commands subsection.
- Callers should never need to read the script source. The
  Invocation + API + Commands sections MUST be sufficient.
