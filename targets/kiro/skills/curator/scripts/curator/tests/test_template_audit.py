"""End-to-end render check for every extractor kind.

For each ``templates/extractors/<kind>/`` (excluding ``_meta``):

1. Build a render context against a synthesised plan that gives the
   template every dependency it could reasonably need (full DAG:
   fetch / convert / security_scan / classify / every extract-* /
   summary / synthesis).
2. Render both the extractor and judge prompts.

The test is intentionally noisy: each kind it can't render shows up
as its own failure with the renderer's stderr surfaced, so a schema-
template mismatch is unambiguous.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engine import EngineRun, algorithm, store
from engine.models import Plan, Task

from curator import prompts as P


_EXTRACTORS_DIR = (
    Path(__file__).resolve().parent.parent.parent  # scripts/
    .parent  # curator (skill root)
    / "templates" / "extractors"
)


def _all_extractor_kinds() -> list[str]:
    return sorted(
        d.name for d in _EXTRACTORS_DIR.iterdir()
        if d.is_dir() and d.name != "_meta"
        and (d / "extractor.j2").exists()
    )


@pytest.fixture
def workdir_with_full_plan(tmp_path: Path) -> tuple[EngineRun, str]:
    """A workdir whose plan covers every dependency a kid template
    might transitively read: fetch / convert / security_scan /
    classify / extract-summary, plus a placeholder agent task that
    declares every other kind as a dep so its render context
    includes them all in upstream/peers.
    """
    kinds = _all_extractor_kinds()
    # Build the plan: stage1 + every extractor-kind task + a probe
    # task that depends on all of them so its render context sees a
    # rich `upstream` / `peers` bag.
    stage1 = [
        Task(id="fetch",         kind="tool"),
        Task(id="convert",       kind="tool", depends_on=["fetch"]),
        Task(id="security_scan", kind="tool", depends_on=["convert"]),
        Task(id="classify",      kind="agent",
             template="classify",
             agent="curator-extractor",
             judge={"template": "classify", "agent": "curator-judge"},
             depends_on=["convert", "security_scan"]),
    ]
    extract_tasks = [
        Task(id=f"extract-{k}", kind="agent",
             template=k,
             agent="curator-extractor",
             judge={"template": k, "agent": "curator-judge"},
             depends_on=["classify", "convert"])
        for k in kinds if k not in ("classify", "synthesis")
    ]
    # Synthesis depends on every other extractor so its render
    # context's upstream contains the full universe.
    synth = Task(
        id="synthesis", kind="agent",
        template="synthesis",
        agent="curator-composer",
        judge={"template": "synthesis", "agent": "curator-judge"},
        depends_on=[t.id for t in extract_tasks] + ["classify"],
    )

    run = EngineRun.start(
        base_dir=tmp_path,
        basename="audit",
        plan_factory=lambda _wd: Plan(tasks=stage1 + extract_tasks + [synth]),
    )

    # Mark stage1 + every extractor task as done with realistic output.
    plan = store.load_plan(run.workdir)
    for tid, doc in [
        ("fetch",         {"path": "/tmp/foo.html"}),
        ("convert",       {"converted_path": "/tmp/foo.md",
                            "metadata": {"author": "alice"}}),
        ("security_scan", {"findings": []}),
        ("classify",      {"quintet": {"media": "article",
                                          "form": "blog",
                                          "register": "non_fiction",
                                          "discipline": "cs",
                                          "audience": "professional"},
                            "topic":   "test topic"}),
        ("extract-summary", {"summary": "x" * 100}),
    ]:
        td = store.task_dir(run.workdir, tid, plan=plan)
        td.mkdir(parents=True, exist_ok=True)
        (td / "output.yaml").write_text(
            yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        algorithm.mark_done(plan, tid)
    store.save_plan(run.workdir, plan)
    return run, "synthesis"


@pytest.mark.parametrize("kind", _all_extractor_kinds())
def test_render_extractor(kind: str, workdir_with_full_plan):
    """Each kind's extractor + judge must render cleanly against
    the full-plan context."""
    run, _ = workdir_with_full_plan
    plan = store.load_plan(run.workdir)
    # Use a real task whose template == kind to source paths from.
    target_id = f"extract-{kind}" if kind not in ("classify", "synthesis") else kind
    task = plan.get(target_id)
    td = store.ensure_task_dir(run.workdir, task.id, plan=plan)
    task_dict = {
        "id":           task.id,
        "task_workdir": str(td),
        "output_path":  str(td / "output.yaml"),
        "template":     task.template,
        "judge":        task.judge if isinstance(task.judge, dict) else None,
    }
    P.render_agent_prompts(run, task_dict)
    # Both prompt files were written.
    assert (td / "extractor-prompt.md").exists()
    assert (td / "judge-prompt.md").exists()
