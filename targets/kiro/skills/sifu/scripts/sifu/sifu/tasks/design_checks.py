"""Tool task: deterministic layout check over a workflow design.

Runs before the design-review gate so a malformed design aborts
before the human reviews it and before materialization. Only
workflow designs (non-empty ``tasks[]``) are checked; other types
pass trivially.

Checks:

- every task id is domain-prefixed kebab (``<domain>-<name>``),
  except the loomv2 entry/exit names ``ingest-input`` /
  ``publish-output``;
- every task id (or its ``ref``) is backed by a ``files[]`` entry
  ``loom*/<folder>/``.
"""
from __future__ import annotations

import re

from sifu.autochecks.workflow_conventions import TASK_ID as _DOMAIN_KEBAB

_FOLDER = re.compile(r"^loom[a-z0-9-]*/([a-z][a-z0-9-]*)/?")


def run(design: dict) -> dict:
    """Return ``{ok, error}``; ``error`` is ``""`` when ok."""
    tasks = design.get("tasks") or []
    if not tasks:
        return {"ok": True, "error": ""}

    folders = set()
    for f in design.get("files") or []:
        m = _FOLDER.match((f.get("path") or "").strip())
        if m:
            folders.add(m.group(1))

    errors: list[str] = []
    for t in tasks:
        tid = (t.get("id") or "").strip()
        if tid not in ("ingest-input", "publish-output") and \
                not _DOMAIN_KEBAB.match(tid):
            errors.append(f"task id '{tid}' is not domain-prefixed kebab")
        folder = (t.get("ref") or "").strip() or tid
        # The design may list subgraph tasks under a display prefix
        # (e.g. `audit-ingest-input` for `loom-audit/ingest-input`).
        candidates = {folder, folder.split("-", 1)[-1]}
        if folders and not candidates & folders:
            errors.append(
                f"task '{tid}' has no `loom*/{folder}/` entry in files[]")
    return {"ok": not errors, "error": "; ".join(errors)}
