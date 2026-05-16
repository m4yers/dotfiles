"""Curator runtime — single-shot run-driving wrappers around EngineRun.

Each `curator.sh` run-driving command (ingest / next / complete /
status) is implemented as a single Python function that resumes (or
starts) a run, calls one engine method, and emits the result as
YAML.

The orchestrator (LLM agent) drives the loop. Curator is stateless
between calls.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable

import yaml

from engine import EngineRun, RunFailed, algorithm, store
from engine.models import Plan, STATUS_FAILED, TERMINAL_STATUSES
from curator.config import WORKDIR_ROOT, derive_basename
from curator.prompts import render_agent_prompts
from curator.stages import build_stage1_plan
from curator.utils import emit, fail


# Generic stage transitions are declared via task metadata.
# Each transitioning task carries:
#   metadata:
#     transition:
#       factory:     "<module>:<attr>"   # importable callable
#       input_field: "<dot.path>"        # field in output.yaml passed as the
#                                        # second positional arg (optional)
#
# The factory signature is: ``fn(workdir: Path, value: Any) -> Plan``
# (or ``fn(workdir: Path) -> Plan`` if ``input_field`` is omitted).
# Engine remains stage-blind; curator-runtime detects the metadata on
# ``complete`` and calls ``run.extend(new_plan)``.
_TRANSITION_KEY = "transition"


def cli_ingest(url_or_path: str) -> None:
    """`curator.sh ingest <url-or-path>` — start a fresh run.

    Drops any existing workdir (same UTC day + same basename),
    creates a new one, writes the stage1 plan, and emits the workdir
    path on stdout. Does NOT advance — caller invokes `next`."""
    basename = derive_basename(url_or_path)
    try:
        run = EngineRun.start(
            base_dir=WORKDIR_ROOT,
            basename=basename,
            plan_factory=lambda wd: build_stage1_plan(
                wd, origin=url_or_path),
        )
    except Exception as e:
        fail(f"ingest failed: {e}")
    emit({"workdir": str(run.workdir), "basename": basename})


def cli_next(workdir: str) -> None:
    """`curator.sh next <wd>` — advance internal tasks; emit next
    external batch (or done).

    Engine runs all ready kind=tool tasks via dispatchers (which
    handle prompt rendering, aggregation, etc.) and yields when the
    next ready task is kind=agent or kind=human. For each yielded
    agent task, curator renders the extractor + judge prompts and
    augments the task spec with their absolute paths. The orchestrator
    just reads the prompt files and dispatches the sub-agents."""
    wd = Path(workdir).resolve()
    try:
        run = EngineRun.resume(wd)
        action = run.next_action()
    except RunFailed as e:
        fail(f"task failed: {e.task_id}", task_id=e.task_id,
              detail=e.message)
    except FileNotFoundError as e:
        fail(str(e))

    if action is None:
        emit({"done": True, "workdir": str(wd)})
        return

    # Render agent/judge prompts for every agent task in the batch.
    # Human tasks get no prompts; tool tasks never reach this point.
    augmented_tasks: list[dict] = []
    for task in action.tasks:
        if task.get("kind") == "agent":
            try:
                paths = render_agent_prompts(run, task)
            except Exception as e:
                fail(f"prompt render failed for task {task['id']!r}: {e}",
                      task_id=task["id"])
            task = {**task, **paths}
        augmented_tasks.append(task)

    emit({
        "done":     False,
        "workdir":  str(action.workdir),
        "ready":    augmented_tasks,
    })


def cli_complete(workdir: str, task_id: str) -> None:
    """`curator.sh complete <wd> <task-id>` — mark agents/human task
    done. Precondition: <wd>/tasks/<task-id>/output.yaml exists.

    Curator-side: if the completed task carries declarative
    transition metadata, invoke the factory and append the returned
    plan via ``run.extend``. Engine itself is stage-blind."""
    wd = Path(workdir).resolve()
    try:
        run = EngineRun.resume(wd)
    except FileNotFoundError as e:
        fail(str(e))

    plan = store.load_plan(wd)
    out_path = store.task_output_path(wd, task_id, plan=plan)
    output: dict[str, Any] | None = None
    if out_path.exists():
        try:
            output = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        except Exception:
            # Engine doesn't validate content; leave output as None.
            output = None

    try:
        run.complete(task_id, output=output)
    except (KeyError, FileNotFoundError) as e:
        fail(str(e))

    # Generic declarative stage transition (replaces the previous
    # hardcoded ``classify -> stage2`` magic). Any task may carry
    # metadata.transition; runtime imports the factory, extracts the
    # named field from the task output, and appends the result.
    task = plan.get(task_id)
    transition = (task.metadata or {}).get(_TRANSITION_KEY)
    if transition:
        try:
            new_plan = _run_transition(run, task_id, transition, output)
        except Exception as e:
            fail(f"transition for task {task_id!r} failed: {e}",
                  task_id=task_id)
        try:
            run.extend(new_plan)
        except Exception as e:
            fail(f"plan extend for task {task_id!r} failed: {e}",
                  task_id=task_id)

    emit({"ok": True, "task_id": task_id, "workdir": str(wd)})


def _run_transition(
    run: EngineRun,
    task_id: str,
    transition: dict[str, Any],
    output: dict[str, Any] | None,
) -> Plan:
    """Resolve and invoke a declarative transition factory.

    ``transition`` shape::

        {factory: "module.path:attr", input_field: "<dotpath>"}

    The factory MUST accept ``(workdir, value)`` (or just
    ``(workdir,)`` if ``input_field`` is absent) and return a Plan.
    """
    factory_spec = transition.get("factory")
    if not factory_spec:
        raise ValueError("transition missing 'factory'")
    factory = _import_factory(factory_spec)

    input_field = transition.get("input_field")
    if input_field is None:
        new_plan = factory(run.workdir)
    else:
        value = _walk_dotpath(output or {}, input_field)
        if value is None:
            raise ValueError(
                f"transition input field {input_field!r} missing in "
                f"task {task_id!r} output")
        new_plan = factory(run.workdir, value)

    if not isinstance(new_plan, Plan):
        raise TypeError(
            f"transition factory {factory_spec!r} returned "
            f"{type(new_plan).__name__}, expected Plan")
    return new_plan


def _import_factory(spec: str) -> Callable[..., Plan]:
    """Import 'module.path:attr' and return the attribute."""
    if ":" not in spec:
        raise ValueError(
            f"factory spec must be 'module:attr', got {spec!r}")
    module_path, attr = spec.split(":", 1)
    module = importlib.import_module(module_path)
    try:
        return getattr(module, attr)
    except AttributeError as e:
        raise ValueError(
            f"factory {attr!r} not found in {module_path!r}") from e


def _walk_dotpath(doc: Any, dotpath: str) -> Any:
    """Walk a dotted path through nested dicts. Return None if any
    segment is missing or the doc is not a mapping at that point."""
    cur = doc
    for part in dotpath.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur


# ── status oracle ──────────────────────────────────────────────────


# Verdicts written by judge sub-agents.
_VERDICT_ACCEPT = "ACCEPT"
_VERDICT_REVIEW = "REVIEW"
_VERDICT_REJECT = "REJECT"
_VERDICTS = (_VERDICT_ACCEPT, _VERDICT_REVIEW, _VERDICT_REJECT)


def _read_verdict(verdict_path: Path) -> str | None:
    """Return the ACCEPT/REVIEW/REJECT verdict, or None if missing or
    malformed. Tolerates absent files: tasks without a judge stage
    legitimately have no verdict.yaml."""
    if not verdict_path.exists():
        return None
    try:
        data = yaml.safe_load(verdict_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    v = data.get("verdict")
    return v if v in _VERDICTS else None


def cli_status(workdir: str) -> None:
    """`curator.sh status <wd>` — aggregate verdicts and emit the
    final completion status.

    Returns one of:
      - DONE                 — plan complete; no judge verdict was REJECT.
      - DONE_WITH_CONCERNS   — plan complete; ≥1 verdict was REJECT.
      - BLOCKED              — any task is in failed status.
      - IN_PROGRESS          — plan not yet complete.
      - NEEDS_CONTEXT        — workdir or plan.yaml missing.

    Reads each agent-task subdir's verdict.yaml directly so the
    orchestrator does not have to. Tasks with no verdict.yaml (e.g.
    tool tasks, human gate) are counted under ``no_verdict``.
    """
    wd = Path(workdir).resolve()
    if not wd.exists() or not store.plan_path(wd).exists():
        emit({"status": "NEEDS_CONTEXT",
              "reason": f"workdir or plan.yaml missing: {wd}",
              "workdir": str(wd)})
        return

    plan = store.load_plan(wd)

    # Aggregate verdicts across every task that has a verdict.yaml.
    counts = {_VERDICT_ACCEPT: 0, _VERDICT_REVIEW: 0, _VERDICT_REJECT: 0}
    no_verdict = 0
    failed_ids: list[str] = []
    for task in plan.tasks:
        if task.status == STATUS_FAILED:
            failed_ids.append(task.id)
        td = store.task_dir(wd, task.id, plan=plan)
        v = _read_verdict(td / "verdict.yaml")
        if v is None:
            no_verdict += 1
        else:
            counts[v] += 1

    summary = {
        "workdir":       str(wd),
        "verdicts":      counts,
        "no_verdict":    no_verdict,
        "failed_tasks":  failed_ids,
    }

    if failed_ids:
        emit({"status": "BLOCKED", **summary})
        return
    if not algorithm.is_done(plan):
        pending = [t.id for t in plan.tasks
                   if t.status not in TERMINAL_STATUSES]
        emit({"status": "IN_PROGRESS", "pending_tasks": pending,
              **summary})
        return
    if counts[_VERDICT_REJECT] > 0:
        emit({"status": "DONE_WITH_CONCERNS", **summary})
        return
    emit({"status": "DONE", **summary})
