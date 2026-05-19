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

Rendering pipeline:

1. ``render_context.build_render_context`` produces the schema-shaped
   variables dict (see templates/extractors/_meta/context-schema.yaml).
2. For backward compatibility, the per-task ``vars:`` block is also
   resolved via the engine's ``${task:...}`` placeholder system and
   merged on top of the schema context — flat names old templates
   reference (``source_text_path``, ``quintet``, ...) keep working.
   New templates should reach for the namespaced bags
   (``source.converted_path``, ``upstream.classify.output.quintet``).
3. The shared renderer at ``$SKILLS/home/template/scripts/render.sh``
   reads the merged dict from a JSON file (``--json-vars``) and
   writes the prompt to the task workdir.

Templates render through the shared renderer rather than a
per-skill jinja Environment so curator does not vendor jinja2.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from engine import store
from engine.runner import EngineRun
from curator.render_context import build_render_context


# Skill paths.
_SKILL_ROOT     = Path(__file__).resolve().parent.parent.parent
_TEMPLATES_DIR  = _SKILL_ROOT / "templates"
_CURATOR_PKG    = Path(__file__).resolve().parent  # for {% include 'curator/quintet.yaml' %}
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


def _render(
    template_path: Path,
    variables: dict,
    output_path: Path,
) -> None:
    """Invoke ``render.sh`` with the JSON vars file and write the
    rendered text to ``output_path``. Raises CalledProcessError with
    captured stderr if the renderer exits non-zero.

    Include dirs cover:
      - templates/ (extractor / judge / shared template assets)
      - secure-llm's templates (security-frame.md.j2)
      - curator/ package dir (so classify can {% include 'curator/quintet.yaml' %})

    ``VIRTUAL_ENV`` is stripped from the subprocess env so the
    renderer's ``uv run`` resolves to its own venv (curator runs
    under its own VIRTUAL_ENV which would otherwise conflict)."""
    # JSON-serialize structured vars; pass via --json-vars so nested
    # dicts/lists survive (--var only carries strings).
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8",
    ) as f:
        json.dump(variables, f, default=str)
        vars_file = f.name

    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}

    try:
        proc = subprocess.run(
            [
                str(_RENDER_SH),
                "--template",     str(template_path),
                "--include-dir",  str(_TEMPLATES_DIR),
                "--include-dir",  str(_SECURE_LLM_TEMPLATES),
                "--include-dir",  str(_CURATOR_PKG.parent),  # so 'curator/quintet.yaml' resolves
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
    """Render extractor + judge prompts for an agent task.

    Variables passed to each render call are the schema render
    context (see render_context.py). Templates read schema bags
    directly (`task.output_path`, `upstream.classify.output.quintet`,
    `peers`, etc.); no per-task vars block is consulted, no legacy
    flat names are injected.
    """
    task_id      = task["id"]
    task_workdir = Path(task["task_workdir"])
    output_path  = Path(task["output_path"])
    verdict_path = task_workdir / "verdict.yaml"

    # Build the schema-shaped context once for both extractor and judge.
    plan = store.load_plan(run.workdir)
    task_obj = plan.get(task_id)
    schema_ctx = build_render_context(run.workdir, task_obj, plan)

    extras: dict[str, str] = {}

    # ── extractor ─────────────────────────────────────────
    kind = task.get("template")
    if kind:
        ext_path = task_workdir / _EXTRACTOR_PROMPT_NAME
        _render(
            _TEMPLATES_DIR / "extractors" / kind / "extractor.j2",
            schema_ctx,
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
        judge_path = task_workdir / _JUDGE_PROMPT_NAME
        _render(
            _TEMPLATES_DIR / "extractors" / judge_kind / "judge.j2",
            schema_ctx,
            judge_path,
        )
        extras["judge_prompt_path"] = str(judge_path)
        extras["verdict_path"]      = str(verdict_path)

    return extras
