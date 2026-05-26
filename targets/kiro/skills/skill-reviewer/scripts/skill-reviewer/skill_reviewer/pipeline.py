"""Pipeline subcommands invoked by loom tool tasks.

Exposed as `$REVIEWER pipeline <subcommand>`. Each writes
schema-conforming YAML to stdout (loom captures it as the task's
`output.yaml`).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml

from skill_reviewer import findings as findings_mod
from skill_reviewer import locate as locate_mod
from skill_reviewer import report as report_mod
from skill_reviewer.lint.runner import lint_to_findings, lint_to_text
from skill_reviewer.utils import emit, fail


# ---------------------------------------------------------------------------
# locate
# ---------------------------------------------------------------------------

def cli_locate(
    name: str = typer.Option(..., "--name"),
    category: Optional[str] = typer.Option(None, "--category"),
) -> None:
    """Resolve a skill by name; emit locate.yaml-shaped output."""
    try:
        result = locate_mod.build_locate_output(name, category)
    except (FileNotFoundError, FileExistsError, ValueError) as e:
        fail(str(e), name=name, category=category or "")
    emit(result)


# ---------------------------------------------------------------------------
# lint
# ---------------------------------------------------------------------------

def cli_lint(
    skill_dir: str,
    fmt: str = typer.Option(
        "yaml", "--format",
        help="Output format: yaml (default, schema-conforming) "
             "or text (legacy human-readable)"),
) -> None:
    """Run automated lint and emit findings."""
    sd = Path(skill_dir).expanduser().resolve()
    if not sd.is_dir():
        fail(f"not a directory: {sd}", skill_dir=str(sd))

    if fmt == "text":
        # Print directly, no YAML wrapper. Used by apply phase.
        print(lint_to_text(sd), end="")
        return
    if fmt != "yaml":
        fail(f"unsupported --format: {fmt}", supported=["yaml", "text"])

    findings = lint_to_findings(sd)
    emit({"findings": findings})


# ---------------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------------

def _read_findings(path: Path) -> list[dict]:
    """Read a findings.yaml file; tolerate skipped tasks (missing).

    Returns [] if the file does not exist (skipped task) or has
    no findings field.
    """
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []
    items = data.get("findings", [])
    return items if isinstance(items, list) else []


def cli_assemble(
    workdir: str = typer.Option(..., "--workdir"),
    locate_path: str = typer.Option(..., "--locate"),
    lint_path: str = typer.Option(..., "--lint"),
    check_paths: list[str] = typer.Option(
        [], "--check", help="One per check-* task output.yaml"),
) -> None:
    """Dedupe findings and write the human-readable report file."""
    wd = Path(workdir).resolve()
    locate_data = yaml.safe_load(
        Path(locate_path).read_text(encoding="utf-8"))

    name     = locate_data["name"]
    category = locate_data["category"]
    typ      = locate_data["type"]

    # Collect findings from lint + every check task.
    raw: list[dict] = []
    raw.extend(_read_findings(Path(lint_path)))
    for cp in check_paths:
        raw.extend(_read_findings(Path(cp)))

    # Dedupe on (file_line, title).
    deduped = findings_mod.deduplicate(raw)

    # Stable severity order: Errors → Warnings → Info.
    severity_order = {"Error": 0, "Warning": 1, "Info": 2}
    deduped.sort(key=lambda f: (
        severity_order.get(f.get("severity", "Info"), 99),
        f.get("file_line", ""),
        f.get("title", ""),
    ))

    # Materialize the report file under workdir/global/report.md
    # so it survives across loom calls.
    report_dir = wd / "global"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.md"

    report_mod.create_report(report_path, name, category, typ)
    counts = {"Errors": 0, "Warnings": 0, "Info": 0}
    for f in deduped:
        report_mod.add_finding(
            report_path,
            f["severity"],
            f["title"],
            f.get("file_line", ""),
            f["description"],
            f["fix"],
        )
        section = report_mod.SECTION_FOR_SEVERITY[f["severity"]]
        counts[section] += 1
    report_mod.format_report(report_path)

    emit({
        "report_path": str(report_path),
        "errors":   counts["Errors"],
        "warnings": counts["Warnings"],
        "infos":    counts["Info"],
    })


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------

def cli_finalize(
    workdir: str = typer.Option(..., "--workdir"),
) -> None:
    """Re-emit the assemble counts + report path for terminal report."""
    wd = Path(workdir).resolve()
    report_path = wd / "global" / "report.md"
    if not report_path.exists():
        fail(f"report missing at {report_path}", workdir=str(wd))

    counts = report_mod.count_findings(report_path)
    emit({
        "report_path": str(report_path),
        "errors":   counts["Errors"],
        "warnings": counts["Warnings"],
        "infos":    counts["Info"],
    })


# ---------------------------------------------------------------------------
# gate-decisions — parse the human-edited report file
# ---------------------------------------------------------------------------

import re

_ACCEPT_RE  = re.compile(r"^(\d+)\. ✅", re.MULTILINE)
_DECLINE_RE = re.compile(
    r"^(\d+)\. ⏩.*?\(declined: (.+?)\)", re.MULTILINE)


def cli_gate_decisions(workdir: str) -> None:
    """Parse the report file and emit gate.yaml-shaped decisions.

    The user marks each finding with ✅ (accept) or ⏩ (decline)
    by editing the report. We parse the markers back into a
    structured decision list.
    """
    wd = Path(workdir).expanduser().resolve()
    report = wd / "global" / "report.md"
    if not report.is_file():
        fail(f"report not found at {report}")

    text = report.read_text(encoding="utf-8")
    decisions: list[dict] = []

    # Decline first — they have richer pattern matching.
    for m in _DECLINE_RE.finditer(text):
        decisions.append({
            "finding_id": int(m.group(1)),
            "action": "decline",
            "reason": m.group(2).strip(),
        })
    declined_ids = {d["finding_id"] for d in decisions}

    for m in _ACCEPT_RE.finditer(text):
        fid = int(m.group(1))
        if fid in declined_ids:
            continue
        decisions.append({
            "finding_id": fid,
            "action": "accept",
        })

    decisions.sort(key=lambda d: d["finding_id"])
    emit({"decisions": decisions})
