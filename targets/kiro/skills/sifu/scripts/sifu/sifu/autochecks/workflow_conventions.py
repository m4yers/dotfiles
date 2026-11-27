"""Automated checks for ``references/workflow-conventions.md``."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml
from typing import List, Tuple

from sifu.autochecks._helpers import ERROR, Finding, WARN, rule
from sifu.utils import SKILLS_ROOT


@rule('references/workflow-conventions.md:2.2')
def rule_2_2_activity_pattern(
    lines: List[str],
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Each step MUST start with ``activity set`` containing a target.

    The template enforces the pattern; this rule lints hand-edited
    SKILL.md files for conformance.

    Rule: references/workflow-conventions.md:2.2
    """
    findings: List[Finding] = []
    step_headings = [
        h for h in headings
        if h[1] == 3 and re.match(r"^(Step\s+)?\d+", h[2])
    ]
    for ph_lineno, _, ph_text in step_headings:
        found_activity = False
        has_target = False
        # 15 lines is the typical max distance between a step heading and
        # its `activity set` line.
        search_end = min(ph_lineno + 15, len(lines))
        for j in range(ph_lineno, search_end):
            if "activity set" in lines[j]:
                found_activity = True
                if re.search(
                    r'activity set "[^"]*\([^)]+\)', lines[j],
                ):
                    has_target = True
                break
            if (j > ph_lineno
                    and lines[j].strip().startswith("#")):
                break
        if not found_activity:
            findings.append(
                (ERROR, "SKILL.md", ph_lineno,
                 f"step '{ph_text}' does not start with "
                 f"tiling activity set")
            )
        elif not has_target:
            findings.append(
                (ERROR, "SKILL.md", ph_lineno,
                 f"step '{ph_text}' activity label missing "
                 f"target — use \"skill(<target>): Step\"")
            )
    return findings


@rule('references/workflow-conventions.md:8.2')
def rule_8_2_max_substeps(
    lines: List[str],
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Each step MUST have at most 5 numbered sub-steps.

    Rule: references/workflow-conventions.md:8.2
    """
    findings: List[Finding] = []
    step_headings = [
        h for h in headings
        if h[1] == 3 and re.match(r"^(Step\s+)?\d+", h[2])
    ]
    for idx, (ph_lineno, _, ph_text) in enumerate(step_headings):
        if idx + 1 < len(step_headings):
            step_end = step_headings[idx + 1][0] - 1
        else:
            step_end = len(lines)
        substep_count = 0
        in_code = False
        for j in range(ph_lineno, step_end):
            ln = lines[j]
            if ln.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if ln.strip().startswith("## "):
                break
            if re.match(r"^\d+\.\s", ln):
                substep_count += 1
        if substep_count > 5:
            findings.append(
                (ERROR, "SKILL.md", ph_lineno,
                 f"step '{ph_text}' has {substep_count} "
                 f"sub-steps (max 5)")
            )
    return findings


# Loomv2 CLI shim (sibling skill).
LOOM_SH = SKILLS_ROOT / "home" / "loomv2" / "scripts" / "loom.sh"

# Body file per task kind (loomv2 references/guide.md §1).
_BODY_FILES = {
    "tool": ("tool.py", "tool.sh"),
    "agent": ("prompt.md.j2",),
    "human": ("message.md.j2",),
}

# Domain-prefixed kebab task id (workflow-conventions §4.3).
TASK_ID = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9{}]+)+$")

# 120s — `loom validate` loads and projects every io.yaml; a
# timeout past two minutes means a hung uv sync, not a slow graph.
_VALIDATE_TIMEOUT = 120


def _graph_files(skill_dir: Path) -> List[Path]:
    return sorted(skill_dir.glob("loom*/graph*.yaml"))


def _is_legacy_loom(skill_dir: Path) -> bool:
    skill_md = skill_dir / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8") if skill_md.exists() else ""
    if "skills/home/loom/scripts/loom.sh" in text:
        return True
    for py in (skill_dir / "scripts").rglob("plan.py") if (
            skill_dir / "scripts").is_dir() else []:
        if ".venv" in py.parts:
            continue
        if re.search(r"^from loom import", py.read_text(encoding="utf-8"),
                     re.MULTILINE):
            return True
    return False


@rule('references/workflow-conventions.md:3.1')
def rule_3_1_loomv2_driver(skill_dir: Path) -> List[Finding]:
    """Workflow skills MUST be driven by a loomv2 graph; legacy
    loom skills SHOULD migrate.

    Rule: references/workflow-conventions.md:3.1
    """
    if _graph_files(skill_dir):
        return []
    if _is_legacy_loom(skill_dir):
        return [(WARN, "SKILL.md", 0,
                 "workflow driven by legacy loom — migrate to a "
                 "loomv2 `loom/graph.yaml`")]
    return [(ERROR, "SKILL.md", 0,
             "workflow skill has no loomv2 graph (`loom*/graph*.yaml`)"
             " — use `type: flow` for prose-step workflows")]


@rule('references/workflow-conventions.md:3.4')
def rule_3_4_graphs_validate(skill_dir: Path) -> List[Finding]:
    """Every graph file MUST pass `$LOOM validate`.

    Rule: references/workflow-conventions.md:3.4
    """
    findings: List[Finding] = []
    graphs = _graph_files(skill_dir)
    if graphs and not LOOM_SH.is_file():
        return [(WARN, "SKILL.md", 0,
                 f"loomv2 CLI not found at {LOOM_SH} — graphs not validated")]
    for graph in graphs:
        rel = str(graph.relative_to(skill_dir))
        try:
            proc = subprocess.run(
                [str(LOOM_SH), "validate", str(skill_dir),
                 "--graph", str(graph)],
                capture_output=True, text=True, check=False,
                timeout=_VALIDATE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            findings.append((ERROR, rel, 0, "`loom validate` timed out"))
            continue
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout).strip().splitlines()
            msg = tail[-1] if tail else "non-zero exit"
            findings.append((ERROR, rel, 0, f"`loom validate` failed: {msg}"))
    return findings


@rule('references/workflow-conventions.md:4.1')
def rule_4_1_task_folder_alignment(skill_dir: Path) -> List[Finding]:
    """Every task folder MUST back a graph entry (id or `ref`),
    carry `io.yaml`, and carry exactly the body file its kind
    needs; task ids MUST be domain-prefixed kebab.

    Rule: references/workflow-conventions.md:4.1
    """
    findings: List[Finding] = []
    roots: dict = {}
    for graph in _graph_files(skill_dir):
        try:
            data = yaml.safe_load(graph.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            findings.append((ERROR, str(graph.relative_to(skill_dir)), 0,
                             f"graph is not valid YAML: {exc}"))
            continue
        used = roots.setdefault(graph.parent, set())
        for entry in data.get("tasks") or []:
            tid = entry.get("id", "")
            kind = entry.get("kind", "")
            if kind == "subgraph":
                continue
            if tid not in ("ingest-input", "publish-output") and \
                    not TASK_ID.match(tid):
                findings.append((WARN, str(graph.relative_to(skill_dir)), 0,
                                 f"task id '{tid}' is not domain-prefixed "
                                 f"kebab"))
            used.add(entry.get("ref") or tid)
    for root, used in roots.items():
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            if folder.name.startswith(("_", ".")):
                continue
            rel = str(folder.relative_to(skill_dir))
            if folder.name not in used:
                findings.append((WARN, rel, 0,
                                 f"task folder '{folder.name}' is not "
                                 f"used by any graph"))
            if not (folder / "io.yaml").is_file():
                findings.append((ERROR, rel, 0,
                                 "task folder has no io.yaml"))
            bodies = [b for names in _BODY_FILES.values() for b in names
                      if (folder / b).is_file()]
            if len(bodies) != 1:
                findings.append((ERROR, rel, 0,
                                 f"task folder must hold exactly one body "
                                 f"file, found {bodies or 'none'}"))
    return findings


@rule('references/workflow-conventions.md:8.1')
def rule_8_1_descriptive_step_name(
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Each step MUST have a descriptive name after the number
    (e.g., "Step 1: Setup & Checkout"), not just "Step 1".

    Rule: references/workflow-conventions.md:8.1
    """
    findings: List[Finding] = []
    step_re = re.compile(r"^(?:Step\s+)?(\d+)(?::\s*(.+))?\s*$")
    for ph_lineno, level, text in headings:
        if level != 3:
            continue
        m = step_re.match(text)
        if not m:
            continue
        name = (m.group(2) or "").strip()
        if not name:
            findings.append(
                (ERROR, "SKILL.md", ph_lineno,
                 f"step heading '{text}' has no descriptive name "
                 f"after the number")
            )
    return findings
