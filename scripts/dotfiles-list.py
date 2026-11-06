#!/usr/bin/env python3
"""List all dotfile targets across repos with profile membership."""
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


def parse_profiles(repo):
    """Extract target-to-profile mappings from repo's install.sh."""
    install = os.path.join(repo, "install.sh")
    if not os.path.isfile(install):
        return {}
    with open(install) as f:
        text = f.read()

    # Match patterns like:
    #   declare -a targets=("bash" "git" "tmux")
    #   targets+=("kiro")
    # Track which function/context they appear in for profile labeling.
    target_profiles = {}

    # Find all target array declarations with context
    lines = text.split("\n")
    current_context = "all"
    for line in lines:
        stripped = line.strip()

        # Track if/function context for profile detection
        if re.match(r'if\s+is_linux', stripped):
            current_context = "linux"
        elif re.match(r'if\s+is_mac', stripped):
            current_context = "mac"
        elif re.match(r'if\s+\[\[\s+"\$PROFILE"\s*==\s*"(\w+)"', stripped):
            m = re.match(
                r'if\s+\[\[\s+"\$PROFILE"\s*==\s*"(\w+)"', stripped
            )
            current_context = m.group(1)
        elif stripped == "fi":
            current_context = "all"

        # Match declare -a targets=(...) or targets+=(...)
        m = re.search(r'targets[+]?=\(([^)]*)\)', stripped)
        if m:
            names = re.findall(r'"([^"]+)"', m.group(1))
            for name in names:
                target_profiles.setdefault(name, set()).add(
                    current_context
                )

    return target_profiles


def list_targets(repos):
    rows = []
    for repo in repos:
        targets_dir = os.path.join(repo, "targets")
        if not os.path.isdir(targets_dir):
            continue
        profiles = parse_profiles(repo)
        short = "~/{}".format(os.path.basename(repo))
        for entry in sorted(os.listdir(targets_dir)):
            path = os.path.join(targets_dir, entry)
            if os.path.isdir(path) and not entry.startswith("."):
                profs = profiles.get(entry, set())
                prof_str = ", ".join(sorted(profs)) if profs else "-"
                rows.append((short, entry, prof_str))
    return rows


def main():
    repos = discover_repos()
    if not repos:
        print("No dotfile repos found", file=sys.stderr)
        sys.exit(1)

    rows = list_targets(repos)

    # Column widths
    w_repo = max(len(r[0]) for r in rows) if rows else 4
    w_target = max(len(r[1]) for r in rows) if rows else 6
    w_repo = max(w_repo, 4)
    w_target = max(w_target, 6)

    fmt = "{:<{rw}}  {:<{tw}}  {}"
    print(fmt.format("REPO", "TARGET", "PROFILES",
                      rw=w_repo, tw=w_target))
    for repo, target, profiles in rows:
        print(fmt.format(repo, target, profiles,
                          rw=w_repo, tw=w_target))


if __name__ == "__main__":
    main()
