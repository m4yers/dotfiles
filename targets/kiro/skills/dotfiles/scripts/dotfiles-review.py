#!/usr/bin/env python3
"""Review dotfile targets using kiro-cli with Opus 4.6."""
import argparse
import os
import re
import subprocess
import sys

HOME = os.path.expanduser("~")
MAIN = os.path.join(HOME, "dotfiles")
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
CHECKS_FILE = os.path.join(SKILL_DIR, "..", "references", "review-checks.md")

PREAMBLE = (
    "You are reviewing dotfile targets. ALL source files are "
    "provided below — do NOT attempt to read any files or use "
    "any tools. Produce your review based solely on the content "
    "given. Ultrathink through every check thoroughly."
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


def find_target(name):
    for repo in discover_repos():
        path = os.path.join(repo, "targets", name)
        if os.path.isdir(path):
            return repo, path
    return None, None


def collect_target_files(target_dir):
    content = {}
    for entry in sorted(os.listdir(target_dir)):
        path = os.path.join(target_dir, entry)
        if os.path.isfile(path) and not entry.startswith("."):
            try:
                with open(path) as f:
                    content[entry] = f.read()
            except (UnicodeDecodeError, PermissionError):
                pass
    return content


def collect_all_targets():
    targets = {}
    for repo in discover_repos():
        td = os.path.join(repo, "targets")
        if not os.path.isdir(td):
            continue
        short = "~/{}".format(os.path.basename(repo))
        for name in sorted(os.listdir(td)):
            path = os.path.join(td, name)
            if os.path.isdir(path) and not name.startswith("."):
                files = collect_target_files(path)
                targets["{}/{}".format(short, name)] = files
    return targets


def read_file(path):
    if os.path.isfile(path):
        with open(path) as f:
            return f.read()
    return ""


def read_checks():
    return read_file(CHECKS_FILE)


def read_repo_installer(repo):
    return read_file(os.path.join(repo, "install.sh"))


def read_shared_sh():
    return read_file(os.path.join(MAIN, "scripts", "shared.sh"))


def build_context_header():
    """Shared context included in every prompt."""
    parts = [
        PREAMBLE,
        "",
        "## shared.sh (helper library)",
        "```bash",
        read_shared_sh(),
        "```",
        "",
        "## Review Checks",
        read_checks(),
        "",
    ]
    return parts


def build_single_prompt(name, repo, target_dir):
    files = collect_target_files(target_dir)
    repo_installer = read_repo_installer(repo)
    short = "~/{}".format(os.path.basename(repo))

    parts = build_context_header()
    parts.append("## Target: {} ({})".format(name, short))
    parts.append("")

    for fname, content in files.items():
        parts.append("### {}".format(fname))
        parts.append("```")
        parts.append(content)
        parts.append("```")
        parts.append("")

    parts.append("### Repo install.sh ({})".format(short))
    parts.append("```bash")
    parts.append(repo_installer)
    parts.append("```")
    parts.append("")
    parts.append(
        "Apply the Single Target Checks. For each check, state "
        "PASS or FAIL with a brief explanation. Then provide "
        "improvement suggestions. Be specific and actionable."
    )
    return "\n".join(parts)


def build_all_prompt():
    targets = collect_all_targets()

    parts = build_context_header()

    for key, files in targets.items():
        parts.append("## Target: {}".format(key))
        parts.append("")
        for fname, content in files.items():
            parts.append("### {}".format(fname))
            parts.append("```")
            parts.append(content)
            parts.append("```")
            parts.append("")

    for repo in discover_repos():
        short = "~/{}".format(os.path.basename(repo))
        installer = read_repo_installer(repo)
        if installer:
            parts.append("## Repo install.sh ({})".format(short))
            parts.append("```bash")
            parts.append(installer)
            parts.append("```")
            parts.append("")

    parts.append(
        "Apply ALL checks — both Single Target and Global. "
        "For each target, run single-target checks (PASS/FAIL). "
        "Then run global checks across all targets. "
        "End with improvement suggestions. "
        "Be specific and actionable."
    )
    return "\n".join(parts)


def run_review(prompt):
    result = subprocess.run(
        [
            "kiro-cli", "chat",
            "--no-interactive",
            "--wrap=never",
            "--trust-tools=",
            "--model", "claude-opus-4.6",
            prompt,
        ],
        capture_output=True,
        text=True,
    )
    # Strip ANSI codes
    return re.sub(r'\x1b\[[0-9;]*m', '', result.stdout)


def main():
    parser = argparse.ArgumentParser(
        description="Review dotfile targets using Opus 4.6"
    )
    parser.add_argument("scope", help="Target name or 'all'")
    args = parser.parse_args()

    if args.scope == "all":
        print("Reviewing all targets with Opus 4.6...",
              file=sys.stderr)
        prompt = build_all_prompt()
    else:
        repo, target_dir = find_target(args.scope)
        if not target_dir:
            print("Target '{}' not found".format(args.scope),
                  file=sys.stderr)
            sys.exit(1)
        short = "~/{}".format(os.path.basename(repo))
        print("Reviewing {} ({}) with Opus 4.6...".format(
            args.scope, short), file=sys.stderr)
        prompt = build_single_prompt(args.scope, repo, target_dir)

    output = run_review(prompt)
    print(output)


if __name__ == "__main__":
    main()
