---
name: live-journal
type: workflow
description: Creates or opens a live journal — an interactive markdown journal under `<vault>/work/live-journal/live-journal-<name>.md` with one H2 section per topic, H3 sub-sections per result, a `Status:` marker per topic, and an Appendix of scripts used. The agent keeps the journal updated during the conversation and commits the vault after every edit. Use when the user says "live journal", "new journal", "create journal", "open journal", "continue journal", "new topic", "next topic", "journal this", "update journal". Not for live docs or ordinary vault articles.
---

# Live Journal

A live journal is a vault markdown file the agent writes to while working with
the operator: one H2 per topic, H3 sub-sections for substantive results, a
`Status:` line per topic, and a trailing `## Appendix` for scripts used. The
shim owns the file format: every structural edit goes through it and each edit
commits the vault.

## Dependencies

| Name     | Purpose                            |
|----------|------------------------------------|
| `tiling` | activity label and pane layout     |
| `editor` | reset the EDITOR pane at setup     |

## Parameters

- **op** (required): `create` or `open`
- **path** (required): absolute path to
  `<vault>/work/live-journal/live-journal-<name>.md`; `create` requires it to
  not exist, `open` requires it to exist inside a git repo

## Aliases

```bash
LJ=~/.kiro/skills/home/live-journal/scripts/live-journal.sh
LJ_TILING=~/.kiro/skills/home/tiling/scripts/run-ttm.sh
LJ_EDITOR=~/.kiro/skills/home/editor/scripts/run-editor.sh
```

Caller state: `LJ_OP`, `LJ_PATH`, `LJ_TOPIC` (title of the current topic).

## Workflow

### Step 1: Setup

```bash
$LJ_TILING activity set "live-journal($LJ_OP:$LJ_PATH): Setup"
eval "$($LJ_TILING layout build)"
$LJ_EDITOR reset
```

Proceed to Step 2.

### Step 2: Create or open

```bash
$LJ_TILING activity set "live-journal($LJ_OP:$LJ_PATH): Create or open"
```

- `op=create`: `$LJ create --path "$LJ_PATH"`. The shim opens the file in the
  editor. Proceed to Step 4.
- `op=open`: `LJ_SUMMARY=$($LJ open --path "$LJ_PATH")`. The shim opens the
  file and prints a YAML summary (`topic_count`, `topics[]` with
  `title`/`status`/`subsection_count`, `last_incomplete_topic`,
  `appendix_script_count`). Proceed to Step 3.

Non-zero exit → NEEDS_CONTEXT.

### Step 3: Summarise (open only)

Skip when `topic_count: 0`.

```bash
$LJ_TILING activity set "live-journal($LJ_OP:$LJ_PATH): Summarise"
```

1. From `LJ_SUMMARY` and the journal text, tell the operator briefly what the
   journal is about, how many topics it has, which are `done` and which are
   `in-progress`.
2. If `last_incomplete_topic` is set, ask whether to continue from it, then
   STOP and wait. On yes, set `LJ_TOPIC` to that title.

Proceed to Step 4.

### Step 4: Topic loop

```bash
$LJ_TILING activity set "live-journal($LJ_OP:$LJ_PATH): Topic loop"
```

Wait for the operator. On each message:

1. **Topic change** — only on an explicit cue ("new topic", "next topic",
   "move on to X"). Mark the current topic `done` unless the operator says it
   is abandoned or unfinished, then add the new one and set `LJ_TOPIC`:
   ```bash
   $LJ topic status --path "$LJ_PATH" --title "$LJ_TOPIC" --status done
   $LJ topic add --path "$LJ_PATH" --title "<next-title>"
   ```
   STOP and wait for the operator's input on the new topic.
2. **Journal update** — after an exchange or agent work that produced a
   substantial result, or on "journal this" / "update journal". Write the body
   to a temp file, then:
   ```bash
   $LJ section put --path "$LJ_PATH" --topic "$LJ_TOPIC" \
       --heading "<h3-heading>" --body "<body-file>"
   ```
   If a script was written or run for the result:
   ```bash
   $LJ appendix add --path "$LJ_PATH" --name "<script-name>" \
       --source "<source-file>"
   ```

Repeat until the operator closes the journal.

## Rules

1. Headings, status lines, and Appendix entries MUST be edited only through
   the shim; the agent authors prose inside sub-section bodies only.
2. The agent MUST NOT open a new topic without an explicit operator cue,
   because topic boundaries are the operator's decision.
3. The agent MUST NOT run `git` against the vault, because the shim already
   commits each edit.
4. Trivial chatter is not journaled; only substantial results or explicit
   cues trigger `section put` / `appendix add`.
5. After 3 consecutive shim failures, stop and report BLOCKED with the
   attempted calls.

## Completion

| Status               | Criteria                                      |
|----------------------|-----------------------------------------------|
| `DONE`               | operator closed the journal; vault committed  |
| `DONE_WITH_CONCERNS` | closed, but some topics left `in-progress`    |
| `BLOCKED`            | 3 consecutive shim failures                   |
| `NEEDS_CONTEXT`      | shim preflight rejected `op`/`path`           |
