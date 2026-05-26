"""Convert raw lint findings into the YAML shape mandated by
`findings.yaml`, or render them as text for the apply phase.
"""
from __future__ import annotations

from pathlib import Path

from skill_reviewer.lint.checks import (
    ERROR, INFO, SKIP, WARN, lint_skill,
)

# Mapping from internal severity codes to the schema's enum.
# SKIP (manual checks) is intentionally dropped from the YAML
# emission — these are not violations of the lint, just
# reminders that semantic checks happen elsewhere.
_SEVERITY_MAP = {
    ERROR: "Error",
    WARN:  "Warning",
    INFO:  "Info",
}


def lint_to_findings(skill_dir: Path) -> list[dict]:
    """Run the lint and return a list of finding dicts conforming
    to `findings.yaml`.

    SKIP findings are excluded — they're advisory not actionable.
    """
    out: list[dict] = []
    for severity, filename, lineno, message in lint_skill(skill_dir):
        if severity == SKIP:
            continue
        loc = f"{filename}:{lineno}" if lineno > 0 else filename
        out.append({
            "title": message[:80],
            "file_line": loc,
            "description": message,
            "fix": "Address per skill-builder conventions.",
            "severity": _SEVERITY_MAP[severity],
            "source": "lint",
        })
    return out


def lint_to_text(skill_dir: Path) -> str:
    """Render lint findings in the legacy text format used by the
    apply phase to verify fixes.
    """
    counts = {ERROR: 0, WARN: 0, SKIP: 0, INFO: 0}
    lines: list[str] = []
    for severity, filename, lineno, message in lint_skill(skill_dir):
        counts[severity] += 1
        loc = f"{filename}:{lineno}" if lineno > 0 else filename
        lines.append(f"  {severity:5s}  {loc:30s}  {message}")
    lines.append("")
    lines.append(
        f"Summary: {counts[ERROR]} errors, {counts[WARN]} warnings, "
        f"{counts[SKIP]} skipped (manual), {counts[INFO]} info"
    )
    return "\n".join(lines) + "\n"
