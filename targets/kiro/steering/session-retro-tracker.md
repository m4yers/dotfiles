# Session Learnings Tracker

Throughout every conversation, track learnings by writing them to disk. These
are findings worth encoding into skills, steering, or vault.

## Critical Rule

Write retro items THE MOMENT you identify them — in the same response where
the learning occurred. Do NOT wait until the user asks. Do NOT batch for later.

**Enforcement:** After ANY user correction, self-correction, or new discovery,
the FIRST action in your response MUST be writing the retro JSON file. Do not
continue with the task until the file is written. If you realize you forgot,
write it immediately — do not wait for the next user message.

Triggers:
- User corrected you (factual error, wrong approach)
- You self-corrected a tool usage mistake
- New knowledge that fits a skill or steering improvement
- Workflow pattern that should be a skill
- Behavioral rule that should be steering
- Missing capability the user worked around

## Storage

### Area Mapping

When choosing `area` for a retro item:
1. Is there an existing skill that covers this topic?
   → `area=skill, action=update, target=<skill-name>`
2. Is there an existing steering file?
   → `area=steering, action=update, target=<file>`
3. Neither? → `steering/new` or `skill/new`

Learnings are stored as individual JSON files in:
```
~/.kiro/retro/pending/
```

Write retro items using the writer script:
```bash
python3 ~/.kiro/skills/util/retro/scripts/write-retro-item.py \
  --dir ~/.kiro/retro/pending/ \
  --area <area> --action <action> --severity <severity> \
  --title "<title>" --detail "<detail>" \
  --evidence "<evidence>" [--target <name>]
```

The script creates the directory if needed, validates inputs, and writes a
timestamped JSON file with this schema:

```json
{
  "area": "skill|steering|vault|prompt",
  "action": "new|update",
  "severity": "high|medium|low",
  "target": "short name or null",
  "title": "short description",
  "detail": "what happened and what should change",
  "evidence": "relevant conversation context"
}
```

## What counts as a learning

- User corrected you (factual error, wrong approach, bad default)
- New knowledge that should be captured in skills or steering
- Workflow pattern that should be a skill or skill improvement
- Behavioral rule that should be steering
- Missing capability the user worked around
- Tool usage mistake you self-corrected

## What does NOT count

- Routine task completion
- Things already in skills/steering/vault
- Transient details (ticket IDs, cluster names)

## Behavior

1. Write it to `~/.kiro/retro/pending/{N}.json`
2. At the very end of your response, append:

```
[RETRO] Learnings so far: N
```

Where N is the total file count in the retro directory. Do NOT show the line
if the count is 0.

3. STOP. Do NOT implement the change (steering updates, script
   modifications, skill changes, vault writes) in the same response.
   The retro file captures the intent; acting on it only happens
   when the user explicitly asks for a retro.

The user can say "retro" at any time to review and act on learnings.

## Formatting

When retro items modify skill files (SKILL.md or references/), you MUST follow
the conventions in `~/.kiro/skills/util/skill-builder/references/conventions.md`
(80-char prose, aligned tables, single-line frontmatter).


## Retro Formatting

When running retro and showing the `retro-table.sh` output:

- Show the script output ONCE, as-is
- Do NOT repeat it in a code block or reformat it
- Add notes and the prompt directly after the script output
