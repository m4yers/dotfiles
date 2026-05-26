"""Runtime — thin wrappers over loom lifecycle.

Top-level CLI commands `ingest`, `next`, `complete` that drive
the loom DAG. Mirrors curator.runtime.
"""
from __future__ import annotations

import datetime
import shutil
from pathlib import Path
from typing import Optional

import loom
from loom.errors import (
    LoomPlanError, OutputSchemaError, RenderFailed, RunFailed,
)

from skill_reviewer.plan import derive_plan
from skill_reviewer.utils import emit, fail


# Workdirs live under /tmp; ephemeral by design.
WORKDIR_ROOT = Path("/tmp/skill-reviewer")


def _workdir_for(name: str) -> Path:
    """Date-prefixed workdir.

    `<root>/<YYYY-MM-DD>/<name>/`. Wipes any existing dir at the
    resolved path so re-runs start fresh.
    """
    today = datetime.date.today().isoformat()
    wd = (WORKDIR_ROOT / today / name).resolve()
    if wd.exists():
        shutil.rmtree(wd)
    return wd


def cli_ingest(
    name: str,
    category: Optional[str] = None,
) -> None:
    """`$REVIEWER ingest <name> [--category C]` — start a review."""
    try:
        wd = _workdir_for(name)
        wd.parent.mkdir(parents=True, exist_ok=True)
        plan = derive_plan(name, category)
        runtime = loom.init(workdir=wd, plan=plan)
    except LoomPlanError as e:
        fail(f"plan validation failed: {e}")
    except Exception as e:
        fail(f"ingest failed: {e}")
    print(runtime.workdir)


def cli_next(workdir: str) -> None:
    """`$REVIEWER next <wd>` — advance internal tasks; emit ready batch."""
    wd = Path(workdir).expanduser().resolve()
    try:
        runtime = loom.resume(wd)
    except FileNotFoundError as e:
        fail(str(e))

    try:
        action = runtime.next()
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


def cli_complete(workdir: str, task_id: str) -> None:
    """`$REVIEWER complete <wd> <id>` — mark agent/human task done."""
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
