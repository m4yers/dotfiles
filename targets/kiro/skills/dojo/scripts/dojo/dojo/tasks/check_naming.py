"""Tool task: verify a workflow design uses domain-prefixed
(`<domain>-<name>`) names for tasks, schemas, and prompts, and
that schema/prompt prefixes belong to the task domain vocabulary.

Runs at design time (gated before design-review) so bad names
abort the run before materialization. Exits non-zero on any
violation so loom marks the task ``failed`` → ``RunAborted``.

Create-only (like check-design): update/review operate on an
existing skill and have no design YAML to inspect.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import typer
import yaml

from loom import tool

from dojo.utils import emit, fail

ID = "check-naming"

# Domain-prefixed kebab: starts with a letter, then one or more
# "-segment" groups (so at least one hyphen → a domain prefix).
# Segments allow lowercase, digits, and {}/placeholders (e.g.
# the fixed-pool representative `conflict-resolve-{i}`).
_DOMAIN_KEBAB = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9{}]+)+$")

_SKILL_ROOT = Path(__file__).resolve().parents[4]
SCHEMA = _SKILL_ROOT / "schemas" / "validate.yaml"
SHIM = _SKILL_ROOT / "scripts" / "dojo.sh"

_FILE_KINDS = (
    ("schemas/", ".yaml", "schema"),
    ("templates/prompts/", ".md.j2", "prompt"),
)


def task(*, depends_on_all=()):
    return tool(
        ID,
        cmd=[str(SHIM), "check", "naming", "--design",
             "${task_path:design}"],
        output_schema=str(SCHEMA),
        depends_on_all=list(depends_on_all) if depends_on_all else None,
    )


def run(design: dict) -> dict:
    """Validate domain-prefixed names. Returns {ok, error?}.

    Only workflow designs (those with a tasks[] array) are
    checked; others pass trivially.
    """
    tasks = design.get("tasks") or []
    if not tasks:
        return {"ok": True}

    errors: list[str] = []
    ids = [(t.get("id") or "").strip() for t in tasks]

    for tid in ids:
        if not _DOMAIN_KEBAB.match(tid):
            errors.append(
                f"task id '{tid}' is not domain-prefixed kebab "
                "(expected '<domain>-<name>', e.g. 'cr-info')")

    domains = {tid.split("-", 1)[0] for tid in ids if "-" in tid}

    for f in (design.get("files") or []):
        path = (f.get("path") or "").strip()
        for prefix, ext, label in _FILE_KINDS:
            if not (path.startswith(prefix) and path.endswith(ext)):
                continue
            base = path[len(prefix):-len(ext)]
            if not _DOMAIN_KEBAB.match(base):
                errors.append(
                    f"{label} '{path}' is not domain-prefixed kebab")
            elif base.split("-", 1)[0] not in domains:
                errors.append(
                    f"{label} '{path}' prefix "
                    f"'{base.split('-', 1)[0]}' is not one of the "
                    f"task domains {sorted(domains)}")

    if errors:
        return {"ok": False, "error": "; ".join(errors)}
    return {"ok": True}


def cli_check(
    design: Optional[Path] = typer.Option(
        None, "--design", help="Path to the design agent output.yaml"),
) -> None:
    """`dojo.sh check naming --design <path>` — exit non-zero on
    a non-domain-prefixed task/schema/prompt name."""
    if design is None or not design.exists():
        fail(f"design output not found at {design}")
    payload = yaml.safe_load(design.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail(f"design output at {design} is not a YAML mapping")
    result = run(payload)
    emit(result)
    if not result["ok"]:
        raise typer.Exit(code=1)
