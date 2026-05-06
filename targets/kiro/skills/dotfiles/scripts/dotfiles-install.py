#!/usr/bin/env python3
"""Run dotfile installers for a target, repo, or all."""
import argparse
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


def resolve_repo(name):
    if name == "main":
        return MAIN
    path = os.path.join(HOME, "dotfiles-" + name)
    if os.path.isdir(path):
        return path
    return None


def find_target(name):
    """Find which repo contains a target, return (repo, target_dir)."""
    for repo in discover_repos():
        path = os.path.join(repo, "targets", name)
        if os.path.isdir(path):
            return repo, path
    return None, None


def short(repo):
    return "~/{}".format(os.path.basename(repo))


def install_target(target_dir):
    script = os.path.join(target_dir, "install.sh")
    if not os.path.isfile(script):
        print("  No install.sh found, skipping")
        return
    subprocess.run(["bash", script])


def install_repo(repo, profile=None):
    script = os.path.join(repo, "install.sh")
    if not os.path.isfile(script):
        print("No install.sh in {}".format(short(repo)))
        return
    cmd = ["bash", script, "home"]
    if profile:
        cmd += ["--profile", profile]
    subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(
        description="Run dotfile installers"
    )
    parser.add_argument(
        "scope", help="Target name, repo name, or 'all'"
    )
    parser.add_argument(
        "--profile", choices=["home", "work"],
        help="Profile for main repo installer",
    )
    args = parser.parse_args()

    scope = args.scope
    profile = args.profile

    if scope == "all":
        repos = discover_repos()
        targets = []
        for repo in repos:
            td = os.path.join(repo, "targets")
            if os.path.isdir(td):
                for t in sorted(os.listdir(td)):
                    if os.path.isdir(os.path.join(td, t)) \
                            and not t.startswith("."):
                        targets.append((short(repo), t))
        print("Will install all repos:")
        for r in repos:
            print("  {}".format(short(r)))
        resp = input("Proceed? [Y/n] ")
        if resp.strip().lower() not in ("", "y", "yes"):
            print("Aborted.")
            sys.exit(0)
        for repo in repos:
            print("\n=== {} ===".format(short(repo)))
            install_repo(repo, profile)
        return

    # Try as repo name
    repo = resolve_repo(scope)
    if repo:
        print("Will install {}".format(short(repo)))
        resp = input("Proceed? [Y/n] ")
        if resp.strip().lower() not in ("", "y", "yes"):
            print("Aborted.")
            sys.exit(0)
        install_repo(repo, profile)
        return

    # Try as target name
    repo, target_dir = find_target(scope)
    if target_dir:
        print("Will install target '{}' from {}".format(
            scope, short(repo)
        ))
        resp = input("Proceed? [Y/n] ")
        if resp.strip().lower() not in ("", "y", "yes"):
            print("Aborted.")
            sys.exit(0)
        install_target(target_dir)
        return

    print("'{}' not found as target or repo".format(scope),
          file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
