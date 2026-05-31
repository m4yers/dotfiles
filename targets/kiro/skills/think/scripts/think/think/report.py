"""Renders the final user-facing markdown report.

Reads the rank task's output, builds a vars dict, and invokes
the `template` skill's `render.sh` against
`<skill>/templates/report.md.j2`. Writes the rendered
markdown to `<workdir>/report.md` and returns the path.

The report links back to the three answer reports and the
rubric so the user can audit the ranking — the orchestrator
shows this file as the workflow's terminal artifact.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

from loom.engine import store as _store


# Path layout: <skill>/scripts/think/think/report.py — parents[3]
# is the skill directory. Used to locate the report template.
SKILL_ROOT = Path(__file__).resolve().parents[3]
REPORT_TEMPLATE = SKILL_ROOT / "templates" / "report.md.j2"


def render(workdir: Path) -> Path:
    """Render the report and return its path."""
    rank_output = _load_rank_output(workdir)
    rubric      = _load_rubric_output(workdir)

    vars_dict = _build_vars(workdir, rank_output, rubric)

    out_path = workdir / "report.md"
    _render_via_template_skill(vars_dict, out_path)
    return out_path


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

def _task_output_path(workdir: Path, task_id: str) -> Path:
    """Resolve via loom's plan-aware numbered task layout."""
    plan = _store.load_plan(workdir)
    return _store.task_output_path(workdir, plan, task_id)


def _load_rank_output(workdir: Path) -> dict[str, Any]:
    p = _task_output_path(workdir, "rank")
    if not p.exists():
        raise FileNotFoundError(f"rank output missing: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _load_rubric_output(workdir: Path) -> dict[str, Any]:
    p = _task_output_path(workdir, "rubric")
    if not p.exists():
        raise FileNotFoundError(f"rubric output missing: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


# ---------------------------------------------------------------------------
# Variables for the Jinja report template
# ---------------------------------------------------------------------------

def _build_vars(
    workdir: Path,
    rank: dict[str, Any],
    rubric: dict[str, Any],
) -> dict[str, Any]:
    """Pre-format the values the template embeds.

    The template skill's renderer is strict-undefined so we
    supply every key the template references, with safe
    defaults for optional ones.
    """
    rejected = rank.get("rejected_judgments", []) or []
    return {
        "question":         str(rubric.get("question_restated", "")),
        "ranking_rows":     _ranking_rows(rank.get("ranking", [])),
        "dimension_rows":   _dimension_rows(
            rank.get("dimension_scores", [])),
        "summary":          str(rank.get("summary", "")),
        "rubric_path":      str(_task_output_path(workdir, "rubric")),
        "answer_links":     _answer_links(rank.get("ranking", [])),
        "confidence_gap":   _fmt_number(rank.get("confidence_gap", 0)),
        "intransitivity_cycles":
            int(rank.get("intransitivity_cycles", 0) or 0),
        "rejected_judgments_count": len(rejected),
        "rejected_judgments_section":
            _rejected_section(rejected),
    }


def _fmt_number(val: Any) -> str:
    """Stable 4-decimal formatting for the report numbers."""
    try:
        return f"{round(float(val), 4)}"
    except (TypeError, ValueError):
        return str(val)


def _ranking_rows(ranking: list[dict]) -> str:
    """Pre-rendered markdown table body rows for the ranking."""
    rows = []
    for i, entry in enumerate(ranking, start=1):
        rows.append(
            f"| {i} | {entry.get('answer_id', '')} | "
            f"{entry.get('score', 0)} | "
            f"[full report]({entry.get('link', '')}) | "
            f"{entry.get('headline', '')} |"
        )
    return "\n".join(rows)


def _dimension_rows(dim_scores: list[dict]) -> str:
    """Pre-rendered markdown table body rows for dimensions."""
    rows = []
    for d in dim_scores:
        avg = d.get("per_answer_averaged", {}) or {}
        weighted = d.get("per_answer_weighted", {}) or {}
        avg_str = ", ".join(
            f"{aid}: {('-' if v is None else round(v, 2))}"
            for aid, v in avg.items()
        )
        weighted_str = ", ".join(
            f"{aid}: {round(v, 4)}"
            for aid, v in weighted.items()
        )
        rows.append(
            f"| {d.get('dimension', '')} | "
            f"{d.get('weight', 0)} | "
            f"{avg_str} | "
            f"{weighted_str} |"
        )
    return "\n".join(rows)


def _rejected_section(rejected: list[dict]) -> str:
    """Bulleted list of rejected compares, or empty string when none."""
    if not rejected:
        return ""
    lines = ["**Rejected compares:**", ""]
    for entry in rejected:
        lines.append(
            f"- `{entry.get('compare_id', '')}` — "
            f"{entry.get('reason', '')}"
        )
    return "\n".join(lines)


def _answer_links(ranking: list[dict]) -> str:
    """Bullet list linking to each answer's full report."""
    return "\n".join(
        f"- {entry.get('answer_id', '')}: "
        f"[{entry.get('headline', '')}]({entry.get('link', '')})"
        for entry in ranking
    )


# ---------------------------------------------------------------------------
# Template skill invocation
# ---------------------------------------------------------------------------

def _render_via_template_skill(
    vars_dict: dict[str, Any], out_path: Path,
) -> None:
    """Invoke `template/scripts/render.sh` with --json-vars.

    Going through the template skill keeps Jinja rendering in
    a single venv with strict-undefined and consistent error
    surface — see script-conventions.md § Rendering Jinja
    Templates.
    """
    skills_root = Path(
        os.environ.get("SKILLS",
                       str(Path.home() / ".kiro" / "skills")))
    render_sh = skills_root / "home" / "template" / "scripts" / "render.sh"
    analytics = (
        skills_root / "home" / "skill-analytics"
        / "scripts" / "add-invocation.sh"
    )

    # Log activation of the template skill (per the template
    # skill's own contract).
    if analytics.is_file():
        subprocess.run(
            [str(analytics), "template", "skill:think"],
            check=False,
        )

    # Hand vars over via a temp JSON file — preferred for
    # multi-line values, per script-conventions.
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8",
    ) as fh:
        json.dump(vars_dict, fh)
        vars_path = fh.name

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as out_fh:
            subprocess.run(
                [
                    str(render_sh),
                    "--template", str(REPORT_TEMPLATE),
                    "--include-dir", str(REPORT_TEMPLATE.parent),
                    "--json-vars", vars_path,
                ],
                stdout=out_fh,
                check=True,
            )
    finally:
        try:
            os.unlink(vars_path)
        except OSError:
            pass
