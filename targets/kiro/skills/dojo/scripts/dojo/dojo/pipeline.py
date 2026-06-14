"""Pipeline subcommands invoked by loom tool tasks.

Exposed as `dojo.sh pipeline <subcommand>`. Each writes
schema-conforming YAML to stdout (loom captures it as the task's
`output.yaml`).
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import typer
import yaml

from dojo import findings as findings_mod
from dojo import report as report_mod
from dojo.autochecks.checks import lint_to_findings, lint_to_text
from dojo.utils import emit, fail


# ---------------------------------------------------------------------------
# autochecks
# ---------------------------------------------------------------------------

def cli_autochecks(
    skill_dir: str,
    fmt: str = typer.Option(
        "yaml", "--format",
        help="Output format: yaml (default, schema-conforming) "
             "or text (legacy human-readable)"),
) -> None:
    """Run automated rule checks and emit findings."""
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
    autochecks_path: str = typer.Option(..., "--autochecks"),
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

    # Collect findings from autochecks + every check task.
    raw: list[dict] = []
    raw.extend(_read_findings(Path(autochecks_path)))
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
            rule_ref=f.get("rule_ref", ""),
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

def cli_show_report(
    workdir: str = typer.Option(..., "--workdir"),
    skill_dir: str = typer.Option(..., "--skill-dir"),
) -> None:
    """`dojo.sh pipeline show-report` — open report.md in the editor.

    Loop header for the review fix loop: re-displays the current
    report (with items already marked ✅/⏩ on prior passes) and
    emits the report path, skill_dir, and counts. It carries
    skill_dir so the loop-body tasks reference only this header
    (loom requires single-entry loop regions).
    """
    wd = Path(workdir).resolve()
    report_path = wd / "global" / "report.md"
    if not report_path.exists():
        fail(f"report missing at {report_path}", workdir=str(wd))

    editor_sh = (
        Path.home() / ".kiro" / "skills" / "home"
        / "editor" / "scripts" / "run-editor.sh"
    )
    if editor_sh.is_file():
        try:
            subprocess.run(
                [str(editor_sh), "show", "file", str(report_path)],
                timeout=30, check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass  # display is best-effort; never block the loop

    counts = report_mod.count_findings(report_path)
    emit({
        "report_path": str(report_path),
        "skill_dir":   skill_dir,
        "errors":   counts["Errors"],
        "warnings": counts["Warnings"],
        "infos":    counts["Info"],
    })


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
# gate-decisions — removed: the review fix loop (show-report ->
# skill-fix-review -> skill-fix-apply) replaced the single gate;
# fixes are applied via `report accept/decline` and the loop exits
# on `report open-count`.
# ---------------------------------------------------------------------------

