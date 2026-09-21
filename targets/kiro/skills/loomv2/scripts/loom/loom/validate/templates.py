"""Static Jinja template reference validation.

For every task's ``prompt.md.j2`` / ``message.md.j2``, parse the Jinja
AST (delegating to the ``template`` skill's ``--parse-only`` mode so
this package does not vendor ``jinja2`` directly) and enforce
contract-locality:

  1. Every top-level undeclared identifier is a subset of ``{"input"}``
     (the only in-scope Jinja name — the validated ``input.yaml``).
  2. Every ``input.<attr>`` reference targets an attribute declared in
     the task's ``io.yaml/input.properties``.
  3. ``input.__loom.<attr>`` / ``input.__task.<attr>`` references must
     be a property of the corresponding meta-schema
     (``schemas/loom-meta.yaml`` / ``schemas/task-meta.yaml``).

Raises :class:`TemplateReferenceError` on the first breach with the
offending name, task id, and template path. Runs in
``_lifecycle._static_validate`` so ``$LOOM validate`` and
``$LOOM runtime init`` reject offending plans before any workdir
write.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from loom.engine.models import LoomPlan, Task
from loom.engine.reserved import (
    RESERVED_ALIASES,
    RESERVED_FIELDS,
    load_meta_schema,
)
from loom.errors import TemplateReferenceError


TEMPLATE_RENDER_SH = Path(
    os.path.expanduser("~/.kiro/skills/home/template/scripts/render.sh")
)


def validate_templates(plan: LoomPlan) -> None:
    """Enforce Jinja-template contract-locality for every task."""
    from loom.discovery import load_io_yaml
    from loom.engine.runner import task_source_folder

    for t in plan.tasks:
        if not isinstance(t, Task):
            continue
        if t.kind == "tool":
            continue
        template_name = (
            "prompt.md.j2" if t.kind == "agent" else "message.md.j2"
        )
        source_folder = task_source_folder(plan.loom_root, t)
        template_path = source_folder / template_name
        if not template_path.exists():
            # io.yaml / kind validators flag missing body files separately.
            continue
        info = _parse_template(t.id, template_path)
        # (1) Top-level names must be ⊆ {"input"}.
        for name in info["undeclared"]:
            if name != "input":
                raise TemplateReferenceError(
                    t.id, name, str(template_path)
                )
        io = load_io_yaml(source_folder)
        properties = io.input_schema.get("properties") or {}
        for chain in info["getattr_chains"]:
            if not chain or chain[0] != "input" or len(chain) < 2:
                continue
            first_attr = chain[1]
            # (2) First-level input.<attr>.
            if first_attr not in properties:
                raise TemplateReferenceError(
                    t.id, f"input.{first_attr}", str(template_path)
                )
            # (3) Second-level on reserved: input.__loom.<attr> /
            #     input.__task.<attr>.
            if first_attr in RESERVED_FIELDS and len(chain) >= 3:
                alias = RESERVED_ALIASES[first_attr]
                meta_schema = load_meta_schema(alias)
                meta_props = meta_schema.get("properties") or {}
                second_attr = chain[2]
                if second_attr not in meta_props:
                    raise TemplateReferenceError(
                        t.id,
                        f"input.{first_attr}.{second_attr}",
                        str(template_path),
                    )


def _parse_template(task_id: str, template_path: Path) -> dict:
    """Delegate template AST parsing to the ``template`` skill.

    Calls ``render.sh --parse-only`` and returns the decoded JSON
    summary (``{"undeclared": [...], "getattr_chains": [...]}``).
    Raises :class:`TemplateReferenceError` on any parse-side failure
    (script missing, syntax error, malformed JSON) with the task id
    and template path in the exception.
    """
    try:
        proc = subprocess.run(
            [
                str(TEMPLATE_RENDER_SH),
                "--template", str(template_path),
                "--parse-only",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise TemplateReferenceError(
            task_id, str(exc), str(template_path)
        ) from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise TemplateReferenceError(
            task_id, detail, str(template_path)
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise TemplateReferenceError(
            task_id, f"parse-only emitted invalid JSON: {exc}",
            str(template_path),
        ) from exc
