#!/usr/bin/env python3
"""book-lab repo shim: own git and the Part/Chapter layout.

Subcommands:
  init      git-init the repo, write AGENTS.md, make the first commit
  status    emit a YAML summary of parts, chapters, and their scripts
  scaffold  create a chapter folder on demand and write a new experiment
  commit    stage everything and commit with a message

stdlib only: subprocess for git, pathlib for the tree.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"

# Folder labels are author-controlled strings, not integers: the example
# convention is a Roman-numeral part ("PartI") and an arabic chapter
# ("Chapter2"), so --part / --chapter are pasted verbatim after the prefix.
PART_PREFIX = "Part"
CHAPTER_PREFIX = "Chapter"


def _fail(msg: str) -> None:
    print(f"book-lab: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=check,
    )


def _is_git_repo(repo: Path) -> bool:
    cp = _git(repo, "rev-parse", "--is-inside-work-tree", check=False)
    return cp.returncode == 0 and cp.stdout.strip() == "true"


def cmd_init(args: argparse.Namespace) -> None:
    repo = Path(args.repo).expanduser().resolve()
    repo.mkdir(parents=True, exist_ok=True)

    if not _is_git_repo(repo):
        _git(repo, "init")

    agents = repo / "AGENTS.md"
    if agents.exists():
        print(f"AGENTS.md already present at {agents}, leaving it unchanged")
    else:
        template = TEMPLATES / "agents.md"
        if not template.exists():
            _fail(f"missing template {template}")
        agents.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"wrote {agents}")

    _git(repo, "add", "-A")
    staged = _git(repo, "diff", "--cached", "--quiet", check=False)
    if staged.returncode == 0:
        print("nothing to commit; repo already initialised")
        return
    _git(repo, "commit", "-m", "Initialise book-lab repo")
    print(f"initialised book-lab repo at {repo}")


def _chapters(repo: Path) -> list[dict]:
    """Return part/chapter entries sorted by path, newest script mtime noted."""
    out: list[dict] = []
    for part_dir in sorted(repo.glob(f"{PART_PREFIX}*")):
        if not part_dir.is_dir():
            continue
        part = part_dir.name[len(PART_PREFIX):]
        for chap_dir in sorted(part_dir.glob(f"{CHAPTER_PREFIX}*")):
            if not chap_dir.is_dir():
                continue
            scripts = sorted(p.name for p in chap_dir.glob("*.py"))
            mtime = max((p.stat().st_mtime for p in chap_dir.glob("*.py")), default=0.0)
            out.append(
                {
                    "part": part,
                    "chapter": chap_dir.name[len(CHAPTER_PREFIX):],
                    "scripts": scripts,
                    "_mtime": mtime,
                }
            )
    return out


def cmd_status(args: argparse.Namespace) -> None:
    repo = Path(args.repo).expanduser().resolve()
    if not _is_git_repo(repo):
        _fail(f"{repo} is not a git repo; run `init` first")

    entries = _chapters(repo)
    last = max(entries, key=lambda e: e["_mtime"], default=None)

    summary = {
        "repo": str(repo),
        "parts": [
            {"part": e["part"], "chapter": e["chapter"], "scripts": e["scripts"]}
            for e in entries
        ],
        "last_chapter": (
            {"part": last["part"], "chapter": last["chapter"]}
            if last and last["_mtime"] > 0
            else None
        ),
    }
    # JSON is a subset of YAML, so this prints valid YAML while json.dumps
    # handles quoting of any path or filename that contains special chars.
    print(json.dumps(summary, indent=2))


def cmd_scaffold(args: argparse.Namespace) -> None:
    repo = Path(args.repo).expanduser().resolve()
    if not _is_git_repo(repo):
        _fail(f"{repo} is not a git repo; run `init` first")

    chap_dir = repo / f"{PART_PREFIX}{args.part}" / f"{CHAPTER_PREFIX}{args.chapter}"
    chap_dir.mkdir(parents=True, exist_ok=True)

    target = chap_dir / f"{args.name}.py"
    if target.exists():
        _fail(f"{target} already exists; pick another name or edit it directly")

    template = TEMPLATES / "experiment.py"
    if not template.exists():
        _fail(f"missing template {template}")
    target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    print(str(target))


def cmd_commit(args: argparse.Namespace) -> None:
    repo = Path(args.repo).expanduser().resolve()
    if not _is_git_repo(repo):
        _fail(f"{repo} is not a git repo; run `init` first")

    _git(repo, "add", "-A")
    staged = _git(repo, "diff", "--cached", "--quiet", check=False)
    if staged.returncode == 0:
        print("nothing to commit")
        return
    _git(repo, "commit", "-m", args.message)
    print(f"committed: {args.message}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="git-init repo, write AGENTS.md, first commit")
    p_init.add_argument("--repo", required=True)
    p_init.set_defaults(func=cmd_init)

    p_status = sub.add_parser("status", help="emit YAML progress summary")
    p_status.add_argument("--repo", required=True)
    p_status.set_defaults(func=cmd_status)

    p_scaffold = sub.add_parser("scaffold", help="create chapter folder + new experiment")
    p_scaffold.add_argument("--repo", required=True)
    p_scaffold.add_argument("--part", required=True, help="part label, e.g. I or 1")
    p_scaffold.add_argument("--chapter", required=True, help="chapter label, e.g. 2")
    p_scaffold.add_argument("--name", required=True, help="experiment slug (no .py)")
    p_scaffold.set_defaults(func=cmd_scaffold)

    p_commit = sub.add_parser("commit", help="stage all and commit")
    p_commit.add_argument("--repo", required=True)
    p_commit.add_argument("--message", required=True)
    p_commit.set_defaults(func=cmd_commit)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
