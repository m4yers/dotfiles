#!/usr/bin/env python3
"""git.py — enforce base+staging two-commit invariant.

Commands:
  stage  --base <ref> -m <msg> [--repo <path>]  new staging commit
  amend  --base <ref>          [--repo <path>]  amend the staging commit
  squash --base <ref> -m <msg> [--repo <path>]  squash staging into base
  clear  --base <ref>          [--repo <path>]  drop staging + changes

Invariant: base..HEAD contains 0 or 1 commits.
  stage requires 0 (no staging yet).
  amend/squash/clear require 1 (exactly one staging).

--repo sets the working dir for every git call. Defaults to CWD.
"""
import argparse
import subprocess
import sys


def run(*cmd, check=True, capture=False, cwd=None):
    return subprocess.run(
        cmd, check=check, text=True,
        capture_output=capture, cwd=cwd,
    )


def resolve(ref, cwd=None):
    """Resolve ref to a full sha, or exit with error."""
    r = run("git", "rev-parse", "--verify", f"{ref}^{{commit}}",
            check=False, capture=True, cwd=cwd)
    if r.returncode != 0:
        sys.exit(f"ERROR: cannot resolve ref: {ref}")
    return r.stdout.strip()


def staging_count(base_sha, cwd=None):
    """Return number of commits in base..HEAD."""
    r = run("git", "rev-list", "--count", f"{base_sha}..HEAD",
            capture=True, cwd=cwd)
    return int(r.stdout.strip())


def require_ancestor(base_sha, cwd=None):
    r = run("git", "merge-base", "--is-ancestor", base_sha, "HEAD",
            check=False, cwd=cwd)
    if r.returncode != 0:
        sys.exit(f"ERROR: {base_sha} is not an ancestor of HEAD")


def cmd_stage(args):
    cwd = args.repo
    base = resolve(args.base, cwd=cwd)
    require_ancestor(base, cwd=cwd)
    n = staging_count(base, cwd=cwd)
    if n != 0:
        sys.exit(f"ERROR: stage requires 0 staging commits, found {n}")
    run("git", "add", "-u", cwd=cwd)
    # No-op when nothing is staged.
    r = run("git", "diff", "--cached", "--quiet", check=False, cwd=cwd)
    if r.returncode == 0:
        print("nothing staged, skipping commit")
        return
    run("git", "commit", "-m", args.message, cwd=cwd)


def cmd_amend(args):
    cwd = args.repo
    base = resolve(args.base, cwd=cwd)
    require_ancestor(base, cwd=cwd)
    n = staging_count(base, cwd=cwd)
    if n != 1:
        sys.exit(f"ERROR: amend requires 1 staging commit, found {n}")
    run("git", "add", "-u", cwd=cwd)
    run("git", "commit", "--amend", "--no-edit", cwd=cwd)


def cmd_squash(args):
    cwd = args.repo
    base = resolve(args.base, cwd=cwd)
    require_ancestor(base, cwd=cwd)
    n = staging_count(base, cwd=cwd)
    if n != 1:
        sys.exit(f"ERROR: squash requires 1 staging commit, found {n}")
    # Soft-reset to base stages staging's tree on top of base. Then amend
    # folds it in with the new message — producing one commit with
    # base's parent lineage and staging's changes merged into base's.
    run("git", "reset", "--soft", base, cwd=cwd)
    run("git", "commit", "--amend", "-m", args.message, cwd=cwd)


def cmd_clear(args):
    cwd = args.repo
    base = resolve(args.base, cwd=cwd)
    require_ancestor(base, cwd=cwd)
    n = staging_count(base, cwd=cwd)
    if n != 1:
        sys.exit(f"ERROR: clear requires 1 staging commit, found {n}")
    # Hard reset drops the staging commit and any uncommitted changes.
    run("git", "reset", "--hard", base, cwd=cwd)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in ("stage", "amend", "squash", "clear"):
        sp = sub.add_parser(name)
        sp.add_argument("--base", required=True)
        sp.add_argument("--repo",
                        help="Repo working dir (default: CWD)")
        if name in ("stage", "squash"):
            sp.add_argument("-m", "--message", required=True)

    args = p.parse_args()
    {"stage": cmd_stage,
     "amend": cmd_amend,
     "squash": cmd_squash,
     "clear": cmd_clear}[args.cmd](args)


if __name__ == "__main__":
    main()
