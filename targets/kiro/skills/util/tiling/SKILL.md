---
name: tiling
description: Tiling window manager. Exposes a script API for creating panes, sending input, reading output, and managing layouts. Use when any skill needs pane operations. Do NOT use for editor operations — use editor instead.
---

# tiling

Pane-centric tiling manager. All commands operate on panes
within the current window — no window concept is exposed
to callers. Panes are identified by stable IDs (`%NNN`).

The standard layout defines three named panes:
- `KIRO` — the kiro-cli pane (agent)
- `EDITOR` — large right pane for editor/diffs
- `CONSOLE` — small bottom-left pane for shell

## Invocation

```bash
~/.kiro/skills/util/tiling/scripts/run-ttm.sh \
  <group> <command> [options]
```


## API

### layout

| Command | Args   | Output                                      |
|---------|--------|---------------------------------------------|
| `build` | (none) | `KIRO=%id` `EDITOR=%id` `CONSOLE=%id`       |
| `check` | (none) | `KIRO=%id` `EDITOR=%id` `CONSOLE=%id` or exit 1 |
| `reset` | (none) | `KIRO=%id` (kills all other panes)          |

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

Create the standard 3-pane layout.

```bash
eval "$(~/.kiro/skills/util/tiling/scripts/run-ttm.sh layout build)"
# → KIRO=%42  EDITOR=%44  CONSOLE=%45
```

```
┌──────────┬───────────────┐
│ KIRO 37% │ EDITOR 63%    │
│ 90%h     │ 100%h         │
├──────────┤               │
│ CONSOLE  │               │
└──────────┴───────────────┘
```

### layout check

Verify the standard 3-pane layout exists.

```bash
eval "$(~/.kiro/skills/util/tiling/scripts/run-ttm.sh layout check)"
# → KIRO=%42  EDITOR=%44  CONSOLE=%45
```

Exits 0 with pane IDs if intact. Exits 1 with error
message if layout is wrong — caller decides what to do.

### layout reset

Kill all panes except the caller, returning to a single
pane.

```bash
eval "$(~/.kiro/skills/util/tiling/scripts/run-ttm.sh layout reset)"
# → KIRO=%42
```

### pane split

Create a new pane by splitting an existing one.

```bash
~/.kiro/skills/util/tiling/scripts/run-ttm.sh pane split -d right -s 63%
~/.kiro/skills/util/tiling/scripts/run-ttm.sh pane split -t %42 -d below -s 10%
```

- `-t PANE` — pane to split (default: current)
- `-d DIR` — `right` (default), `left`, `below`, `above`
- `-s SIZE` — percentage or line count (default: `50%`)

Prints the new pane's ID to stdout.

### pane write

Send keystrokes to a pane. Appends Enter by default.

```bash
~/.kiro/skills/util/tiling/scripts/run-ttm.sh pane write -t $EDITOR 'ls -la'
~/.kiro/skills/util/tiling/scripts/run-ttm.sh pane write -t $EDITOR -n 'partial input'
```

- `-t PANE` — target pane (required)
- `-n` — suppress trailing Enter
- `KEYS` — key sequence (positional)

### pane read

Read the visible content of a pane.

```bash
~/.kiro/skills/util/tiling/scripts/run-ttm.sh pane read -t $EDITOR
~/.kiro/skills/util/tiling/scripts/run-ttm.sh pane read -t $EDITOR -n 30
```

- `-t PANE` — target pane (required)
- `-n LINES` — lines from bottom (default: 15)

### pane list

List panes in the current window.

```bash
~/.kiro/skills/util/tiling/scripts/run-ttm.sh pane list
# %42: aim
# %44: vim
# %45: bash
```

### pane kill

Destroy a pane.

```bash
~/.kiro/skills/util/tiling/scripts/run-ttm.sh pane kill -t %44
```

- `-t PANE` — pane to kill (required)

### pane resize

Resize a pane by pushing its edge in a direction.

```bash
~/.kiro/skills/util/tiling/scripts/run-ttm.sh pane resize -t $EDITOR -d left -s 10
~/.kiro/skills/util/tiling/scripts/run-ttm.sh pane resize -t $CONSOLE -d up -s 3
```

- `-t PANE` — pane to resize (required)
- `-d DIR` — `up`, `down`, `left`, `right` (required)
- `-s SIZE` — lines or columns (default: 5)

### activity set

Set the activity label in the status bar. Skills call
this when starting work so the user sees what's active.

```bash
~/.kiro/skills/util/tiling/scripts/run-ttm.sh activity set "cr-review CR-12345"
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

**Constraints:**
- You MUST log activation at the start of the first
  workflow step:
  ```bash
  ~/.kiro/skills/util/skill-analytics/scripts/add-invocation.sh \
    tiling TYPE:NAME  # e.g. user:alice, skill:cr-review
  ```

## Completion

| Status               | Criteria                           |
|----------------------|------------------------------------|
| `DONE`               | Layout created, pane IDs captured  |
| `DONE_WITH_CONCERNS` | Partial layout (one split failed)  |
| `BLOCKED`            | Not in a tiling session            |
| `NEEDS_CONTEXT`      | Caller did not provide pane ID     |
