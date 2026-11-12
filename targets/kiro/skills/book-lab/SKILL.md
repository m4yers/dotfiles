---
name: book-lab
type: workflow
description: Initialises and maintains a git repo of worked coding examples for a book, one runnable experiment per chapter exercise. Use when working through a book chapter by chapter — reading a chapter to summarise it and propose coding examples, picking and implementing those examples, iterating on them, then moving to the next chapter. Triggers: "work through a book", "book lab", "read a chapter", "book examples", "next chapter", "start a book repo". Not for vault journals or live docs (use live-journal or live-doc instead).
---

# Book Lab

A book lab is a git repo of small, runnable coding experiments that work through
a book one chapter at a time. The user supplies the book; the agent reads a
chapter, proposes coding examples, implements the ones the user picks, and keeps
iterating until the user is satisfied before moving on to the next chapter. The
shim owns the repo — git, the `Part/Chapter` layout, and experiment scaffolding
— so the layout stays uniform and every change is committed.

## Dependencies

| Name     | Purpose                                      |
|----------|----------------------------------------------|
| `tiling` | activity label and pane layout               |

## Parameters

- **op** (required): `init` or `open`.
- **repo** (required): absolute path to the book-lab repo directory. `init`
  requires it to be empty or not yet a git repo; `open` requires an existing
  book-lab repo.
- **book**: path to the book source — a PDF, an EPUB, or a git repo /
  directory. Needed before reading a chapter; may be supplied at `open` or
  later.

## Aliases

```bash
BOOKLAB=~/.kiro/skills/home/book-lab/scripts/book-lab.sh
TILING=~/.kiro/skills/home/tiling/scripts/run-ttm.sh
```

Caller state: `BL_OP`, `BL_REPO`, `BL_BOOK`, `BL_CHAPTER` (the chapter being
worked, e.g. `PartI/Chapter2`). The `BL_` prefix keeps these from clobbering
another skill's shell variables. The shim exposes `init`, `status`, `scaffold`,
and `commit`; each is shown in context in the workflow steps below.

## Workflow

### Step 1: Setup

```bash
$TILING activity set "book-lab($BL_OP:$BL_REPO): Setup"
eval "$($TILING layout build)"
```

Proceed to Step 2.

### Step 2: Init or open

```bash
$TILING activity set "book-lab($BL_OP:$BL_REPO): Init or open"
```

- `op=init`: `$BOOKLAB init --repo "$BL_REPO"`. The shim git-inits the repo,
  writes `AGENTS.md`, and makes the first commit. Proceed to Step 4.
- `op=open`: `BL_SUMMARY=$($BOOKLAB status --repo "$BL_REPO")`. The shim prints
  a YAML summary (`parts[]` with `chapter` and `scripts`, plus `last_chapter`).
  Proceed to Step 3.

Non-zero exit → NEEDS_CONTEXT.

### Step 3: Resume summary (open only)

```bash
$TILING activity set "book-lab($BL_OP:$BL_REPO): Resume"
```

1. From `BL_SUMMARY`, tell the user briefly which chapters already have
   experiments and how many, naming them as `PartX/ChapterY`.
2. If `last_chapter` is set, ask whether to resume there or start a different
   chapter, then STOP and wait. Set `BL_CHAPTER` from the answer.

Proceed to Step 4.

### Step 4: Read a chapter

```bash
$TILING activity set "book-lab($BL_OP:$BL_REPO): Read $BL_CHAPTER"
```

1. Confirm `BL_BOOK`; ask for the book source if it is not yet set.
2. Extract the requested chapter's text following
   [references/reading-sources.md](references/reading-sources.md).
3. Print a brief summary of the chapter, then a numbered menu of candidate
   coding examples. STOP and wait for the user to pick.

Proceed to Step 5 once the user picks.

### Step 5: Implement and iterate

```bash
$TILING activity set "book-lab($BL_OP:$BL_REPO): Implement $BL_CHAPTER"
```

1. For each pick (from the menu or the user's own idea), scaffold a file:
   ```bash
   $BOOKLAB scaffold --repo "$BL_REPO" --part <P> --chapter <C> --name <slug>
   ```
2. Write the experiment into the scaffolded file, then let the user run it and
   give feedback; revise until the user is satisfied.
3. Commit the satisfied example:
   ```bash
   $BOOKLAB commit --repo "$BL_REPO" --message "<Part/Chapter>: <slug>"
   ```
4. On a next-chapter cue, set `BL_CHAPTER` and return to Step 4. Otherwise
   repeat from sub-step 1 for the next pick.

## Rules

1. git and the repo layout MUST be changed only through the shim, because
   raw git or hand-made folders drift from the layout the shim and `status`
   expect.
2. Each experiment MUST be one script in its chapter folder; a chapter with
   several experiments gets several files, because one-file-per-experiment
   keeps each runnable with a single `uv run`.
3. Experiment scripts MUST follow the repo `AGENTS.md` conventions: `uv` with
   PEP 723 inline dependencies, an `argparse` CLI with defaulted flags, and
   `rich` terminal output.
4. The chapter summary and example menu MUST be grounded in the extracted
   chapter text, because an invented summary misleads the user about what they
   read.
5. The agent MUST implement only what the user picked and MUST NOT add extra
   scripts, abstractions, or defensive layers, because uncommanded additions
   inflate the repo and the review.
6. After 3 consecutive shim failures, stop and report BLOCKED with the attempted
   commands.

## Completion

| Status               | Criteria                                                        |
|----------------------|-----------------------------------------------------------------|
| `DONE`               | Picked examples implemented, run by the user, and committed     |
| `DONE_WITH_CONCERNS` | Examples committed, but a source chapter could not be extracted |
| `BLOCKED`            | 3 consecutive shim failures                                     |
| `NEEDS_CONTEXT`      | shim rejected `op`/`repo`, or the book source is missing        |
