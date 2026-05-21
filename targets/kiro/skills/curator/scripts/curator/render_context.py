"""Render-context builder.

Produces the schema-shaped dict described by
``templates/extractors/_meta/context-schema.yaml``. The dict is
passed to ``render.sh`` (via ``--json-vars``) as the complete
superset of variables a template might need. Templates take what
they want; the renderer's ``--allow-unused`` flag tolerates the
rest.

Design:
    - One context-builder per render call. The output is the entire
      contract between engine and templates — adding a new field
      lives in this file, not in plan factories.
    - Native Python types throughout. No leaf is a YAML-dumped
      string of structured data. The classify quintet, an upstream
      task's output, etc. all stay as dicts/lists.
    - Bounded scope. ``upstream`` carries only the current task's
      transitive ``depends_on``. ``peers`` is a pre-filtered list
      of agent extractor peers (no classify, no tool tasks).
"""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from engine import store
from engine.models import Plan, Task

from curator import quintet as _quintet


# Path to the package-local quintet vocabulary. Templates reference
# `quintet.path`; the classify extractor + judge `{% include %}` it
# directly via the renderer's --include-dir.
_QUINTET_PATH = Path(__file__).resolve().parent / "quintet.yaml"

# Skill root: <root>/scripts/curator/render_context.py → <root>/.
_SKILL_ROOT = Path(__file__).resolve().parent.parent.parent

# Schema document loaded once per process. Used to validate every
# context the engine builds before it reaches the renderer.
_SCHEMA_PATH = (
    _SKILL_ROOT / "templates" / "extractors" / "_meta" /
    "context-schema.yaml"
)


@functools.lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    return yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))

# Tool tasks that produce data exposed through the `source` bag.
# Their outputs are reachable as `source.fetched_path`,
# `source.converted_path`, etc., not via `upstream`.
_SOURCE_TOOL_IDS: frozenset[str] = frozenset({
    "fetch", "convert", "security_scan",
})


SCHEMA_VERSION = 1


def build_render_context(workdir: Path, task: Task, plan: Plan) -> dict[str, Any]:
    """Build the complete render context for ``task`` against the
    live ``plan``.

    Returned dict satisfies
    ``templates/extractors/_meta/context-schema.yaml``.
    The schema is enforced via ``jsonschema.validate`` before the
    dict is returned — a validation error is an engine bug (the
    context builder produced something the templates won't be able
    to read), not a user error, so it surfaces as
    ``ContextSchemaError``.
    """
    ctx: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "task":           _build_task(workdir, task, plan),
        "run":            _build_run(workdir),
        "quintet":        {"path": str(_QUINTET_PATH)},
        "templates": {
            "wiki_template_path":
                str(_SKILL_ROOT / "templates" / "vault" / "wiki.j2"),
            "vault_templates_dir":
                str(_SKILL_ROOT / "templates" / "vault"),
        },
    }

    # source — always present so templates can safely substitute
    # source.converted_path etc.; fields are null until convert
    # has produced output.
    ctx["source"] = _build_source(workdir, plan)

    # destinations — static, loaded from quintet.yaml. Normalize
    # each entry so `folder` is always present (null when not
    # applicable) — templates can `{% if dest.folder %}` without
    # tripping StrictUndefined on synthesis-mode entries that have
    # no folder key in the YAML.
    ctx["destinations"] = {
        kind: {"mode": dest["mode"], "folder": dest.get("folder")}
        for kind, dest in _quintet.destinations().items()
    }

    # upstream — every transitive dep with parsed output + verdict.
    # Always present as a dict (possibly empty) so templates can
    # safely test ``upstream.<id> is defined`` without first
    # checking whether `upstream` itself exists.
    deps = _transitive_deps(plan, task.id)
    ctx["upstream"] = {
        dep_id: _build_upstream(workdir, dep_id, plan)
        for dep_id in deps
    }

    # peers — pre-filtered agent extractor peers (no classify,
    # no tool tasks). Order matches the depends_on chain so the
    # rendered prompt is deterministic.
    ctx["peers"] = [
        ctx["upstream"][dep_id]
        for dep_id in deps
        if ctx["upstream"][dep_id]["kind"] == "agent"
        and dep_id != "classify"
    ]

    _validate(ctx)
    return ctx


class ContextSchemaError(RuntimeError):
    """Raised when the engine builds a render context that does not
    satisfy the schema. This is an engine bug, not a user error —
    surface it loudly so it can't be silently swallowed."""


def _validate(ctx: dict[str, Any]) -> None:
    try:
        jsonschema.validate(ctx, _schema())
    except jsonschema.ValidationError as e:
        path = "/".join(str(p) for p in e.absolute_path)
        raise ContextSchemaError(
            f"render context fails schema at {path!r}: {e.message}"
        ) from e


# ── per-bag builders ──────────────────────────────────────


def _build_task(workdir: Path, task: Task, plan: Plan) -> dict[str, Any]:
    """Schema's `task` bag.

    Paths follow the symmetric pair pattern:
      extractor: prompt_path → output_path
      judge:     judge_prompt_path → judge_output_path
    """
    task_dir = store.task_dir(workdir, task.id, plan=plan)
    has_extractor = task.kind == "agent" and task.template
    has_judge = task.kind == "agent" and task.judge is not None

    return {
        "id":        task.id,
        "kind":      task.kind,
        "template":  task.template,
        "agent_role": task.agent,
        "workdir":   str(task_dir),
        "prompt_path":
            str(task_dir / "extractor-prompt.md") if has_extractor else None,
        "output_path":
            str(task_dir / "output.yaml"),
        "judge_prompt_path":
            str(task_dir / "judge-prompt.md") if has_judge else None,
        "judge_output_path":
            str(task_dir / "verdict.yaml") if has_judge else None,
        "depends_on": list(task.depends_on),
    }


def _build_run(workdir: Path) -> dict[str, Any]:
    """Schema's `run` bag. ``origin`` and ``ingested_at`` are derived
    from the fetch task's output if it has run, else null.
    """
    return {
        "workdir":      str(workdir),
        "basename":     workdir.name,
        "replica_root": str(workdir / "vault-replica"),
        "origin":       None,    # populated below if fetch is done
        "ingested_at":  None,    # populated below if fetch is done
    }


def _build_source(workdir: Path, plan: Plan) -> dict[str, Any]:
    """Schema's `source` bag. Always present; inner fields are
    null until convert/fetch/security_scan have produced output.

    Reads:
      - fetch's       output.yaml → fetched_path (raw file path)
                                     + vault_path (vault-relative)
      - convert's     output.yaml → converted_path + container_metadata
      - security_scan's output.yaml → security_scan
    """
    convert_out = _load_task_output(workdir, "convert", plan) or {}
    fetch_out   = _load_task_output(workdir, "fetch",   plan) or {}
    sec_out     = _load_task_output(workdir, "security_scan", plan) or {}

    fetched_path = fetch_out.get("path")
    vault_path: str | None = None
    if isinstance(fetched_path, str) and fetched_path:
        # Lazy import to avoid pulling vault config into the
        # render context module's import surface.
        from curator.vault.pages import VAULT_ROOT
        try:
            vault_path = str(
                Path(fetched_path).resolve().relative_to(VAULT_ROOT))
        except (ValueError, OSError):
            # fetched_path lives outside the vault (shouldn't
            # happen for production fetch handlers, but don't
            # let it crash render).
            vault_path = None

    return {
        "fetched_path":      fetched_path,
        "vault_path":        vault_path,
        "converted_path":    convert_out.get("converted_path"),
        "container_metadata": convert_out.get("metadata") or {},
        "security_scan":     sec_out,
    }


def _build_upstream(workdir: Path, task_id: str, plan: Plan) -> dict[str, Any]:
    """One entry under `upstream`. Always populates ``output`` and
    ``verdict`` (latter is null if no judge stage)."""
    task = plan.get(task_id)
    task_dir = store.task_dir(workdir, task_id, plan=plan)
    output = _load_task_output(workdir, task_id, plan)

    verdict_path = task_dir / "verdict.yaml"
    verdict: Any = None
    if verdict_path.exists():
        try:
            verdict = yaml.safe_load(
                verdict_path.read_text(encoding="utf-8"))
        except Exception:
            verdict = None

    return {
        "task_id":      task_id,
        "kind":         task.kind,
        "status":       task.status,
        "output":       output,
        "verdict":      verdict,
        "task_path":    str(task_dir / "output.yaml"),
        "verdict_path":
            str(verdict_path) if verdict is not None or task.judge else None,
    }


# ── helpers ───────────────────────────────────────────────


def _transitive_deps(plan: Plan, task_id: str) -> list[str]:
    """Return all transitive dependencies of ``task_id`` in
    topological order. Excludes ``task_id`` itself.
    """
    by_id = {t.id: t for t in plan.tasks}
    seen: set[str] = set()
    out: list[str] = []

    def walk(tid: str) -> None:
        if tid in seen:
            return
        seen.add(tid)
        node = by_id.get(tid)
        if node is None:
            return
        for d in node.depends_on:
            walk(d)
        if tid != task_id:
            out.append(tid)

    walk(task_id)
    return out


def _load_task_output(workdir: Path, task_id: str,
                       plan: Plan) -> dict[str, Any] | None:
    """Load <wd>/tasks/<NN-id>/output.yaml; return None if missing
    or unparseable."""
    try:
        p = store.task_output_path(workdir, task_id, plan=plan)
    except KeyError:
        return None
    if not p.exists():
        return None
    try:
        loaded = yaml.safe_load(p.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else None
    except Exception:
        return None
