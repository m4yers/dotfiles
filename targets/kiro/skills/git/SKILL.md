---
name: git
type: interface
description: Git operations that enforce a base+staging two-commit invariant. Use when a workflow needs to stage pending changes on a single "staging" commit above a fixed base commit, amend into it, or squash it back. Commands are stage, amend, squash. Do NOT use for general git operations — call git directly. Do NOT use for review-system-specific flows — use the appropriate review skill instead.
---

# Git Interface

Enforces the invariant: between a fixed base commit and HEAD there is
**at most one "staging" commit**. `stage` fails if one already exists.
`amend` fails if none exists. `squash` folds the staging commit into the base.

All commands take `--base <ref>` identifying the base commit. The staging
commit, when present, is the single commit reachable from HEAD but not from
base — i.e., `base..HEAD` has exactly one entry.

## Invocation

```bash
~/.kiro/skills/home/git/scripts/git.py <command> --base <ref> [options]
```

Run from inside the target git repository.

## API

| Command  | Args                         | Output                                  |
|----------|------------------------------|-----------------------------------------|
| `stage`  | `--base <ref> -m <message>`  | new staging commit on top of base       |
| `amend`  | `--base <ref>`               | staging commit amended with staged tree |
| `squash` | `--base <ref> -m <message>`  | base rewritten with staging folded in   |
| `clear`  | `--base <ref>`               | staging commit discarded (hard reset)   |

Exit 0 on success, non-zero on invariant violation or git failure.

## Commands

### stage

Create a new staging commit on top of `--base`. Fails if `base..HEAD` is
non-empty (a staging commit already exists — use `amend` instead).

```bash
~/.kiro/skills/home/git/scripts/git.py stage --base HEAD -m "staging"
```

- `--base <ref>` — the base commit (required)
- `-m <message>` — commit message (required)

Runs `git add -u` before committing. No-op if nothing is staged.

### amend

Amend the single staging commit sitting directly on top of `--base`. Fails if
`base..HEAD` has zero or more than one commit.

```bash
~/.kiro/skills/home/git/scripts/git.py amend --base <base-sha>
```

- `--base <ref>` — the base commit (required)

Runs `git add -u` and `git commit --amend --no-edit`.

### squash

Squash the staging commit into the base, producing a single commit at HEAD
with the supplied message. Fails if `base..HEAD` has zero or more than one
commit.

```bash
~/.kiro/skills/home/git/scripts/git.py squash --base <base-sha> \
    -m "<final message>"
```

- `--base <ref>` — the base commit (required)
- `-m <message>` — final commit message for the squashed commit (required)

Runs `git reset --soft <base>` then `git commit --amend -m <message>`.

## Rules

- `--base` MUST resolve to an ancestor of HEAD. The wrapper verifies
  with `git merge-base --is-ancestor` and fails otherwise because
  operating on a non-ancestor would silently rewrite unrelated history.
- The invariant `len(base..HEAD) ∈ {0, 1}` is checked before every
  command. `stage` requires 0, `amend` and `squash` require exactly 1.
- Callers MUST log this skill's activation once per workflow step:
  ```bash
  ~/.kiro/skills/home/skill-analytics/scripts/add-invocation.sh \
    git TRIGGER_TYPE:TRIGGER_NAME  # e.g. user:alice, skill:cr-comments
  ```

## Completion

| Status          | Criteria                                    |
|-----------------|---------------------------------------------|
| `DONE`          | Command succeeded                           |
| `BLOCKED`       | Invariant violated or git returned non-zero |
| `NEEDS_CONTEXT` | `--base` not provided                       |
