#!/usr/bin/env python3
"""Search across all dotfile targets for a pattern."""
import argparse
import os
import re
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


def search_file(filepath, pattern, repo):
    matches = []
    try:
        with open(filepath) as f:
            for i, line in enumerate(f, 1):
                if pattern.search(line):
                    short_repo = "~/{}".format(os.path.basename(repo))
                    rel = os.path.relpath(filepath, repo)
                    matches.append((short_repo, rel, i, line.rstrip()))
    except (UnicodeDecodeError, PermissionError):
        pass
    return matches


def main():
    parser = argparse.ArgumentParser(
        description="Search across all dotfile targets"
    )
    parser.add_argument("query", help="Text to search for")
    args = parser.parse_args()

    query = args.query
    pattern = re.compile(re.escape(query), re.IGNORECASE)

    repos = discover_repos()
    results = []

    for repo in repos:
        targets_dir = os.path.join(repo, "targets")
        if not os.path.isdir(targets_dir):
            continue
        for root, dirs, files in os.walk(targets_dir):
            # Skip hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if fname.startswith("."):
                    continue
                filepath = os.path.join(root, fname)
                results.extend(search_file(filepath, pattern, repo))

    if not results:
        print("No matches for '{}'".format(query))
        sys.exit(0)

    for repo, rel, lineno, line in results:
        print("{}:{}:{}: {}".format(repo, rel, lineno, line))

    print("\n{} match(es)".format(len(results)))


if __name__ == "__main__":
    main()
