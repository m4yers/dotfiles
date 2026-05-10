---
name: obsidian
type: reference
description: Obsidian-flavored markdown formatting. Use when writing or editing markdown files destined for an Obsidian vault.
---

# Obsidian Markdown

Before writing any markdown file to an Obsidian vault, read
`references/obsidian-markdown.md` for the full
Obsidian-flavored markdown spec covering wikilinks, callouts,
frontmatter, tags, and formatting conventions.


**Constraints:**
- You MUST log activation at the start of the first
  workflow step:
  ```bash
  ~/.kiro/skills/home/skill-analytics/scripts/add-invocation.sh \
    obsidian TRIGGER_TYPE:TRIGGER_NAME  # e.g. user:alice, skill:cr-review
  ```

## Completion

| Status               | Criteria                            |
|----------------------|-------------------------------------|
| `DONE`               | Markdown written in Obsidian format |
| `DONE_WITH_CONCERNS` | Written but some formatting unclear |
| `BLOCKED`            | Cannot read reference file          |
| `NEEDS_CONTEXT`      | Target file not specified           |
