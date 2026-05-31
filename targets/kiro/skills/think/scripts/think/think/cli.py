"""CLI surface for the think skill.

Subcommands:

- `ingest --question <text> [--context <text>]` — initialise a
  fresh loom workdir and print its path.
- `next <workdir>` — emit the ready-task batch via loom's
  Python API (mirrors dojo's runtime).
- `complete <workdir> <task-id>` — mark a task complete and
  validate its output via loom's Python API.
- `output <init|add> ...` — proxy to `loom.sh output` so
  sub-agents can build schema-valid YAML.
- `pipeline rank <workdir>` — tool-task body that aggregates
  the three pair-wise comparisons into a Copeland-weighted
  ranking. Loom invokes this; users normally do not.
- `report <workdir>` — render the user-facing markdown report
  from the rank output and print its path.

Design deviation: the design proposed shelling out to
`$LOOM_SH` for `ingest`/`next`/`complete`. Loom's shell
entrypoint exposes only `output` and `visualise`, so those
three subcommands cannot shell out — they must use the
Python API. `cli_ingest`, `cli_next`, and `cli_complete`
therefore call `loom.init`, `loom.resume`, `runtime.next`,
and `runtime.complete` directly, mirroring how dojo's own
runtime drives loom. `output` still shells out via
`_loom_sh()` so sub-agents can use the schema-validated
writer.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import typer
import yaml

from think import plan as plan_mod
from think import rank as rank_mod
from think import report as report_mod

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


# Workdirs are namespaced by question slug under /tmp/think.
# Slugged so concurrent runs against different questions do
# not collide and each run is human-identifiable on disk.
WORKDIR_ROOT = Path("/tmp/think")

# Maximum slug length before truncation. 48 is enough to make
# the slug recognisable when listing /tmp/think but short
# enough to keep absolute paths well under typical 4 KB shell
# limits.
_MAX_SLUG_LEN = 48


def _loom_sh() -> str:
    """Resolve the loom shim path. Honour `$LOOM_SH` if set
    (mirrors how dojo's runtime resolves it); otherwise fall
    back to `$SKILLS/home/loom/scripts/loom.sh` so a
    user-overridden install path is respected.
    """
    env = os.environ.get("LOOM_SH")
    if env:
        return env
    skills_root = Path(
        os.environ.get("SKILLS",
                       os.path.expanduser("~/.kiro/skills")))
    return str(skills_root / "home" / "loom" / "scripts" / "loom.sh")


def _slugify(text: str) -> str:
    """Lowercase, replace runs of non-alnum with '-', trim.

    Used to derive a workdir name from the user's question so
    `/tmp/think/<slug>/` is identifiable when several runs
    coexist.
    """
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    s = s.strip("-")
    if not s:
        # Pure-symbol or empty inputs fall back to a stable
        # placeholder; ingest re-checks --question is non-empty
        # before this is reached.
        s = "question"
    return s[:_MAX_SLUG_LEN]


def _workdir_for(question: str) -> Path:
    """Resolve `/tmp/think/<slug>/`. Wipes any existing dir
    so re-runs start fresh — matches dojo's runtime contract
    so the orchestrator can re-invoke ingest idempotently.
    """
    wd = (WORKDIR_ROOT / _slugify(question)).resolve()
    if wd.exists():
        shutil.rmtree(wd)
    return wd


def _emit(payload: dict) -> None:
    """Write a YAML dict to stdout. Matches dojo.utils.emit."""
    yaml.safe_dump(payload, sys.stdout, sort_keys=False)


def _fail(message: str, **fields) -> None:
    """Print a YAML error envelope to stderr and exit non-zero."""
    payload = {"error": message, **fields}
    yaml.safe_dump(payload, sys.stderr, sort_keys=False)
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Top-level loop driver — ingest / next / complete via loom Python API.
# ---------------------------------------------------------------------------

def _escape_for_loom_vars(text: str) -> str:
    """Escape `$` to `$$` so user-supplied text passes loom's
    static placeholder validation untouched.

    User input flows into the rubric task's `vars` dict, which
    loom both statically validates and resolves at render time.
    Any literal `${task:id:...}` or `${workdir}` in the user's
    question or context (legitimate when the question is about
    loom itself) would otherwise be interpreted as a placeholder
    reference. Loom's resolver treats `$$` as the literal-`$`
    escape — see `_PLACEHOLDER_RE` and `_ESCAPE_RE` in
    `loom/engine/resolve.py` — so `$$` round-trips back to `$`
    in the rendered prompt and the LLM sees the user's exact
    text.
    """
    return text.replace("$", "$$")


@app.command("ingest")
def cli_ingest(
    question: str = typer.Option(
        ..., "--question", "-q",
        help="The complex question to think about. "
             "Required and must be non-empty."),
    context: str = typer.Option(
        "", "--context", "-c",
        help="Optional orchestrator-supplied summary of the "
             "active session, used to bias rubric weights "
             "toward what matters for THIS question."),
) -> None:
    """`think.sh ingest --question Q [--context C]` — start a run."""
    if not question.strip():
        _fail("--question must not be empty")

    wd = _workdir_for(question)
    wd.parent.mkdir(parents=True, exist_ok=True)

    # Escape `$` in user-supplied text so a literal `${task:...}`
    # in the question or context (e.g. asking about loom itself)
    # is not interpreted as a placeholder reference by loom's
    # static validator. The resolver unescapes `$$` back to `$`
    # at render time, so the LLM still sees the user's exact text.
    safe_question = _escape_for_loom_vars(question)
    safe_context  = _escape_for_loom_vars(context)

    try:
        loom_plan = plan_mod.build_plan(wd, safe_question, safe_context)
    except Exception as e:
        _fail(f"plan build failed: {e}")

    try:
        import loom
        loom.init(workdir=wd, plan=loom_plan)
    except Exception as e:
        _fail(f"loom.init failed: {e}")

    print(wd)


@app.command("next")
def cli_next(
    workdir: str = typer.Argument(..., help="Loom workdir from ingest"),
) -> None:
    """Advance the plan; emit the next ready batch as YAML."""
    import loom
    from loom.errors import (
        OutputSchemaError, RenderFailed, RunFailed, RunAborted,
    )

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
            _emit({
                "done": False,
                "stuck": True,
                "workdir": str(wd),
                "summary": runtime.status_summary(),
            })
        return

    runtime.commit_running([t["id"] for t in action.tasks])
    _emit({
        "done": False,
        "workdir": str(action.workdir),
        "ready": action.tasks,
    })


@app.command("complete")
def cli_complete(
    workdir: str = typer.Argument(..., help="Loom workdir"),
    task_id: str = typer.Argument(..., help="Task id to mark complete"),
) -> None:
    """Mark agent/human task done; validate its output.yaml."""
    import loom
    from loom.errors import OutputSchemaError

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


# ---------------------------------------------------------------------------
# output — proxy to `loom output` so sub-agents can build schema-valid YAML.
# ---------------------------------------------------------------------------

output_app = typer.Typer(
    no_args_is_help=True, pretty_exceptions_enable=False,
    help="Proxy to `loom output` for schema-validated task outputs.",
)


@output_app.command("init")
def cli_output_init(
    workdir: str = typer.Argument(...),
    task: str = typer.Option(..., "--task"),
) -> None:
    rc = subprocess.run(
        [_loom_sh(), "output", "init", workdir, "--task", task],
        check=False,
    ).returncode
    raise typer.Exit(rc)


@output_app.command("add")
def cli_output_add(
    workdir: str = typer.Argument(...),
    task: str = typer.Option(..., "--task"),
    set_pairs: list[str] = typer.Option(
        ..., "--set",
        help="Repeatable dotted-path = value assignments."),
) -> None:
    cmd = [_loom_sh(), "output", "add", workdir, "--task", task]
    for pair in set_pairs:
        cmd += ["--set", pair]
    rc = subprocess.run(cmd, check=False).returncode
    raise typer.Exit(rc)


app.add_typer(output_app, name="output")


# ---------------------------------------------------------------------------
# pipeline rank — deterministic tool-task body for the rank task.
# ---------------------------------------------------------------------------

pipeline_app = typer.Typer(
    no_args_is_help=True, pretty_exceptions_enable=False,
    help="Tool-task entrypoints invoked by loom.",
)


@pipeline_app.command("rank")
def cli_pipeline_rank(
    workdir: str = typer.Argument(..., help="Loom workdir"),
) -> None:
    """Aggregate the three pair-wise compares into a
    Copeland-weighted ranking. Reads compare/answer/rubric
    outputs from the workdir, writes the rank task's
    output.yaml via the loom writer.
    """
    try:
        rank_mod.aggregate(Path(workdir).expanduser().resolve())
    except Exception as e:
        _fail(f"rank failed: {e}")


app.add_typer(pipeline_app, name="pipeline")


# ---------------------------------------------------------------------------
# report — render the final user-facing markdown report.
# ---------------------------------------------------------------------------

@app.command("report")
def cli_report(
    workdir: str = typer.Argument(..., help="Loom workdir"),
) -> None:
    """Render the user-facing report and print its path."""
    try:
        path = report_mod.render(
            Path(workdir).expanduser().resolve())
    except Exception as e:
        _fail(f"report render failed: {e}")
    print(path)


if __name__ == "__main__":
    app()
