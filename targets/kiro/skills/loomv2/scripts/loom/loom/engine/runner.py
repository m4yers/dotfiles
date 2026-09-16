"""LoomRuntime — the object callers drive to execute a plan.

Public methods carry docstrings stating preconditions, side effects,
and error surface.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from loom.engine.algorithm import (
    cascade_skip,
    failed_task_ids,
    is_done as _is_done,
    is_stuck as _is_stuck,
    ready_tasks,
    status_of,
    TERMINAL,
)
from loom.engine.models import ActionSpec, LoomPlan, Task
from loom.engine.store import (
    clear_generated_artifacts,
    output_read_path,
    task_folder as _task_folder,
    write_error_yaml,
    write_plan_yaml,
    write_schema_error_yaml,
    write_skip_reason_yaml,
)
from loom.errors import OutputSchemaError, RunAborted


def task_source_folder(loom_root: Path, task: Task) -> Path:
    """Resolve ``task``'s io.yaml/body source folder (loom-root side).

    Inlined subgraph tasks carry ``folder`` or ``source_root`` pointing
    at the CHILD loom root; only root-level tasks resolve against the
    plan's own loom_root.
    """
    from loom.discovery import resolve_task_folder

    if task.folder is not None:
        return task.folder
    if task.source_root is not None:
        return resolve_task_folder(task.source_root, task.id)
    return resolve_task_folder(loom_root, task.id)


class LoomRuntime:
    """Drives a plan against an on-disk workdir."""

    def __init__(self, workdir: Path, plan: LoomPlan):
        self.workdir = Path(workdir)
        self.plan = plan

    def next(self) -> ActionSpec | None:
        """Return the next batch of tasks to run, or None when the plan is done.

        Evaluates each candidate's ``when`` predicate at dispatch time:
          - clean false → task skipped, ``skip-reason.yaml`` written
            (``reason_kind: when-false``);
          - cascade-skip (upstream dep skipped) → task skipped,
            ``skip-reason.yaml`` written (``reason_kind: cascade-skip``);
          - :class:`PredicateEvalError` (parse error, unresolvable ref)
            propagates unchanged — the run aborts loudly.

        Raises :class:`RunAborted` if any task is already in ``failed``.
        In-flight tasks finish naturally (their outputs are persisted)
        but no new tasks are dispatched.
        """
        from loom.engine.predicate import eval_predicate

        failed = failed_task_ids(self.plan)
        if failed:
            raise RunAborted(failed)
        batch: list[dict[str, Any]] = []
        for t in ready_tasks(self.plan):
            if cascade_skip(self.plan, t):
                t.status = "skipped"
                folder = _task_folder(self.workdir, self.plan, t.id)
                folder.mkdir(parents=True, exist_ok=True)
                write_skip_reason_yaml(folder, t.id, "cascade-skip")
                continue
            ok, _reason = eval_predicate(
                t.when or "", self.plan, self.workdir,
                evaluator=(t.id, self._pending_round(t.id)),
            )
            if not ok:
                t.status = "skipped"
                folder = _task_folder(self.workdir, self.plan, t.id)
                folder.mkdir(parents=True, exist_ok=True)
                write_skip_reason_yaml(
                    folder, t.id, "when-false", predicate=t.when
                )
                continue
            t.status = "ready"
            batch.append({"id": t.id, "kind": t.kind})
        write_plan_yaml(self.workdir, self.plan)
        if not batch:
            unfinished = [
                t for t in self.plan.tasks
                if isinstance(t, Task) and t.status not in TERMINAL
            ]
            if not unfinished:
                return None
        return ActionSpec(tasks=batch)

    def _pending_round(self, task_id: str) -> int | None:
        """Round index the next activation of ``task_id`` would get.

        None for tasks outside every loop region (they do not iterate).
        """
        from loom.engine.loops import region_members
        from loom.engine.store import next_round_index

        if task_id not in region_members(self.plan):
            return None
        return next_round_index(_task_folder(self.workdir, self.plan, task_id))

    def commit_running(self, task_ids: list[str]) -> None:
        """Flip ``task_ids`` to running and persist."""
        for t in self.plan.tasks:
            if isinstance(t, Task) and t.id in task_ids:
                t.status = "running"
        write_plan_yaml(self.workdir, self.plan)

    def complete(self, task_id: str) -> None:
        """Mark ``task_id`` done after validating output.yaml.

        Raises OutputSchemaError if output.yaml does not validate against
        io.yaml/output; also writes ``schema-error.yaml`` (phase output)
        alongside the failing task. On subgraph child failure, raise
        carries the full canonical address.

        If ``task_id`` is a loop latch, the latch decision runs after the
        status flip: fuel is decremented and persisted; on continue the
        whole loop body (header through latch) is reset to ``pending``
        so the scheduler re-dispatches it, with prior round outputs
        preserved under their ``iter-NN/`` dirs.
        """
        import jsonschema

        from loom.discovery import load_io_yaml
        from loom.engine.loops import region_members

        task = self._task(task_id)
        source_folder = task_source_folder(self.plan.loom_root, task)
        io = load_io_yaml(source_folder)
        folder = _task_folder(self.workdir, self.plan, task_id)
        is_loop_body = task_id in region_members(self.plan)
        read_path = output_read_path(folder, is_loop_body=is_loop_body)
        output = yaml.safe_load(read_path.read_text()) if read_path.exists() else {}
        try:
            jsonschema.validate(output, io.output_schema)
        except jsonschema.ValidationError as exc:
            task.status = "failed"
            write_plan_yaml(self.workdir, self.plan)
            write_schema_error_yaml(
                read_path.parent, task_id, "output", exc.message
            )
            raise OutputSchemaError(task_id, exc.message) from exc
        task.status = "done"
        write_plan_yaml(self.workdir, self.plan)
        self._maybe_loop(task)

    def _maybe_loop(self, task: Task) -> None:
        """If ``task`` is a loop latch that just reached ``done``, decide
        whether to run another round.

        On continue: decrement ``fuel`` (if any), reset the loop body to
        ``pending``, and bump each body task's ``iter`` counter. On
        stop: persist the decremented fuel and leave the latch ``done``
        so the region's single exit edge releases downstream tasks.

        No-op for tasks without a ``latch``.
        """
        from loom.engine.loops import latch_continue, loop_regions

        if task.latch is None:
            return
        cont, new_fuel = latch_continue(task, self.plan, self.workdir)
        if task.latch.fuel is not None:
            task.latch.fuel = new_fuel
        if cont:
            body = loop_regions(self.plan).get(task.id, set())
            for t in self.plan.tasks:
                if isinstance(t, Task) and t.id in body:
                    t.status = "pending"
                    t.iter += 1
        write_plan_yaml(self.workdir, self.plan)

    def task_output(self, task_id: str) -> dict[str, Any]:
        """Read ``output.yaml`` for ``task_id``.

        For a loop-body task this is the latest completed round's
        output. For a subgraph instance id, resolves to the child exit
        task's output.yaml (the composite output of the whole subgraph).
        """
        from loom.engine.loops import region_members

        folder = _task_folder(self.workdir, self.plan, task_id)
        path = output_read_path(
            folder, is_loop_body=task_id in region_members(self.plan)
        )
        return yaml.safe_load(path.read_text()) if path.exists() else {}

    def fail(self, task_id: str, message: str) -> None:
        """Mark ``task_id`` failed and write ``error.yaml`` for it.

        Callers use this to surface human/agent failures the CLI cannot
        detect itself. The next :meth:`next` call raises
        :class:`RunAborted`.
        """
        task = self._task(task_id)
        folder = _task_folder(self.workdir, self.plan, task_id)
        folder.mkdir(parents=True, exist_ok=True)
        exc = RuntimeError(message)
        write_error_yaml(folder, task_id, task.kind, exc)
        task.status = "failed"
        write_plan_yaml(self.workdir, self.plan)

    def reset(self, task_id: str) -> None:
        """Flip ``task_id`` back to pending and clear its generated artifacts.

        Region-aware: for a loop-body task the whole region is reset
        together so round indexing restarts at ``iter-00``. Latch
        ``fuel`` is NOT restored — it reflects rounds already
        consumed. A caller-seeded input.yaml (on tasks without an
        ``input:`` mapping) is preserved so entries can be re-run
        without rewriting the seed.
        """
        from loom.engine.loops import loop_regions

        regions = loop_regions(self.plan)
        targets: list[str] = [task_id]
        for latch_id, body in regions.items():
            if task_id in body:
                targets = sorted(body)
                break
        for tid in targets:
            t = self._task(tid)
            folder = _task_folder(self.workdir, self.plan, tid)
            clear_generated_artifacts(
                folder, preserve_input=(t.input_mapping is None)
            )
            t.status = "pending"
        write_plan_yaml(self.workdir, self.plan)

    def is_done(self) -> bool:
        """True iff every task is in a terminal status."""
        return _is_done(self.plan)

    def is_stuck(self) -> bool:
        """True iff the plan cannot make progress and is not done."""
        return _is_stuck(self.plan)

    def status_summary(self) -> dict[str, Any]:
        """Return a snapshot of run state.

        Shape: ``{total, is_done, is_stuck, counts}`` where ``counts``
        is a dict from status label (``pending``/``ready``/...) to the
        number of tasks in that status.
        """
        counts = {
            s: 0 for s in
            ("pending", "ready", "running", "done", "failed", "skipped")
        }
        total = 0
        for t in self.plan.tasks:
            if not isinstance(t, Task):
                continue
            total += 1
            counts[t.status] = counts.get(t.status, 0) + 1
        return {
            "total": total,
            "is_done": _is_done(self.plan),
            "is_stuck": _is_stuck(self.plan),
            "counts": counts,
        }

    def _task(self, task_id: str) -> Task:
        for t in self.plan.tasks:
            if isinstance(t, Task) and t.id == task_id:
                return t
        raise KeyError(task_id)
