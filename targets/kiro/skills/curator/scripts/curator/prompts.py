"""Prompt rendering — auto-rendered when ``curator next`` yields an
agent task.

Templates live under ``<skill>/templates/``:

    templates/
    ├── security-frame.md.j2          ← shared security preamble
    ├── synthesis-page.md.j2          ← wiki layout for synthesis pages
    ├── report.md.j2                  ← final ingest report
    └── extractors/
        ├── _meta/
        │   ├── extractor.j2          ← base for every per-kind extractor
        │   ├── judge.j2              ← base for every per-kind judge
        │   └── judge-output-schema.yaml  ← shared judge verdict schema
        └── <kind>/
            ├── extractor.j2          ← {% extends 'extractors/_meta/extractor.j2' %}
            ├── judge.j2              ← {% extends 'extractors/_meta/judge.j2' %}
            └── schema.yaml           ← validation schema for the kind

Each agent task has a ``template`` field naming the kind. The
extractor and judge templates inherit security-frame and rubric-
output blocks from the bases under ``_meta/``.

This module's job is only:

1. resolve task ``vars`` placeholders via ``EngineRun``,
2. inject runtime paths (``output_path``, ``verdict_path``),
3. invoke the shared renderer at ``$SKILLS/home/template/scripts/render.sh``
   to produce the prompt,
4. write the resulting prompt file to the task workdir.

Templates are rendered through the shared renderer rather than a
per-skill jinja Environment so curator does not vendor jinja2 (per
conventions.md § Template Rendering).
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from engine.runner import EngineRun
from curator import quintet as _quintet


# Skill paths.
_SKILL_ROOT     = Path(__file__).resolve().parent.parent.parent
_TEMPLATES_DIR  = _SKILL_ROOT / "templates"
_QUINTET_PATH   = Path(__file__).resolve().parent / "quintet.yaml"
_RENDER_SH      = (Path(os.environ.get("SKILLS",
                                          str(Path.home() / ".kiro/skills"))).
                   joinpath("home/template/scripts/render.sh"))

# Extra include-dir contributed by the secure-llm skill. The
# extractor / judge base templates do
# ``{% include 'security-frame.md.j2' %}``; the include resolves
# from secure-llm's templates dir, not from curator's.
_SECURE_LLM_TEMPLATES = (
    Path(os.environ.get("SKILLS",
                          str(Path.home() / ".kiro/skills"))) /
    "home/secure-llm/templates")

_EXTRACTOR_PROMPT_NAME = "extractor-prompt.md"
_JUDGE_PROMPT_NAME     = "judge-prompt.md"

# Templates that need ``slots`` (the quintet vocabulary). Other
# templates do not reference it; injecting it everywhere would be
# rejected by the renderer's strict-unused check (without
# ``--allow-unused``) and bloats the JSON vars file.
_SLOTS_KINDS: frozenset[str] = frozenset({"classify"})


# Defaults injected into every extractor/judge prompt context. The
# base templates (extractors/_meta/{extractor,judge}.j2) reference
# these unconditionally; injecting safe defaults lets per-task vars
# omit them without triggering the renderer's strict-undefined
# check. ``None`` here means "absent" — the templates use the
# ``| default('...', true)`` filter so a None value renders as a
# "(missing)" placeholder.
_COMMON_VAR_DEFAULTS: dict[str, object] = {
    "container_metadata": None,
    "quintet":            None,
    "topic":              None,
    "quintet_path":       str(_QUINTET_PATH),
    "upstream_outputs":   {},
    "upstream_verdicts":  {},
}


def _render(
    template_path: Path,
    variables: dict,
    output_path: Path,
) -> None:
    """Invoke ``render.sh`` with the JSON vars file and write the
    rendered text to ``output_path``. Raises CalledProcessError with
    captured stderr if the renderer exits non-zero.

    ``VIRTUAL_ENV`` is stripped from the subprocess env so the
    renderer's ``uv run`` resolves to its own venv (curator runs
    under its own VIRTUAL_ENV which would otherwise conflict)."""
    # JSON-serialize structured vars; pass via --json-vars so nested
    # dicts/lists survive (--var only carries strings).
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8",
    ) as f:
        json.dump(variables, f)
        vars_file = f.name

    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}

    try:
        proc = subprocess.run(
            [
                str(_RENDER_SH),
                "--template",     str(template_path),
                "--include-dir",  str(_TEMPLATES_DIR),
                "--include-dir",  str(_SECURE_LLM_TEMPLATES),
                "--json-vars",    vars_file,
                "--allow-unused",
            ],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
    finally:
        Path(vars_file).unlink(missing_ok=True)

    output_path.write_text(proc.stdout, encoding="utf-8")


def render_agent_prompts(run: EngineRun, task: dict) -> dict[str, str]:
    """Render extractor + judge prompts for a task.

    ``task['template']`` is the kind name (e.g., ``"classify"``). The
    renderer loads ``templates/extractors/<kind>/{extractor,judge}.j2``
    and writes the output to the task workdir.
    """
    task_id      = task["id"]
    task_workdir = Path(task["task_workdir"])
    output_path  = Path(task["output_path"])
    verdict_path = task_workdir / "verdict.yaml"

    extras: dict[str, str] = {}

    # ── extractor ─────────────────────────────────────────
    kind = task.get("template")
    if kind:
        ext_vars = dict(task.get("vars") or {})
        ext_vars = run.resolve_value(ext_vars, task_id=task_id)
        ext_vars.setdefault("output_path", str(output_path))
        ext_vars.setdefault("kind", kind)
        for k, v in _COMMON_VAR_DEFAULTS.items():
            ext_vars.setdefault(k, v)
        if kind in _SLOTS_KINDS:
            ext_vars.setdefault("slots", _quintet.slots())
        ext_path = task_workdir / _EXTRACTOR_PROMPT_NAME
        _render(
            _TEMPLATES_DIR / "extractors" / kind / "extractor.j2",
            ext_vars,
            ext_path,
        )
        extras["extractor_prompt_path"] = str(ext_path)
        extras["output_path"] = str(output_path)

    # ── judge ─────────────────────────────────────────────
    judge = task.get("judge")
    if judge:
        judge_kind = judge.get("template")
        if not judge_kind:
            raise ValueError(
                f"task {task_id!r} has judge but no judge.template")
        judge_vars = dict(judge.get("vars") or {})
        judge_vars = run.resolve_value(judge_vars, task_id=task_id)
        judge_vars.setdefault("output_path",  str(output_path))
        judge_vars.setdefault("verdict_path", str(verdict_path))
        judge_vars.setdefault("kind", judge_kind)
        for k, v in _COMMON_VAR_DEFAULTS.items():
            judge_vars.setdefault(k, v)
        if judge_kind in _SLOTS_KINDS:
            judge_vars.setdefault("slots", _quintet.slots())
        judge_path = task_workdir / _JUDGE_PROMPT_NAME
        _render(
            _TEMPLATES_DIR / "extractors" / judge_kind / "judge.j2",
            judge_vars,
            judge_path,
        )
        extras["judge_prompt_path"] = str(judge_path)
        extras["verdict_path"]      = str(verdict_path)

    return extras
