"""Runtime — thin wrappers over loom lifecycle.

Top-level CLI commands `ingest`, `next`, `complete`. Mirrors
dojo.runtime.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import loom
from loom.errors import (
    LoomPlanError, OutputSchemaError, RenderFailed, RunFailed, RunAborted,
)
import typer

from dojo.plan import derive_plan
from dojo.utils import emit, fail


# Workdir root. Each ingest creates `<root>/<op>/<skill-name>/`
# and loom owns everything underneath (tasks/, global/,
# plan.yaml). Op-namespaced so concurrent runs of `create`,
# `update`, and `review` against the same skill name do not
# collide.
WORKDIR_ROOT = Path("/tmp/dojo")


def _workdir_for(op: str, name: str) -> Path:
    """Workdir at `/tmp/dojo/<op>/<name>/`. Wipes any
    existing dir at the resolved path so re-runs start fresh.
    """
    wd = (WORKDIR_ROOT / op / name).resolve()
    if wd.exists():
        shutil.rmtree(wd)
    return wd


_VALID_OPS = {"create", "update", "review"}


def cli_ingest(
    op: str = typer.Option(
        ..., "--op",
        help="Operation: create | update | review"),
    name: str = typer.Option(
        ..., "--name", "-n",
        help="Skill name. For create: the desired kebab-case name. "
             "For update or review: an existing installed skill's name."),
) -> None:
    """`dojo.sh ingest --op create|update|review --name N` — start a run."""
    if op not in _VALID_OPS:
        fail(f"invalid --op: {op!r}; "
             f"expected one of {sorted(_VALID_OPS)}")
    try:
        wd = _workdir_for(op, name)
        wd.parent.mkdir(parents=True, exist_ok=True)
        plan = derive_plan(op, wd, name)
        runtime = loom.init(workdir=wd, plan=plan)
    except LoomPlanError as e:
        fail(f"plan validation failed: {e}")
    except Exception as e:
        fail(f"ingest failed: {e}")
    print(runtime.workdir)


def cli_next(
    workdir: str = typer.Argument(..., help="Loom workdir from ingest"),
) -> None:
    """`dojo.sh next <wd>` — advance internal tasks; emit ready batch."""
    wd = Path(workdir).expanduser().resolve()
    try:
        runtime = loom.resume(wd)
    except FileNotFoundError as e:
        fail(str(e))

    try:
        action = runtime.next()
    except RunAborted as e:
        fail(f"run aborted; failed tasks: {', '.join(e.failed_task_ids)}",
             failed_task_ids=e.failed_task_ids)
    except RunFailed as e:
        fail(f"tool task failed: {e.task_id}",
             task_id=e.task_id, detail=e.message)
    except RenderFailed as e:
        fail(f"prompt render failed: {e.task_id}",
             task_id=e.task_id,
             template_path=e.template_path,
             detail=e.message)
    except OutputSchemaError as e:
        fail(f"output schema validation failed: {e.task_id}",
             task_id=e.task_id, detail=e.message)

    if action is None:
        if runtime.is_done():
            emit({"done": True, "workdir": str(wd)})
        else:
            summary = runtime.status_summary()
            emit({"done": False, "stuck": True,
                  "workdir": str(wd), "summary": summary})
        return

    runtime.commit_running([t["id"] for t in action.tasks])

    emit({
        "done": False,
        "workdir": str(action.workdir),
        "ready": action.tasks,
    })


def cli_complete(
    workdir: str = typer.Argument(..., help="Loom workdir"),
    task_id: str = typer.Argument(..., help="Task id to mark complete"),
) -> None:
    """`dojo.sh complete <wd> <id>` — mark agent/human task done."""
    wd = Path(workdir).expanduser().resolve()
    try:
        runtime = loom.resume(wd)
    except FileNotFoundError as e:
        fail(str(e))

    try:
        runtime.complete(task_id)
    except FileNotFoundError as e:
        fail(str(e), task_id=task_id)
    except OutputSchemaError as e:
        fail(f"output schema validation failed: {e.task_id}",
             task_id=e.task_id, detail=e.message)
    except (KeyError, ValueError) as e:
        fail(str(e), task_id=task_id)

    emit({"ok": True, "task_id": task_id, "workdir": str(wd)})


def cli_status(
    workdir: str = typer.Argument(..., help="Loom workdir"),
) -> None:
    """`dojo.sh status <wd>` — emit a summary of plan state."""
    wd = Path(workdir).expanduser().resolve()
    try:
        runtime = loom.resume(wd)
    except FileNotFoundError as e:
        fail(str(e))
    emit({
        "workdir": str(wd),
        "done": runtime.is_done(),
        "summary": runtime.status_summary(),
    })
