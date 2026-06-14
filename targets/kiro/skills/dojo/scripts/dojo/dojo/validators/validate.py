"""Pipeline-wide validator: render every prompt template in every
dojo pipeline against a synthetic loom context and report any
render failures.

This catches the class of bugs we hit during dojo create think
on 2026-05-30/31:

  1. ``upstream['gather'].vars.type``     — wrong attribute name
     on the upstream bag (loom exposes ``output``, not ``vars``).
  2. literal ``{% include %}`` in backticks — Jinja parses
     templates before markdown, so the literal must live inside
     ``{% raw %}...{% endraw %}``.
  3. ``upstream['create'].task_path``     — stale task id from a
     previous pipeline shape.

All three are caught by trying to render every template against
a context built from the actual plan, with synthetic stubs for
each upstream task's ``output.yaml`` derived from its
``output_schema``.

Run via ``dojo.sh check prompts``. Exits non-zero on any render
failure.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

import typer
import yaml

from dojo.utils import emit, fail
from dojo import plan as plan_mod
from loom.engine import store
from loom.errors import RenderFailed
from loom.render import jinja as loom_jinja

# ---------------------------------------------------------------------------
# Synthetic output stub generator — derives a schema-shaped value from a
# JSON Schema (YAML on disk). Sufficient for prompts that pluck individual
# keys from upstream outputs (the only pattern dojo prompts actually use).
# ---------------------------------------------------------------------------


def _stub_for_schema(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return ""
    t = schema.get("type")
    if isinstance(t, list):
        # Pick the first non-null type.
        t = next((x for x in t if x != "null"), "string")
    if t == "object":
        out: dict = {}
        for k, v in (schema.get("properties") or {}).items():
            out[k] = _stub_for_schema(v)
        return out
    if t == "array":
        items = schema.get("items") or {}
        return [_stub_for_schema(items)]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if t == "integer" or t == "number":
        return 0
    if t == "boolean":
        return False
    return "stub"


def _load_stub(schema_path: str | None) -> dict:
    if not schema_path:
        return {}
    p = Path(schema_path)
    if not p.exists():
        return {}
    try:
        schema = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    stub = _stub_for_schema(schema)
    return stub if isinstance(stub, dict) else {"value": stub}


# ---------------------------------------------------------------------------
# Per-pipeline prompt-render check
# ---------------------------------------------------------------------------


def _check_pipeline(pipeline_name: str, plan,
                    type_override: str | None = None) -> list[dict]:
    """Render every templated task in ``plan`` against synthetic
    upstream outputs. Returns a list of failure dicts.

    ``type_override`` (when set) replaces the synthetic
    ``gather.output.type`` value so dispatcher templates that
    branch on type get exercised in every branch.
    """
    failures: list[dict] = []
    label = pipeline_name + (f"[type={type_override}]"
                             if type_override else "")
    workdir = Path(tempfile.mkdtemp(
        prefix=f"dojo-check-prompts-{pipeline_name}-"))
    try:
        # Persist the plan so loom's store helpers can resolve task dirs.
        store.save_plan(workdir, plan)

        # Pre-write a stub output.yaml for every task so any downstream
        # task that reads upstream outputs sees a schema-shaped dict.
        for t in plan.tasks:
            stub = _load_stub(t.output_schema)
            # Inject the type override into gather-shaped stubs so the
            # design-prompt dispatcher branches every type at least
            # once across runs.
            if type_override and isinstance(stub, dict) and "type" in stub:
                # Only override on tasks whose schema enum includes the
                # override value (so we don't mutate unrelated tasks).
                stub_type = stub.get("type")
                if isinstance(stub_type, str):
                    stub["type"] = type_override
            store.ensure_task_dir(workdir, plan, t.id)
            # Write to loom's READ path: flat output.yaml for normal
            # tasks, iter-00/output.yaml for loop-body tasks (so
            # downstream refs to a loop-body task's output resolve).
            out_path = store.task_output_path(workdir, plan, t.id)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                yaml.safe_dump(stub, sort_keys=False),
                encoding="utf-8",
            )

        # Now render each task's template (if it has one).
        for t in plan.tasks:
            if not t.template:
                continue
            try:
                loom_jinja.render_task(t, workdir, plan)
            except RenderFailed as e:
                failures.append({
                    "pipeline":      label,
                    "task_id":       t.id,
                    "template_path": str(t.template),
                    "error":         str(e),
                })
            except Exception as e:  # pragma: no cover
                failures.append({
                    "pipeline":      label,
                    "task_id":       t.id,
                    "template_path": str(t.template),
                    "error":         f"unexpected: {type(e).__name__}: {e}",
                })
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return failures


def run() -> dict:
    """Render every prompt template across all three pipelines.

    Returns ``{ok, checked, failures}``. ``checked`` counts
    templated tasks; ``failures`` lists any render errors.
    """
    workdir = Path(tempfile.mkdtemp(prefix="dojo-check-prompts-build-"))
    try:
        plans = {
            "create": plan_mod.build_create_plan(workdir, "stub-skill"),
            "update": plan_mod.build_update_plan(workdir, "stub-skill"),
            "review": plan_mod.build_review_plan(workdir, "stub-skill"),
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    failures: list[dict] = []
    checked = 0
    # Skill types the design-prompt dispatcher must branch into.
    # Each pipeline gets rendered once per type so every branch is
    # exercised on every run.
    skill_types = ("interface", "tool", "workflow", "reference")
    for name, plan in plans.items():
        templated = sum(1 for t in plan.tasks if t.template)
        for t in skill_types:
            checked += templated
            failures.extend(_check_pipeline(name, plan, type_override=t))

    return {
        "ok":       not failures,
        "checked":  checked,
        "failures": failures,
    }


def cli_check() -> None:
    """``dojo.sh check prompts`` — render every prompt template
    in every pipeline; exit non-zero if any fails.
    """
    result = run()
    emit(result)
    if not result["ok"]:
        raise typer.Exit(code=1)
