---
name: editor
description: Editor operations in the tiling EDITOR pane. Use when any skill needs to open files, show diffs, or navigate code. Use when the user says "view file", "edit file", "show file", "show diff", "open in editor". Builds on the tiling skill. Do NOT use for tiling operations — use tiling instead.
---

# editor

Opaque editor for the tiling EDITOR pane. Callers use
commands without knowing the underlying implementation.

Script: `~/.kiro/skills/util/editor/scripts/editor.py`

Run via:
```bash
uv run --python 3.12 \
  --project ~/.kiro/skills/util/editor/scripts \
  python ~/.kiro/skills/util/editor/scripts/editor.py \
  <command> [args]
```


## Dependencies

- `~/.kiro/skills/util/tiling/SKILL.md` — pane management

## API

| Command                  | Effect                              |
|--------------------------|-------------------------------------|
| `reset`                  | Clear all tabs, buffers, splits     |
| `show diff <file> <ref>` | Side-by-side diff (reuses tab)     |
| `show file <file>`       | Open file (reuses tab)              |
| `show only <file>`       | Reset editor and show single file   |
| `list tabs`              | List open tabs as JSON              |

## Commands

### reset

Clear all tabs, splits, and buffers. Returns the editor
to a clean single-buffer state.

```bash
~/.kiro/skills/util/editor/scripts/run-editor.sh reset
```

### show diff

Open a file with a side-by-side diff against a ref
(branch, tag, or revision like `HEAD`, `HEAD~1`, `rc`).

```bash
~/.kiro/skills/util/editor/scripts/run-editor.sh show diff src/main.cpp rc
~/.kiro/skills/util/editor/scripts/run-editor.sh show diff src/query.cpp HEAD~1
```

Each call reuses the tab if the file is already open,
otherwise opens a new tab.

### show file

Open a file in a tab. Reuses existing tab if the file
is already open.

```bash
~/.kiro/skills/util/editor/scripts/run-editor.sh show file src/main.cpp
```

### show only

Reset the editor and show a single file. Equivalent to
`reset` followed by `show file`.

```bash
~/.kiro/skills/util/editor/scripts/run-editor.sh show only src/main.cpp
```

### list tabs

List all open tabs with their splits and file names.

```bash
~/.kiro/skills/util/editor/scripts/run-editor.sh list tabs
```

Returns JSON array of tabs:

```json
[
  {
    "tab": 1,
    "panes": [
      {"file": "src/main.cpp", "active": true}
    ]
  }
]
```

## Rules

- MUST call `reset` before starting a new review or
  workflow to avoid stale tabs from a previous session.
- MUST NOT send raw keystrokes to the EDITOR pane — use
  the commands above.

**Constraints:**
- You MUST log activation at the start of the first
  workflow step:
  ```bash
  ~/.kiro/skills/util/skill-analytics/scripts/add-invocation.sh \
    editor TYPE:NAME  # e.g. user:alice, skill:cr-review
  ```

## Completion

| Status               | Criteria                            |
|----------------------|-------------------------------------|
| `DONE`               | File or diff shown in editor        |
| `DONE_WITH_CONCERNS` | Editor opened but diff unavailable  |
| `BLOCKED`            | Standard layout not set up          |
| `NEEDS_CONTEXT`      | No file specified to open           |
