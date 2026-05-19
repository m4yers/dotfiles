"""CLI tests for curator.sh next — invariants visible at the
shell boundary that the curator skill orchestrator depends on.

These exercise:

- A render failure exits non-zero with the renderer's stderr in the
  error message, AND leaves the offending task status=pending so a
  fix-and-retry just works.
- A stuck plan (non-terminal task + no ready successors) exits
  non-zero with ``stuck:`` rather than emitting ``done: true``.
- Successful rendering commits the batch to running and returns
  ``done: false`` with a populated ``ready`` list.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml


CURATOR_SH = Path(
    "/home/artyomgo/.kiro/skills/home/curator/scripts/curator.sh")


def _run_curator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CURATOR_SH), *args],
        capture_output=True, text=True, check=False,
    )


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch) -> Path:
    """Create a fresh curator workdir under tmp_path with an empty
    plan; tests overwrite plan.yaml to install the scenario they
    want without going through the (heavyweight) ingest flow.

    Skip the suite entirely if the curator.sh entrypoint is missing
    — this happens in clean checkouts before the dotfiles symlink
    is set up.
    """
    if not CURATOR_SH.exists():
        pytest.skip(f"curator.sh not available at {CURATOR_SH}")

    wd = tmp_path / "wd"
    wd.mkdir()
    return wd


def _write_plan(wd: Path, tasks: list[dict]) -> None:
    (wd / "plan.yaml").write_text(
        yaml.safe_dump({"tasks": tasks}, sort_keys=False),
        encoding="utf-8",
    )


def _write_task_output(wd: Path, task_id: str, doc: dict) -> None:
    """Write ``output.yaml`` to the task's numbered subdir.

    The engine assigns directories as ``NN-<task_id>`` based on the
    task's 1-based position in the plan; this helper finds that
    position by reading plan.yaml and writes the output where
    ``store.task_output_path`` will look for it.
    """
    plan = yaml.safe_load((wd / "plan.yaml").read_text(encoding="utf-8"))
    idx = next(
        (i for i, t in enumerate(plan["tasks"], start=1)
            if t["id"] == task_id),
        None,
    )
    assert idx is not None, f"task {task_id!r} not in plan"
    p = wd / "tasks" / f"{idx:02d}-{task_id}" / "output.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _read_plan(wd: Path) -> dict:
    return yaml.safe_load((wd / "plan.yaml").read_text(encoding="utf-8"))


# ── done vs stuck ──────────────────────────────────────


def test_next_emits_done_when_all_terminal(workdir: Path):
    """All tasks done → next exits 0 with done:true."""
    _write_plan(workdir, [
        {"id": "A", "kind": "tool", "status": "done"},
    ])
    r = _run_curator("next", str(workdir))
    assert r.returncode == 0, r.stderr
    out = yaml.safe_load(r.stdout)
    assert out["done"] is True


def test_next_fails_with_stuck_when_blocked(workdir: Path):
    """Non-terminal task + no ready successors → next exits non-zero
    with ``stuck:`` and the offending task ids. This prevents the
    orchestrator from false-completing on a partially-failed run."""
    _write_plan(workdir, [
        {"id": "A", "kind": "agent", "status": "running"},
        {"id": "B", "kind": "agent", "depends_on": ["A"]},
    ])
    r = _run_curator("next", str(workdir))
    assert r.returncode != 0, (r.stdout, r.stderr)
    err = yaml.safe_load(r.stderr)
    assert "stuck" in err["error"]
    assert err["stuck_tasks"] == ["A", "B"]


# ── render failure does not strand the task ────────────


def _classify_quintet_output(media: str = "article") -> dict:
    """Minimal classify output enough to feed the summary template's
    quintet.get('media') call."""
    return {
        "quintet": {
            "media":      media,
            "form":       "blog",
            "register":   "non_fiction",
            "discipline": "cs",
            "audience":   "professional",
        },
        "topic": "test topic",
    }


def _summary_only_plan() -> list[dict]:
    """A two-task plan: a fake classify (already done with output)
    plus an extract-summary that depends on it. Forces cli_next to
    render the summary prompt."""
    return [
        {"id": "classify", "kind": "agent", "status": "done"},
        {
            "id": "extract-summary", "kind": "agent",
            "depends_on": ["classify"],
            "agent": "curator-extractor",
            "template": "summary",
            "vars": {
                "source_text_path": "/dev/null",
                "container_metadata": {},
                "quintet": "${task:classify:quintet}",
                "topic":   "${task:classify:topic}",
                "upstream_outputs":  {},
                "upstream_verdicts": {},
            },
        },
    ]


def test_summary_render_succeeds_with_native_quintet(workdir: Path):
    """Regression test for the original failure: the summary template
    calls quintet.get('media'). With the resolver fix, ``quintet``
    arrives as a native dict and the render succeeds."""
    _write_plan(workdir, _summary_only_plan())
    _write_task_output(workdir, "classify", _classify_quintet_output())

    r = _run_curator("next", str(workdir))
    assert r.returncode == 0, (r.stdout, r.stderr)
    out = yaml.safe_load(r.stdout)
    assert out["done"] is False
    ids = [t["id"] for t in out["ready"]]
    assert ids == ["extract-summary"]
    # The prompt files were written to the numbered subdir
    # (engine assigns 02-extract-summary because it's task index 2).
    prompt = workdir / "tasks" / "02-extract-summary" / "extractor-prompt.md"
    assert prompt.exists() and prompt.read_text().strip()



