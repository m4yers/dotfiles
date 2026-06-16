# Retro

Track learnings worth encoding into skills, steering, or prompts. Default
stance: when the user asks for a fix, fix it. Do not preempt with a retro.

## When to write

Write a retro only when the lesson should outlive this session.

**Write when:**

- User corrects your behavior, defaults, or process — the lesson is
  behavioral and outlives any specific fix.
- User surfaces a factual error or wrong mental model you can't "fix in
  code" this turn.
- You discover a missing safety net, automated check, or process gap. Retro
  the gap, not the bug that exposed it.
- You discover a workflow pattern, skill improvement, or steering rule worth
  encoding for future sessions.
- You self-correct a tool-usage mistake whose root cause is a missing rule.
  Retro the rule, not the mistake.

**Do NOT write when:**

- User asked for a fix and you applied it this session.
- You found and fixed a bug mid-task without changing your understanding.
- The "lesson" is the specific bug or typo with no durable rule behind it.
- Routine task completion, things already in skills/steering, or transient
  details (ticket IDs, cluster names).

When in doubt, finish the request first. Decide at the end, when the
durability of the lesson is clear.

If you wrote a retro and the issue was then fixed in the same session,
delete the file from `~/.kiro/retro/pending/`.

## How to write

Use the writer script:

```bash
python3 ~/.kiro/skills/home/retro/scripts/write-retro-item.py \
  --dir ~/.kiro/retro/pending/ \
  --area <skill|steering|prompt> \
  --action <new|update> \
  --severity <high|medium|low> \
  --title "<title>" --detail "<detail>" \
  --evidence "<evidence>" [--target <name>]
```

Pick `area` by routing to where the rule belongs:

1. Existing skill covers it → `skill/update`, target = skill name
2. Existing steering file covers it → `steering/update`, target = file
3. Neither → `skill/new` or `steering/new`

After writing, append at the very end of your response:

```
[RETRO] Learnings so far: N
```

`N` is the file count in `~/.kiro/retro/pending/`. Omit the line if `N=0`.

Do NOT implement the change in the same response. The retro captures intent;
acting happens when the user runs `retro`.

## Formatting

Retro items that modify skill files MUST follow the conventions in
`~/.kiro/skills/home/dojo/references/conventions.md` (80-char prose, aligned
tables, single-line frontmatter).

When running `retro` and showing `retro-table.sh` output, show it once,
as-is. Do not reformat it as a markdown table.
