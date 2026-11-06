#!/usr/bin/env python3
"""Show what a dotfile target does: packages, symlinks, configs."""
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


def find_target(name, repo_filter=None):
    repos = discover_repos()
    if repo_filter:
        if repo_filter == "main":
            repos = [MAIN]
        else:
            repos = [
                r for r in repos
                if os.path.basename(r) == "dotfiles-" + repo_filter
                or os.path.basename(r) == repo_filter
            ]
    for repo in repos:
        path = os.path.join(repo, "targets", name)
        if os.path.isdir(path):
            return repo, path
    return None, None


def analyze_install(install_path):
    """Parse install.sh for packages, symlinks, and bash configs."""
    with open(install_path) as f:
        text = f.read()

    packages = {"brew": [], "apt": [], "yum": []}
    symlinks = []
    bash_sources = []
    bash_exports = []
    bash_paths = []
    dir_links = []
    other_actions = []

    for line in text.split("\n"):
        s = line.strip()

        # Package installs
        m = re.match(r'brew install (.+)', s)
        if m:
            packages["brew"].append(m.group(1))
        m = re.match(r'sudo apt install (.+)', s)
        if m:
            packages["apt"].append(m.group(1))
        m = re.match(r'sudo yum install (.+)', s)
        if m:
            packages["yum"].append(m.group(1))

        # Symlinks (ln -s -f)
        m = re.match(r'ln -s -f\s+(\S+)\s+(\S+)', s)
        if m:
            src, dst = m.group(1), m.group(2)
            symlinks.append((src, dst))

        # bash_export_source
        m = re.match(r'bash_export_source\s+"?([^"]+)"?', s)
        if m:
            bash_sources.append(m.group(1))

        # bash_export_source_maybe
        m = re.match(r'bash_export_source_maybe\s+"?([^"]+)"?', s)
        if m:
            bash_sources.append(m.group(1) + " (if exists)")

        # bash_export_global
        m = re.match(r'bash_export_global\s+(\S+)\s+(.+)', s)
        if m:
            bash_exports.append("{}={}".format(m.group(1), m.group(2)))

        # bash_export_path
        m = re.match(r'bash_export_path\s+"?([^"]+)"?', s)
        if m:
            bash_paths.append(m.group(1))

        # link_config_dir
        m = re.match(r'link_config_dir\s+(\S+)', s)
        if m:
            dir_links.append(m.group(1))

        # git clone
        m = re.match(r'git clone\s+(\S+)', s)
        if m:
            other_actions.append("Clone: " + m.group(1))

        # toolbox install
        m = re.match(r'toolbox install\s+(\S+)', s)
        if m:
            other_actions.append("Toolbox: " + m.group(1))

    return {
        "packages": packages,
        "symlinks": symlinks,
        "bash_sources": bash_sources,
        "bash_exports": bash_exports,
        "bash_paths": bash_paths,
        "dir_links": dir_links,
        "other": other_actions,
    }


def list_config_files(target_dir):
    """List non-install.sh files in the target directory."""
    files = []
    for entry in sorted(os.listdir(target_dir)):
        path = os.path.join(target_dir, entry)
        if os.path.isfile(path) and entry != "install.sh":
            files.append(entry)
    return files


def main():
    parser = argparse.ArgumentParser(
        description="Show what a dotfile target does"
    )
    parser.add_argument("target", help="Target name")
    parser.add_argument("repo", nargs="?", help="Repo filter")
    args = parser.parse_args()

    name = args.target
    repo_filter = args.repo

    repo, target_dir = find_target(name, repo_filter)
    if not target_dir:
        print("Target '{}' not found".format(name), file=sys.stderr)
        sys.exit(1)

    short_repo = "~/{}".format(os.path.basename(repo))
    print("Target: {} ({})".format(name, short_repo))

    install_path = os.path.join(target_dir, "install.sh")
    if not os.path.isfile(install_path):
        print("  No install.sh found")
        return

    info = analyze_install(install_path)

    # Packages
    all_pkgs = []
    for mgr, pkgs in info["packages"].items():
        for p in pkgs:
            all_pkgs.append("{} ({})".format(p, mgr))
    if all_pkgs:
        print("Packages: {}".format(", ".join(all_pkgs)))

    # Symlinks
    for src, dst in info["symlinks"]:
        print("Symlink: {} -> {}".format(src, dst))

    # Directory links
    for d in info["dir_links"]:
        print("Dir link: {} -> ~/.kiro/{}".format(d, d))

    # Bash config
    if info["bash_sources"] or info["bash_exports"] or info["bash_paths"]:
        print("Bash config: ~/.config/dotfiles/{}".format(name))
        for s in info["bash_sources"]:
            print("  Source: {}".format(s))
        for e in info["bash_exports"]:
            print("  Export: {}".format(e))
        for p in info["bash_paths"]:
            print("  PATH: {}".format(p))

    # Other actions
    for a in info["other"]:
        print("Action: {}".format(a))

    # Config files
    configs = list_config_files(target_dir)
    if configs:
        print("Files: {}".format(", ".join(configs)))


if __name__ == "__main__":
    main()
