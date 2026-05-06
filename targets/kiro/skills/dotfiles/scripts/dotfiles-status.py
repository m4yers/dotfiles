#!/usr/bin/env python3
"""Show git status across all dotfile repos."""
import os
import subprocess
import sys

HOME = os.path.expanduser("~")
MAIN = os.path.join(HOME, "dotfiles")


def discover_repos():
    repos = []
    if os.path.isdir(MAIN):
        repos.append(MAIN)
    for entry in sorted(os.listdir(HOME)):
        path = os.path.join(HOME, entry)
        if entry.startswith("dotfiles-") and os.path.isdir(path):
            repos.append(path)
    return repos


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip()


def main():
    repos = discover_repos()
    if not repos:
        print("No dotfile repos found", file=sys.stderr)
        sys.exit(1)

    any_output = False
    for repo in repos:
        if not os.path.isdir(os.path.join(repo, ".git")):
            continue

        short = "~/{}".format(os.path.basename(repo))
        status = run(["git", "status", "--short"], repo)
        unpushed = run(
            ["git", "log", "@{u}..", "--oneline"], repo
        )

        if status or unpushed:
            any_output = True
            print("{}".format(short))
            if status:
                for line in status.split("\n"):
                    print("  {}".format(line))
            if unpushed:
                print("  Unpushed:")
                for line in unpushed.split("\n"):
                    print("    {}".format(line))
            print()

    if not any_output:
        print("All repos clean")


if __name__ == "__main__":
    main()
