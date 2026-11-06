# AGENTS.md

Instructions for coding agents working in this repo. Humans: see
`README.md`. Detailed references live in `docs/`, helper scripts in
`scripts/`.

## Project overview

Bash-based dotfiles installer. The repo is a set of **targets**, one
directory per tool under `targets/`. Each target has an `install.sh` that
installs packages, symlinks config files into `$HOME`, and appends shell
setup to `~/.config/dotfiles/<target>`, which `~/.bashrc` sources.

No build step, no test suite, no Node tooling. Bash plus a few Python
helper scripts.

## Repo family

`~/dotfiles` is the main repo and owns `scripts/shared.sh`. Extension
repos are siblings matching `~/dotfiles-*` (e.g. `~/dotfiles-hidden`) with
the same `targets/` layout and their own root `install.sh`; they source
this repo's `shared.sh`. Discover them with `ls -d ~/dotfiles-*`.

## Layout

```
install.sh              root installer: picks targets by OS and profile
scripts/shared.sh       helper library sourced by every target install.sh
scripts/dotfiles-*.py   agent helpers (list, show, create, review, ...)
docs/                   shared.sh API, target templates, review checks
targets/<name>/         one target: install.sh + bashrc.*.sh + config files
targets/scripts/export/ scripts on PATH (git-kiro-commit, git-pull-dotfiles)
targets/kiro/           Kiro skills/steering/agents/settings, linked into ~/.kiro
```

## References

- `docs/shared-api.md` — every helper in `scripts/shared.sh`.
- `docs/templates.md` — `install.sh` templates for main and
  extension repos, common `bashrc.*.sh` files.
- `docs/review-checks.md` — checklist for reviewing a target
  or the whole repo.

Read the relevant reference before writing or reviewing a target.

## Helper scripts

```bash
python3 scripts/dotfiles-list.py                      # targets + profiles, all repos
python3 scripts/dotfiles-show.py <target> [repo]      # what a target does
python3 scripts/dotfiles-search.py <query>            # grep all repos
python3 scripts/dotfiles-status.py                    # git status, all repos
python3 scripts/dotfiles-create.py <name> <main|ext>  # scaffold a target
python3 scripts/dotfiles-install.py <scope> [--profile home|work]
python3 scripts/dotfiles-commit.py [repo] [--push]    # git-kiro-commit per dirty repo
python3 scripts/dotfiles-review.py <target|all>       # kiro-cli review using review-checks.md
```

After `dotfiles-create.py`, register the target in the repo's root
`install.sh` array, otherwise it is never installed.

## Rules

- Follow `docs/templates.md` for new `install.sh`; use
  `local this=$(get_source)`, `ln -s -f $this/... $HOME/...`, and keep the
  `if ! is_sourced; then install; fi` guard.
- Package commands must match their OS branch: `brew`/`is_mac`,
  `apt`/`is_ubuntu`, `yum`/`is_centos`.
- Run the review checklist on any target you add or change.
- Installers mutate `$HOME` (root `install.sh` overwrites `~/.bashrc`,
  `targets/kiro/install.sh` wipes `~/.kiro`, `ln -s -f` replaces files).
  Ask before running any installer.
- `shared.sh` belongs to this repo; extensions must not copy it.
- `targets/kiro/` is symlinked into `~/.kiro`; edits there are live. Kiro
  skill authoring is handled by the `dojo` skill, not this repo's docs.
- No Node.js tooling. Bash, two-space indent, `#!/usr/bin/env bash`.
- Commit with `git-kiro-commit [--push]` (or `git-kiro-commit-dotfiles`
  across all repos). Check `git status` in every `~/dotfiles*`.
