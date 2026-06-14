---
name: tiling
type: interface
description: Tiling window manager. Exposes a script API for creating panes, sending input, reading output, and managing layouts. Use when any skill needs pane operations. Do NOT use for editor operations — use editor instead.
---

# tiling

Pane-centric tiling manager. All commands operate on panes
within the current window — no window concept is exposed
to callers. Panes are identified by stable IDs (`%NNN`).

The standard layout defines two named panes:
- `KIRO` — the kiro-cli pane (agent)
- `EDITOR` — left pane for editor/diffs

## Invocation

```bash
~/.kiro/skills/home/tiling/scripts/run-ttm.sh \
  <group> <command> [options]
```

## API

### layout

| Command | Args   | Output                            |
|---------|--------|-----------------------------------|
| `build` | (none) | —                                 |
| `check` | (none) | — (exit 1 if layout incorrect)    |
| `reset` | (none) | —                                 |

### pane

| Command   | Args                                              | Output              |
|-----------|---------------------------------------------------|---------------------|
| `split`   | `[-t PANE] [-d right\|left\|below\|above] [-s SIZE]` | new pane ID     |
| `write`   | `-t PANE [-n] KEYS`                               | —                   |
| `read`    | `-t PANE [-n LINES]`                               | pane content        |
| `list`    | (none)                                             | `%id: cmd` per line |
| `kill`    | `-t PANE`                                          | —                   |
| `resize`  | `-t PANE -d up\|down\|left\|right [-s SIZE]`       | —                   |

### activity

| Command | Args    | Output |
|---------|---------|--------|
| `set`   | `LABEL` | —      |

## Commands

### layout build

Create the standard 2-pane layout. Idempotent — exits
silently if the layout already exists.

```bash
~/.kiro/skills/home/tiling/scripts/run-ttm.sh layout build
```

```
┌───────────┬───────────┐
│ EDITOR    │ KIRO      │
│ 50%       │ 50%       │
└───────────┴───────────┘
```

### layout check

Verify the standard 2-pane layout exists.

```bash
~/.kiro/skills/home/tiling/scripts/run-ttm.sh layout check
```

Exits 0 if intact. Exits 1 with error message if layout
is wrong — caller decides what to do.

### layout reset

Kill all panes except the caller, returning to a single
pane.

```bash
~/.kiro/skills/home/tiling/scripts/run-ttm.sh layout reset
```

### pane split

Create a new pane by splitting an existing one.

```bash
~/.kiro/skills/home/tiling/scripts/run-ttm.sh pane split -d right -s 63%
~/.kiro/skills/home/tiling/scripts/run-ttm.sh pane split -t %42 -d below -s 10%
```

- `-t PANE` — pane to split (default: current)
- `-d DIR` — `right` (default), `left`, `below`, `above`
- `-s SIZE` — percentage or line count (default: `50%`)

Prints the new pane's ID to stdout.

### pane write

Send keystrokes to a pane. Appends Enter by default.

```bash
~/.kiro/skills/home/tiling/scripts/run-ttm.sh pane write -t %44 'ls -la'
~/.kiro/skills/home/tiling/scripts/run-ttm.sh pane write -t %44 -n 'partial input'
```

- `-t PANE` — target pane (required)
- `-n` — suppress trailing Enter
- `KEYS` — key sequence (positional)

### pane read

Read the visible content of a pane.

```bash
~/.kiro/skills/home/tiling/scripts/run-ttm.sh pane read -t %44
~/.kiro/skills/home/tiling/scripts/run-ttm.sh pane read -t %44 -n 30
```

- `-t PANE` — target pane (required)
- `-n LINES` — lines from bottom (default: 15)

### pane list

List panes in the current window.

```bash
~/.kiro/skills/home/tiling/scripts/run-ttm.sh pane list
# %42: aim
# %44: vim
```

### pane kill

Destroy a pane.

```bash
~/.kiro/skills/home/tiling/scripts/run-ttm.sh pane kill -t %44
```

- `-t PANE` — pane to kill (required)

### pane resize

Resize a pane by pushing its edge in a direction.

```bash
~/.kiro/skills/home/tiling/scripts/run-ttm.sh pane resize -t %44 -d left -s 10
```

- `-t PANE` — pane to resize (required)
- `-d DIR` — `up`, `down`, `left`, `right` (required)
- `-s SIZE` — lines or columns (default: 5)

### activity set

Set the activity label in the status bar. Skills call
this when starting work so the user sees what's active.

```bash
~/.kiro/skills/home/tiling/scripts/run-ttm.sh activity set "cr-review CR-12345"
```

- `LABEL` — activity description (positional)

## Defaults

- `split` → right, 50%, current pane
- `read` → 15 lines
- `write` → appends Enter (`-n` to suppress)
- `resize` → 5 lines/columns

## Rules

- MUST verify a pane runs the expected command before
  sending keys — the process may have exited.
- SHOULD call `activity set` when starting a skill so
  the user sees what's happening.

## Completion

| Status               | Criteria                           |
|----------------------|------------------------------------|
| `DONE`               | Layout created, pane IDs captured  |
| `DONE_WITH_CONCERNS` | Partial layout (one split failed)  |
| `BLOCKED`            | Not in a tiling session            |
| `NEEDS_CONTEXT`      | Caller did not provide pane ID     |

- You MUST stop after 3 failed pane operations and report
  status BLOCKED with what was tried.
