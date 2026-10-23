---
name: editor
type: interface
description: Editor operations in the tiling EDITOR pane. Use when any skill needs to open files, show diffs, or navigate code. Use when the user says "view file", "edit file", "show file", "show diff", "open in editor". Builds on the tiling skill. Do NOT use for tiling operations — use tiling instead.
---

# editor

Opaque editor API for the tiling EDITOR pane, built on the tiling skill. Callers
invoke named commands to open files, show diffs, and manage tabs without knowing
the underlying implementation.

Callers MUST call `reset` before starting a new review or workflow so stale tabs
from previous sessions do not persist.

## Invocation

```bash
EDITOR=~/.kiro/skills/home/editor/scripts/run-editor.sh
$EDITOR <command> [args]
```

## API

| Command     | Args           | Effect                            |
|-------------|----------------|-----------------------------------|
| `reset`     | (none)         | Clear all tabs, buffers, splits   |
| `show diff` | `<file> <ref>` | Side-by-side diff against a ref   |
| `show file` | `<file>`       | Open file (reuses tab)            |
| `show only` | `<file>`       | Reset editor and show single file |
| `list tabs` | (none)         | List open tabs as JSON            |

## Commands

### reset

Clear all tabs, splits, and buffers. Returns the editor to a clean single-buffer
state so a new workflow starts without leftover tabs.

```bash
$EDITOR reset
```

### show diff

Show a side-by-side diff of a file against a ref (a branch, tag, or revision
like `HEAD`, `HEAD~1`, or `rc`).

```bash
$EDITOR show diff src/main.cpp rc
$EDITOR show diff src/query.cpp HEAD~1
```

`<file>` may be a directory, in which case every changed file under it is
shown. The pane stays on the diff; `n` / `N` move between files, `q` closes it.

### show file

Open a file in a tab. Reuses an existing tab when the file is already open;
otherwise opens the file in a new tab.

```bash
$EDITOR show file src/main.cpp
```

### show only

Reset the editor and show a single file in it. Equivalent to running `reset` and
then `show file` back-to-back.

```bash
$EDITOR show only src/main.cpp
```

### list tabs

List all open tabs with their splits and open file names.

```bash
$EDITOR list tabs
```

Returns a JSON array of tabs with the open panes in each tab:

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

- MUST NOT send raw keystrokes to the EDITOR pane because it bypasses the
  command API and breaks tab tracking.

## Completion

| Status               | Criteria                           |
|----------------------|------------------------------------|
| `DONE`               | File or diff shown in editor       |
| `DONE_WITH_CONCERNS` | Editor opened but diff unavailable |
| `BLOCKED`            | Standard layout not set up         |
| `NEEDS_CONTEXT`      | No file specified to open          |

- You MUST stop after 3 failed editor operations and report
  status BLOCKED with what was tried.
