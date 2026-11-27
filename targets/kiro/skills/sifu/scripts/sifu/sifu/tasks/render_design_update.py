"""Tool task: render the `design-author-update` agent's YAML
output as a human-readable markdown report for the
`design-review-update` human gate.

Unlike create's `render_design.py` (which builds markdown via
pure-Python string concat over the create-side schema), this
renderer goes through a Jinja template at
``templates/render/design-update.md.j2``. The change-plan
shape is regular enough (file lists grouped by action, open
questions, rationale) that a template is the cleaner home for
presentation tweaks; future edits don't require Python
changes.

Rendering itself is delegated to the shared `template` skill
via ``~/.kiro/skills/home/template/scripts/render.sh`` so this
package does not vendor jinja2; the template skill owns the
strict-undefined renderer, the include search path semantics,
and the dependency lifecycle.

Pipeline:

1. Receive the change plan from ``input.yaml`` (``plan``).
2. Group ``change_plan.files[]`` by ``action`` into
   ``files_created`` / ``files_modified`` / ``files_deleted``
   so the template stays declarative.
3. Write the grouped vars to a temp JSON file and shell out to
   ``template/scripts/render.sh`` with ``--template`` and
   ``--json-vars``.
4. mdformat the result for an 80-char wrap.
5. Write ``design.md`` into the task workdir (``loomtasks``) and
   emit ``{report_path}``.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import mdformat
import yaml


from sifu.utils import SKILLS_ROOT, emit, fail


_SKILL_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE = (
    _SKILL_ROOT / "templates" / "render" / "design-update.md.j2"
)
RENDER_SH = SKILLS_ROOT / "home" / "template" / "scripts" / "render.sh"


def _group_files(files: list[dict]) -> tuple[list, list, list]:
    """Partition ``change_plan.files[]`` by ``action``. Drops
    ``content_outline`` (consumed by modify-changes, not shown
    in the review markdown). Returns (created, modified, deleted)
    in plan order within each bucket."""
    created: list[dict] = []
    modified: list[dict] = []
    deleted: list[dict] = []
    for f in files:
        if not isinstance(f, dict):
            continue
        action = (f.get("action") or "").strip()
        entry = {
            "path":    (f.get("path") or "").strip(),
            "summary": (f.get("summary") or "").strip(),
        }
        rationale = (f.get("rationale") or "").strip()
        if rationale:
            entry["rationale"] = rationale
        if action == "created":
            created.append(entry)
        elif action == "modified":
            modified.append(entry)
        elif action == "deleted":
            deleted.append(entry)
        else:
            fail(f"unknown change-plan action '{action}' for {entry['path']}")
    return created, modified, deleted


def _render(payload: dict, canonical_yaml_path: str) -> str:
    """Render the change-plan YAML via the shared template
    skill. Writes the template variables to a temp JSON file
    and shells out to ``render.sh``; captures stdout."""
    skill = payload.get("skill") or {}
    change_plan = payload.get("change_plan") or {}
    files = change_plan.get("files") or []
    created, modified, deleted = _group_files(files)

    vars_ = {
        "skill": {
            "name":      (skill.get("name") or "").strip(),
            "namespace": (skill.get("namespace") or "").strip(),
            "type":      (skill.get("type") or "").strip(),
            "path":      (skill.get("path") or "").strip(),
        },
        "change_request":
            (payload.get("change_request") or "").strip(),
        "files_created":  created,
        "files_modified": modified,
        "files_deleted":  deleted,
        "open_questions":
            list(change_plan.get("open_questions") or []),
        "rationale": (change_plan.get("rationale") or "").strip(),
        "canonical_yaml_path": canonical_yaml_path,
    }

    if not RENDER_SH.is_file():
        fail(f"template renderer not found at {RENDER_SH}")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8",
    ) as fh:
        json.dump(vars_, fh)
        json_path = fh.name
    try:
        result = subprocess.run(
            [
                str(RENDER_SH),
                "--template", str(TEMPLATE),
                "--json-vars", json_path,
            ],
            check=False, capture_output=True, text=True,
        )
    finally:
        os.unlink(json_path)
    if result.returncode != 0:
        fail(
            f"template render failed: {result.stderr.strip() or result.stdout.strip()}",
            template=str(TEMPLATE),
        )
    return result.stdout


