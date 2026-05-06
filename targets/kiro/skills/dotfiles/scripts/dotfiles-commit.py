#!/usr/bin/env python3
"""Commit and push changes across dotfile repos using git-kiro-commit."""
import argparse
import os
import subprocess
import sys

HOME = os.path.expanduser("~")
MAIN = os.path.join(HOME, "dotfiles")
GIT_KIRO = os.path.join(
    HOME, "dotfiles/targets/scripts/export/git-kiro-commit"
)


def discover_repos():
    repos = []
    if os.path.isdir(MAIN):
        repos.append(MAIN)
    for entry in sorted(os.listdir(HOME)):
        path = os.path.join(HOME, entry)
        if entry.startswith("dotfiles-") and os.path.isdir(path):
            repos.append(path)
    return repos


def is_dirty(repo):
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo, capture_output=True, text=True,
    )
    return bool(r.stdout.strip())


def main():
    parser = argparse.ArgumentParser(
        description="Commit and push dotfile changes"
    )
    parser.add_argument(
        "repo", nargs="?", default="all",
        help="Repo: 'main', extension name, or 'all' (default)",
    )
    parser.add_argument(
        "--push", action="store_true",
        help="Push after committing",
    )
    args = parser.parse_args()

    repos = discover_repos()

    if args.repo != "all":
        if args.repo == "main":
            repos = [MAIN]
        else:
            repos = [
                r for r in repos
                if os.path.basename(r) == "dotfiles-" + args.repo
                or os.path.basename(r) == args.repo
            ]
            if not repos:
                print(
                    "Repo '{}' not found".format(args.repo),
                    file=sys.stderr,
                )
                sys.exit(1)

    dirty = [r for r in repos if is_dirty(r)]
    if not dirty:
        print("All repos clean, nothing to commit.")
        sys.exit(0)

    for repo in dirty:
        short = "~/{}".format(os.path.basename(repo))
        print("\n=== {} ===".format(short))
        cmd = [GIT_KIRO]
        if args.push:
            cmd.append("--push")
        subprocess.run(cmd, cwd=repo)


if __name__ == "__main__":
    main()
