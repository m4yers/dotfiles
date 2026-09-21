"""Render prompt.md.j2 / message.md.j2 via the shared template skill.

Delegates to ``~/.kiro/skills/home/template/scripts/render.sh`` so this
skill does not vendor ``jinja2``. Context is CONTRACT-LOCAL: every task
sees ONLY ``input`` — the validated ``input.yaml`` the engine
materialised at dispatch. There is no ambient state; every value a
template can reference is a property in the task's ``io.yaml/input``.

Reserved default objects (``__loom``, ``__task``) are ordinary opt-in
io.yaml properties whose values happen to be objects filled by the
engine at dispatch. Templates access them as
``{{ input.__loom.workdir }}`` / ``{{ input.__task.id }}``; Jinja's
default ``Environment.getattr`` falls back to ``obj[attribute]`` when
``getattr`` raises ``AttributeError``, so dict-subscript resolution
works on the plain dicts persisted in ``input.yaml``.

The renderer is already ``StrictUndefined`` via the template skill;
undeclared names raise ``RenderFailed``. Static enforcement lives in
``loom.validate.templates`` so the contract is caught at
``$LOOM validate`` / ``$LOOM runtime init`` rather than only at
dispatch.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from loom.engine.models import Task
from loom.errors import RenderFailed


TEMPLATE_RENDER_SH = Path(
    os.path.expanduser("~/.kiro/skills/home/template/scripts/render.sh")
)

SECURE_LLM_TEMPLATES = Path(
    os.path.expanduser("~/.kiro/skills/home/secure-llm/templates")
)


def render_task_body(
    task: Task,
    task_folder: Path,
    input_data: dict[str, Any],
) -> str:
    """Render ``task``'s Jinja body (prompt/message) to a string.

    Shells out to the ``template`` skill. Raises :class:`RenderFailed`
    on any non-zero exit (missing template, undefined variable, syntax
    error).
    """
    template_name = "prompt.md.j2" if task.kind == "agent" else "message.md.j2"
    template_path = task_folder / template_name

    variables = {"input": input_data}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as fh:
        json.dump(variables, fh, default=str)
        vars_path = fh.name

    # Include dirs enable ``{% include %}`` resolution against the
    # task folder (for the template itself), the containing skill's
    # ``references/`` directory (for skill-local shared partials),
    # and the shared secure-llm templates directory (for the
    # security frame partial).
    include_dirs = [task_folder, task_folder.parent.parent / "references"]
    if SECURE_LLM_TEMPLATES.is_dir():
        include_dirs.append(SECURE_LLM_TEMPLATES)
    include_args: list[str] = []
    for d in include_dirs:
        include_args += ["--include-dir", str(d)]

    try:
        proc = subprocess.run(
            [
                str(TEMPLATE_RENDER_SH),
                "--template", str(template_path),
                "--json-vars", vars_path,
                *include_args,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        Path(vars_path).unlink(missing_ok=True)

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise RenderFailed(task.id, str(template_path), detail)
    return proc.stdout
