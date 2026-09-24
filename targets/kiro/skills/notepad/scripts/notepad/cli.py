"""Typer CLI for the notepad skill.

Subcommands:
- `ingest`                       — start a fresh notepad session.
- `next` / `complete`            — thin wrappers over loom lifecycle.
- `pipeline setup-layout`        — tool-task body for setup-layout.
- `pipeline editor-open`         — tool-task body for editor-open.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml

import loom
from loom.errors import (
    LoomPlanError, OutputSchemaError, RenderFailed, RunAborted, RunFailed,
)

from notepad import pipeline
from notepad.plan import build_plan

# scripts/notepad/cli.py -> parents[2] is the notepad skill root.
SKILL_ROOT     = Path(__file__).resolve().parents[2]
SEED_TEMPLATE  = SKILL_ROOT / "templates" / "notepad.md.j2"

TEMPLATE_SH = (
    Path.home() / ".kiro" / "skills" / "home"
    / "template" / "scripts" / "render.sh"
)

# Ephemeral notebook root: /tmp/kiro-notebook-<uuid>/.
WORKDIR_PREFIX = Path("/tmp")

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


def _emit(obj) -> None:
    print(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True,
                         default_flow_style=False), end="")


def _fail(msg: str, **extra) -> None:
    print(yaml.safe_dump({"error": msg, **extra}, sort_keys=False),
          file=sys.stderr, end="")
    raise typer.Exit(code=1)


def _render_seed(target: Path, session_uuid: str, start_time: str) -> None:
    """Render templates/notepad.md.j2 -> notepad.md via the template skill."""
    vars_json = target.with_suffix(".vars.json")
    vars_json.write_text(json.dumps({
        "uuid":       session_uuid,
        "start_time": start_time,
    }))
    try:
        with target.open("w") as out:
            subprocess.run(
                [str(TEMPLATE_SH),
                 "--template", str(SEED_TEMPLATE),
                 "--json-vars", str(vars_json)],
                check=True, stdout=out, stderr=subprocess.PIPE,
            )
    finally:
        vars_json.unlink(missing_ok=True)


@app.command("ingest")
def cli_ingest() -> None:
    """`notepad.sh ingest` — start a fresh notepad session."""
    session_uuid = str(uuid.uuid4())
    wd = (WORKDIR_PREFIX / f"kiro-notebook-{session_uuid}").resolve()
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)

    try:
        plan = build_plan(wd, SKILL_ROOT)
        runtime = loom.init(workdir=wd, plan=plan)
    except LoomPlanError as e:
        _fail(f"plan validation failed: {e}")
    except Exception as e:
        _fail(f"ingest failed: {e}")

    start_time = datetime.now(timezone.utc).isoformat()
    try:
        _render_seed(wd / "notepad.md", session_uuid, start_time)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else ""
        shutil.rmtree(wd, ignore_errors=True)
        _fail(f"seed render failed: {stderr.strip() or e}")
    except Exception as e:
        shutil.rmtree(wd, ignore_errors=True)
        _fail(f"seed render failed: {e}")

    print(runtime.workdir)


@app.command("next")
def cli_next(
    workdir: str = typer.Argument(..., help="Loom workdir from ingest"),
) -> None:
    """`notepad.sh next <wd>` — advance internal tasks; emit ready batch."""
    wd = Path(workdir).expanduser().resolve()
    try:
        runtime = loom.resume(wd)
    except FileNotFoundError as e:
        _fail(str(e))

    try:
        action = runtime.next()
    except RunAborted as e:
        _fail(f"run aborted; failed tasks: {', '.join(e.failed_task_ids)}",
              failed_task_ids=e.failed_task_ids)
    except RunFailed as e:
        _fail(f"tool task failed: {e.task_id}",
              task_id=e.task_id, detail=e.message)
    except RenderFailed as e:
        _fail(f"prompt render failed: {e.task_id}",
              task_id=e.task_id,
              template_path=e.template_path,
              detail=e.message)
    except OutputSchemaError as e:
        _fail(f"output schema validation failed: {e.task_id}",
              task_id=e.task_id, detail=e.message)

    if action is None:
        if runtime.is_done():
            _emit({"done": True, "workdir": str(wd)})
        else:
            _emit({"done": False, "stuck": True,
                   "workdir": str(wd),
                   "summary": runtime.status_summary()})
        return

    runtime.commit_running([t["id"] for t in action.tasks])
    _emit({"done": False, "workdir": str(action.workdir),
           "ready": action.tasks})


@app.command("complete")
def cli_complete(
    workdir: str = typer.Argument(..., help="Loom workdir"),
    task_id: str = typer.Argument(..., help="Task id to mark complete"),
) -> None:
    """`notepad.sh complete <wd> <id>` — mark agent/human task done."""
    wd = Path(workdir).expanduser().resolve()
    try:
        runtime = loom.resume(wd)
    except FileNotFoundError as e:
        _fail(str(e))
    try:
        runtime.complete(task_id)
    except FileNotFoundError as e:
        _fail(str(e), task_id=task_id)
    except OutputSchemaError as e:
        _fail(f"output schema validation failed: {e.task_id}",
              task_id=e.task_id, detail=e.message)
    except (KeyError, ValueError) as e:
        _fail(str(e), task_id=task_id)
    _emit({"ok": True, "task_id": task_id, "workdir": str(wd)})


# --- pipeline: tool-task bodies invoked from loom ---
pipeline_app = typer.Typer(
    no_args_is_help=True, pretty_exceptions_enable=False,
    help="Pipeline-internal helpers (loom-invoked).",
)


@pipeline_app.command("setup-layout")
def cli_setup_layout(
    workdir: Path = typer.Option(..., "--workdir",
                                 help="Loom workdir"),
) -> None:
    """Tool-task body: build the standard 2-pane layout."""
    pipeline.setup_layout(workdir)


@pipeline_app.command("editor-open")
def cli_editor_open(
    workdir: Path = typer.Option(..., "--workdir",
                                 help="Loom workdir"),
    notepad: Path = typer.Option(..., "--notepad",
                                 help="Path to notepad.md"),
) -> None:
    """Tool-task body: open notepad.md in the EDITOR pane."""
    pipeline.editor_open(workdir, notepad)


app.add_typer(pipeline_app, name="pipeline")
