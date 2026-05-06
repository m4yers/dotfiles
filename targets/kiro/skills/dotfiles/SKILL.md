---
name: dotfiles
type: interface
description: Manage dotfiles across ~/dotfiles (main) and ~/dotfiles-* (extensions). Use when the user says "dotfiles", "create target", "install target", "dotfiles status", "dotfiles commit", "review target", or wants to manage dotfile targets and profiles. Do NOT use for Kiro skill management — use skill-builder instead.
---

# Dotfiles

Manage dotfile targets across a main repo and optional
extension repos:

| Repo              | Role       | Shared lib                  |
|-------------------|------------|-----------------------------|
| `~/dotfiles`      | Main       | `scripts/shared.sh` (owner) |
| `~/dotfiles-*`    | Extensions | Source main's shared.sh     |

`~/dotfiles` is required. Extension repos are any
directories matching `~/dotfiles-*` (e.g.,
`~/dotfiles-hidden`, `~/dotfiles-work`). All scripts
discover them dynamically.

Each repo has `targets/` containing named target
directories. Each target has an `install.sh` that uses
helpers from `shared.sh`. The main `install.sh` at the
repo root selects which targets to install based on OS
and profile.

Target install scripts follow these patterns:
- Bash config: `bash_init_config` + `bash_export_source`
  → `~/.config/dotfiles/<target>` sourced from `~/.bashrc`
- Symlinks: `ln -s -f` for config files to `$HOME`
- Directory links: `ln -s -f` for directory trees
- Package install: OS-specific via brew/apt/yum
- Combinations of the above

See `references/shared-api.md` for the full shared.sh
helper API. See `references/templates.md` for target
scaffolding templates.

## Activation

```bash
~/.kiro/skills/home/skill-analytics/scripts/add-invocation.sh \
  dotfiles TRIGGER_TYPE:TRIGGER_NAME
```

## Invocation

```bash
python3 ~/.kiro/skills/home/dotfiles/scripts/dotfiles-<cmd>.py \
  [args]
```

All commands are scripts. `review` delegates to
`kiro-cli` with Opus 4.6 for deep analysis.

## API

| Command   | Args                  | Output                     |
|-----------|-----------------------|----------------------------|
| `list`    | —                     | Target table with profiles |
| `create`  | name, repo            | Scaffolded target dir      |
| `show`    | target, [repo]        | Target summary             |
| `status`  | —                     | Git status all repos       |
| `search`  | query                 | Grep matches with context  |
| `install` | scope, [--profile X]  | Installer output           |
| `commit`  | [repo], [--push]      | Commit + push              |
| `review`  | scope                 | Review report              |

## Commands

### list

```bash
python3 ~/.kiro/skills/home/dotfiles/scripts/dotfiles-list.py
```

Shows all targets across all repos with profile
membership parsed from each repo's `install.sh`.

### create

```bash
python3 ~/.kiro/skills/home/dotfiles/scripts/dotfiles-create.py \
  <name> <repo>
```

- **name**: target directory name
- **repo**: `main` or extension name (e.g., `hidden`)

Scaffolds `install.sh` and `bashrc.aliases.sh` using
the correct template for main vs extension repos. After
running, register the target in the repo's `install.sh`
target array and add any additional config files based
on the target's purpose.

### show

```bash
python3 ~/.kiro/skills/home/dotfiles/scripts/dotfiles-show.py \
  <target> [repo]
```

Parses install.sh to show packages, symlinks, directory
links, bash config sources/exports, and other actions.

### status

```bash
python3 ~/.kiro/skills/home/dotfiles/scripts/dotfiles-status.py
```

Shows git status and unpushed commits across all repos.

### search

```bash
python3 ~/.kiro/skills/home/dotfiles/scripts/dotfiles-search.py \
  <query>
```

Greps across all target directories in all repos.
Case-insensitive substring match.

### install

```bash
python3 ~/.kiro/skills/home/dotfiles/scripts/dotfiles-install.py \
  <target|repo|all> [--profile home|work]
```

- **scope**: target name, repo name (`main`, `hidden`,
  etc.), or `all`
- **--profile**: `home` or `work` — passed to main repo's
  installer

Confirms before running. For a single target, runs its
`install.sh` directly. For a repo or `all`, runs the
repo-level `install.sh`.

### commit

```bash
python3 ~/.kiro/skills/home/dotfiles/scripts/dotfiles-commit.py \
  [repo] [--push]
```

- **repo** (optional): `main`, extension name, or `all`
  (default) — auto-detects dirty repos
- **--push**: also push after committing

Uses `git-kiro-commit` from
`~/dotfiles/targets/scripts/export/` to stage changes,
generate a commit message via `kiro-cli`, show it for
confirmation, and commit. Runs per dirty repo
sequentially.

### review

```bash
python3 ~/.kiro/skills/home/dotfiles/scripts/dotfiles-review.py \
  <target|all>
```

- **scope**: target name or `all`

Collects all target files and repo installers, builds a
prompt with the checks from `references/review-checks.md`,
and sends it to `kiro-cli` using Opus 4.6 with an
ultrathink directive. Single target runs single-target
checks; `all` runs both single-target and global checks.

See `references/review-checks.md` for the full check
list.

## Completion

| Status               | Criteria                             |
|----------------------|--------------------------------------|
| `DONE`               | Operation completed, output shown    |
| `DONE_WITH_CONCERNS` | Completed but review found issues    |
| `BLOCKED`            | Repo not found or git errors         |
| `NEEDS_CONTEXT`      | Target name or repo not specified    |
