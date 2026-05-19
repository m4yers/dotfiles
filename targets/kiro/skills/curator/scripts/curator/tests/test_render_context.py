"""Tests for the render-context builder.

Verifies that ``build_render_context`` produces a dict that:

- Validates against ``templates/extractors/_meta/context-schema.yaml``.
- Carries native Python types end-to-end (no YAML-stringified
  blobs).
- Includes only the transitive depends_on chain under ``upstream``.
- Filters ``peers`` to agent extractors, excluding classify and
  tool tasks.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engine import EngineRun, store, algorithm
from engine.models import Plan, Task

from curator.render_context import build_render_context


# Optional dependency — skip schema validation tests if absent.
jsonschema = pytest.importorskip("jsonschema")


_SCHEMA_PATH = (
    Path(__file__).resolve()
    .parent.parent.parent.parent  # tests → curator → scripts → skill root
    / "templates" / "extractors" / "_meta" / "context-schema.yaml"
)


@pytest.fixture
def schema():
    return yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _start_run(tmp_path: Path, tasks: list[Task]) -> EngineRun:
    return EngineRun.start(
        base_dir=tmp_path,
        basename="rc-test",
        plan_factory=lambda _wd: Plan(tasks=tasks),
    )


def _write_done(run: EngineRun, task_id: str, doc: dict) -> None:
    plan = store.load_plan(run.workdir)
    out = store.task_output_path(run.workdir, task_id, plan=plan)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    algorithm.mark_done(plan, task_id)
    store.save_plan(run.workdir, plan)


def _write_verdict(run: EngineRun, task_id: str, doc: dict) -> None:
    plan = store.load_plan(run.workdir)
    td = store.task_dir(run.workdir, task_id, plan=plan)
    td.mkdir(parents=True, exist_ok=True)
    (td / "verdict.yaml").write_text(
        yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


# ── shape + schema validation ─────────────────────────


def test_minimal_context_validates(tmp_path: Path, schema):
    """A trivial single-task plan produces a schema-valid context."""
    run = _start_run(tmp_path, [Task(id="solo", kind="agent")])
    plan = store.load_plan(run.workdir)
    ctx = build_render_context(run.workdir, plan.get("solo"), plan)

    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(ctx, schema)


def test_context_carries_required_top_level_keys(tmp_path: Path):
    run = _start_run(tmp_path, [Task(id="solo", kind="agent")])
    plan = store.load_plan(run.workdir)
    ctx = build_render_context(run.workdir, plan.get("solo"), plan)

    for key in ("schema_version", "task", "run", "quintet"):
        assert key in ctx, f"missing required key {key!r}"
    assert ctx["schema_version"] == 1


def test_task_bag_uses_renamed_paths(tmp_path: Path):
    """Per the schema renames: workdir, prompt_path, output_path,
    judge_prompt_path, judge_output_path. No old aliases."""
    run = _start_run(tmp_path, [
        Task(id="solo", kind="agent",
             template="summary",
             agent="curator-extractor",
             judge={"template": "summary",
                    "agent": "curator-judge"}),
    ])
    plan = store.load_plan(run.workdir)
    ctx = build_render_context(run.workdir, plan.get("solo"), plan)

    t = ctx["task"]
    assert t["id"] == "solo"
    assert t["kind"] == "agent"
    assert t["template"] == "summary"
    assert t["agent_role"] == "curator-extractor"
    assert t["workdir"].endswith("/01-solo")
    assert t["prompt_path"].endswith("/extractor-prompt.md")
    assert t["output_path"].endswith("/output.yaml")
    assert t["judge_prompt_path"].endswith("/judge-prompt.md")
    assert t["judge_output_path"].endswith("/verdict.yaml")
    # Old aliases must not leak.
    assert "task_workdir" not in t
    assert "extractor_prompt_path" not in t
    assert "verdict_path" not in t


# ── upstream + peers contracts ────────────────────────


def test_upstream_native_types(tmp_path: Path):
    """Upstream output is the parsed YAML — native dict, NOT a
    YAML-dumped string. Regression test for the resolver bug."""
    run = _start_run(tmp_path, [
        Task(id="classify", kind="agent"),
        Task(id="extract-summary", kind="agent",
             depends_on=["classify"]),
    ])
    _write_done(run, "classify", {
        "quintet": {"media": "article", "form": "blog",
                    "register": "non_fiction",
                    "discipline": "cs", "audience": "professional"},
        "topic": "test topic",
    })

    plan = store.load_plan(run.workdir)
    ctx = build_render_context(
        run.workdir, plan.get("extract-summary"), plan)

    classify_up = ctx["upstream"]["classify"]
    assert isinstance(classify_up["output"]["quintet"], dict)
    assert classify_up["output"]["quintet"]["media"] == "article"
    assert classify_up["output"]["topic"] == "test topic"


def test_upstream_only_transitive_deps(tmp_path: Path):
    """upstream excludes tasks not in the current task's transitive
    depends_on — even if they exist in the plan."""
    run = _start_run(tmp_path, [
        Task(id="A", kind="agent"),
        Task(id="B", kind="agent"),
        Task(id="C", kind="agent", depends_on=["A"]),
    ])
    _write_done(run, "A", {})
    _write_done(run, "B", {})

    plan = store.load_plan(run.workdir)
    ctx = build_render_context(run.workdir, plan.get("C"), plan)

    assert "A" in ctx["upstream"]
    assert "B" not in ctx["upstream"]


def test_peers_excludes_classify_and_tools(tmp_path: Path):
    """peers contains only agent extractors that are not classify
    and not stage-1 tool plumbing. Order matches the depends_on
    walk."""
    run = _start_run(tmp_path, [
        Task(id="fetch", kind="tool"),
        Task(id="convert", kind="tool", depends_on=["fetch"]),
        Task(id="classify", kind="agent", depends_on=["convert"]),
        Task(id="extract-keywords", kind="agent",
             depends_on=["classify"]),
        Task(id="extract-people", kind="agent",
             depends_on=["classify"]),
        Task(id="summary", kind="agent",
             depends_on=["extract-keywords", "extract-people",
                          "classify"]),
    ])
    for tid in ("fetch", "convert"):
        _write_done(run, tid, {})
    _write_done(run, "classify", {"quintet": {}, "topic": "t"})
    _write_done(run, "extract-keywords", {"keywords": []})
    _write_done(run, "extract-people", {"people": []})

    plan = store.load_plan(run.workdir)
    ctx = build_render_context(run.workdir, plan.get("summary"), plan)

    peer_ids = [p["task_id"] for p in ctx["peers"]]
    assert peer_ids == ["extract-keywords", "extract-people"]
    # classify and tool tasks excluded
    assert "classify" not in peer_ids
    assert "convert" not in peer_ids
    assert "fetch" not in peer_ids


# ── source bag ────────────────────────────────────────


def test_source_always_present_fields_null_until_convert_done(tmp_path: Path):
    """The source bag is always part of the schema, but its inner
    fields are null until the relevant tool task has produced
    output."""
    run = _start_run(tmp_path, [
        Task(id="fetch", kind="tool"),
        Task(id="convert", kind="tool", depends_on=["fetch"]),
        Task(id="classify", kind="agent", depends_on=["convert"]),
    ])
    plan = store.load_plan(run.workdir)
    ctx_before = build_render_context(
        run.workdir, plan.get("classify"), plan)
    # source bag is present even though convert hasn't run.
    assert "source" in ctx_before
    assert ctx_before["source"]["fetched_path"] is None
    assert ctx_before["source"]["converted_path"] is None

    _write_done(run, "fetch", {"path": "/tmp/foo.html"})
    _write_done(run, "convert", {
        "converted_path": "/tmp/foo.md",
        "metadata": {"author": "alice"},
    })
    plan = store.load_plan(run.workdir)
    ctx_after = build_render_context(
        run.workdir, plan.get("classify"), plan)
    assert ctx_after["source"]["fetched_path"] == "/tmp/foo.html"
    assert ctx_after["source"]["converted_path"] == "/tmp/foo.md"
    assert ctx_after["source"]["container_metadata"] == {"author": "alice"}


# ── verdict round-trip ────────────────────────────────


def test_verdict_loaded_when_present(tmp_path: Path):
    run = _start_run(tmp_path, [
        Task(id="classify", kind="agent"),
        Task(id="extract-keywords", kind="agent",
             depends_on=["classify"]),
    ])
    _write_done(run, "classify", {"quintet": {}, "topic": "t"})
    _write_verdict(run, "classify", {
        "verdict": "ACCEPT",
        "reasoning": "looks good",
    })
    plan = store.load_plan(run.workdir)
    ctx = build_render_context(
        run.workdir, plan.get("extract-keywords"), plan)

    assert ctx["upstream"]["classify"]["verdict"]["verdict"] == "ACCEPT"
    assert (
        ctx["upstream"]["classify"]["verdict"]["reasoning"]
        == "looks good"
    )
