"""High-level run orchestration — the engine's public surface.

``EngineRun`` is the only class applications need to interact with.
It hides workdir lifecycle, plan/state I/O, dispatcher invocation,
and DAG transitions behind start / next_action / complete / extend.

Engine performs presence-only post-conditions: a task is considered
successful when its dispatcher exits 0 and ``output.yaml`` exists in
the task subdir. Engine does not validate output content.

Engine does NOT retry failed internal tasks — retries (if any) are
the dispatcher's responsibility. A task that fails once is marked
failed and the run reports it via RunFailed.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from engine import algorithm, store, workdir as workdir_mod
from engine.models import Plan, Task

# Default kinds engine runs internally vs yields back to the caller.
INTERNAL_KINDS: frozenset[str] = frozenset({"tool"})
EXTERNAL_KINDS: frozenset[str] = frozenset({"agent", "human"})


@dataclass
class ActionSpec:
    """A batch of external tasks the application must dispatch.

    Each item in ``tasks`` is a Task dict (Task.to_dict) with extra
    ``task_workdir`` and ``output_path`` fields filled in.
    """

    workdir: Path
    tasks: list[dict]


class RunFailed(RuntimeError):
    """Raised by next_action when an internal task fails."""

    def __init__(self, task_id: str, message: str):
        super().__init__(f"task {task_id!r} failed: {message}")
        self.task_id = task_id
        self.message = message


class EngineRun:
    """Single-run handle. Each CLI process resumes (or starts) one
    of these, calls a single state-changing method, exits."""

    def __init__(self, workdir: Path):
        self.workdir = workdir

    # ── lifecycle ───────────────────────────────────────────

    @classmethod
    def start(
        cls,
        base_dir: str | Path,
        basename: str,
        plan_factory: Callable[[Path], Plan],
        slug_max_length: int = workdir_mod.DEFAULT_SLUG_MAX_LENGTH,
    ) -> "EngineRun":
        """Create a fresh workdir and write the initial plan.

        If the resolved workdir already exists it is dropped first.
        Does NOT advance the plan — call next_action() to run any
        internal tasks.
        """
        wd = workdir_mod.create_workdir(base_dir, basename, slug_max_length)
        plan = plan_factory(wd)
        if not isinstance(plan, Plan):
            raise TypeError(
                f"plan_factory must return a Plan, got {type(plan).__name__}")
        store.save_plan(wd, plan)
        return cls(wd)

    @classmethod
    def resume(cls, workdir: str | Path) -> "EngineRun":
        """Re-attach to an existing workdir between CLI calls."""
        wd = Path(workdir).resolve()
        if not store.plan_path(wd).exists():
            raise FileNotFoundError(
                f"no plan at {store.plan_path(wd)}; cannot resume")
        return cls(wd)

    # ── state-changing API ──────────────────────────────────

    def next_action(self) -> Optional[ActionSpec]:
        """Advance internal tasks; return next external batch, or
        None if the plan is complete or has no further work to do
        without external completions arriving first.

        External tasks in the returned batch are NOT committed to
        ``running`` — the caller is responsible for calling
        :meth:`commit_running` after any per-task setup (prompt
        rendering, dispatcher prep) has succeeded. This lets the
        caller fail cleanly without leaving tasks stranded in
        ``running`` with no progress.

        To distinguish "all tasks terminal" from "blocked, awaiting
        external", the caller should check :func:`algorithm.is_done`
        on the live plan when this method returns None.
        """
        while True:
            plan = store.load_plan(self.workdir)

            if algorithm.is_done(plan):
                return None

            ready = algorithm.ready(plan)
            if not ready:
                # Nothing ready and not done — awaiting an in-flight
                # external task or blocked. Return None as a signal
                # that engine has nothing more to do right now.
                return None

            internal = [t for t in ready if t.kind in INTERNAL_KINDS]
            external = [t for t in ready if t.kind in EXTERNAL_KINDS]
            unknown  = [t for t in ready
                          if t.kind not in INTERNAL_KINDS
                          and t.kind not in EXTERNAL_KINDS]
            if unknown:
                raise RuntimeError(
                    "ready tasks have unknown kinds: "
                    f"{sorted({t.kind for t in unknown})}")

            if internal:
                algorithm.mark_running(plan, [t.id for t in internal])
                store.save_plan(self.workdir, plan)
                for task in internal:
                    self._run_internal(task, plan)
                continue   # reload plan — new tasks may be ready

            # Yield the external batch WITHOUT committing running.
            # Caller commits via commit_running after rendering.
            return self._action_spec(external, plan)

    def commit_running(self, task_ids: list[str]) -> None:
        """Mark the given tasks as ``running`` and persist.

        Used by the caller of :meth:`next_action` to commit the
        external batch after all per-task setup (e.g., prompt
        rendering) has succeeded. Calling this before all setup is
        complete risks leaving a task in ``running`` without the
        artifacts the orchestrator needs (e.g., prompt files).
        """
        plan = store.load_plan(self.workdir)
        algorithm.mark_running(plan, task_ids)
        store.save_plan(self.workdir, plan)

    def complete(
        self,
        task_id: str,
        output: dict[str, Any] | None = None,
    ) -> None:
        """Mark an external task complete. Precondition: the task's
        ``output.yaml`` must exist in <workdir>/tasks/<task-id>/.

        Engine does not validate the output's content.
        """
        plan = store.load_plan(self.workdir)
        task = plan.get(task_id)
        if task is None:
            raise KeyError(f"unknown task: {task_id}")

        out_path = store.task_output_path(self.workdir, task_id, plan=plan)
        if not out_path.exists():
            raise FileNotFoundError(
                f"output.yaml missing for task {task_id!r} at {out_path}")

        algorithm.mark_done(plan, task_id)
        store.save_plan(self.workdir, plan)

    def reset(self, task_id: str) -> None:
        """Reset a task back to pending."""
        plan = store.load_plan(self.workdir)
        algorithm.reset_task(plan, task_id)
        store.save_plan(self.workdir, plan)

    def resolve_value(self, value: Any, task_id: str | None = None) -> Any:
        """Resolve ``${...}`` placeholders in a string, list, or dict.

        Recurses into containers. Strings get the same placeholder
        substitution as tool task cmds (`${workdir}`, `${task_workdir}`,
        `${task:<id>}`, `${task:<id>:<dotpath>}`). When ``task_id`` is
        provided, ``${task_workdir}`` resolves to that task's subdir.

        Type preservation: when a string is *exactly* a single
        ``${task:<id>[:<dotpath>]}`` placeholder (no surrounding text),
        the native upstream value is returned — dict/list stay
        structured, scalars stay scalars. Embedded placeholders or
        non-``task:`` placeholders fall through to the same string-
        coercing pipeline as tool argv (``_resolve_cmd``), preserving
        the existing contract for tool tasks.
        """
        plan = store.load_plan(self.workdir)
        twd = (store.task_dir(self.workdir, task_id, plan=plan)
               if task_id is not None else self.workdir / "tasks")
        if isinstance(value, str):
            return self._resolve_string_native(value, task_id or "", twd)
        if isinstance(value, list):
            return [self.resolve_value(v, task_id) for v in value]
        if isinstance(value, dict):
            return {k: self.resolve_value(v, task_id) for k, v in value.items()}
        return value

    # Whole-string-is-a-single-placeholder check — used to decide
    # whether to return a native Python type or fall back to string
    # substitution.
    _WHOLE_PLACEHOLDER_RE = __import__("re").compile(r"^\$\{([^}]+)\}$")

    def _resolve_string_native(self, s: str, task_id: str,
                                  task_workdir: Path) -> Any:
        """Resolve a single string. If the entire string is one
        ``${task:<id>[:<field>]}`` placeholder, return the native
        Python value loaded from the upstream output (dict/list/
        scalar). Otherwise, delegate to ``_resolve_cmd`` which
        produces a string with all placeholders substituted.
        """
        m = self._WHOLE_PLACEHOLDER_RE.match(s)
        if m and m.group(1).startswith("task:"):
            spec = m.group(1)
            _, _, rest = spec.partition(":")
            if ":" in rest:
                tid, _, field = rest.partition(":")
            else:
                tid, field = rest, ""
            doc = self._load_task_output(tid)
            if not field:
                return doc
            cur = doc
            for part in field.split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    return None
            return cur
        # Embedded placeholder (or any non-task: placeholder) —
        # fall back to string substitution.
        return self._resolve_cmd([s], task_id, task_workdir)[0]

    def _load_task_output(self, task_id: str) -> Any:
        """Load <wd>/tasks/<id>/output.yaml and return the parsed
        document. Missing files return None — callers must tolerate.
        """
        import yaml as _yaml
        plan = store.load_plan(self.workdir)
        p = store.task_output_path(self.workdir, task_id, plan=plan)
        try:
            return _yaml.safe_load(p.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def extend(self, more_tasks: Iterable[Task] | Plan) -> None:
        """Append tasks to the live plan.

        Accepts either a Plan whose tasks should all be appended or
        a bare iterable of Tasks. Duplicate ids are caught at append
        time.
        """
        plan = store.load_plan(self.workdir)
        new_tasks = list(more_tasks.tasks if isinstance(more_tasks, Plan)
                         else more_tasks)
        existing_ids = {t.id for t in plan.tasks}
        for task in new_tasks:
            if task.id in existing_ids:
                raise ValueError(
                    f"task id collision in extend: {task.id!r}")
            plan.tasks.append(task)
            existing_ids.add(task.id)
        store.save_plan(self.workdir, plan)

    # ── internals ───────────────────────────────────────────

    def _run_internal(self, task: Task, plan: Plan) -> None:
        """Execute one tool task directly.

        The task's `cmd` is invoked as a subprocess; stdout is
        captured to `<task_workdir>/output.yaml`, stderr to
        `<task_workdir>/stderr.log`. Marks the task done if exit==0
        and output.yaml exists; marks failed and raises RunFailed
        otherwise. Engine does not retry — that is up to the task
        implementation.

        Curator's plan factories construct each tool task's `cmd`
        with absolute paths to executables, so engine does not need
        a dispatcher shim. Placeholder substitution is done inline
        by `_resolve_cmd` before the subprocess starts.
        """
        if task.kind != "tool":
            raise RuntimeError(
                f"_run_internal called for non-tool kind: {task.kind}")
        if not task.cmd:
            raise RuntimeError(
                f"tool task {task.id!r} has empty cmd")

        task_workdir = store.ensure_task_dir(self.workdir, task.id, plan=plan)
        out_path = store.task_output_path(self.workdir, task.id, plan=plan)
        stderr_path = task_workdir / "stderr.log"

        env = os.environ.copy()
        env["WORKDIR"]      = str(self.workdir)
        env["TASK_ID"]      = task.id
        env["OUTPUT_PATH"]  = str(out_path)
        env["TASK_WORKDIR"] = str(task_workdir)

        resolved_cmd = self._resolve_cmd(task.cmd, task.id, task_workdir)

        with out_path.open("w") as out_f, stderr_path.open("w") as err_f:
            proc = subprocess.run(
                resolved_cmd,
                env=env,
                stdout=out_f,
                stderr=err_f,
                text=True,
            )

        ok = (proc.returncode == 0) and out_path.exists()
        if ok:
            algorithm.mark_done(plan, task.id)
            store.save_plan(self.workdir, plan)
            return

        algorithm.mark_failed(plan, task.id)
        store.save_plan(self.workdir, plan)
        stderr_tail = "\n".join(
            stderr_path.read_text(encoding="utf-8").splitlines()[-20:]
            if stderr_path.exists() else [])
        raise RunFailed(
            task.id,
            f"exit={proc.returncode} output_exists={out_path.exists()}\n"
            f"stderr_tail:\n{stderr_tail}")

    def _resolve_cmd(self, cmd: list[str], task_id: str,
                       task_workdir: Path) -> list[str]:
        """Resolve placeholders in a tool task's cmd list.

        Supported placeholders (passed-through from the original
        task model):
            ${workdir}                — absolute workdir path
            ${task_workdir}           — absolute task subdir path
            ${task:<id>}              — load <wd>/tasks/<id>/output.yaml as dict (str-coerced)
            ${task:<id>:<dotpath>}    — extract field via dot path
            ${task_path:<id>}         — absolute path to <id>'s output.yaml
            ${verdict_path:<id>}      — absolute path to <id>'s verdict.yaml (judge output)
        """
        import re, yaml as _yaml
        wd = self.workdir
        plan = store.load_plan(wd)
        cache: dict[str, Any] = {}

        def _load_output(tid: str):
            if tid in cache:
                return cache[tid]
            p = store.task_output_path(wd, tid, plan=plan)
            try:
                cache[tid] = _yaml.safe_load(p.read_text(encoding="utf-8"))
            except FileNotFoundError:
                cache[tid] = None
            return cache[tid]

        def _walk(doc, dotpath: str):
            if doc is None:
                return None
            for part in dotpath.split("."):
                if isinstance(doc, dict) and part in doc:
                    doc = doc[part]
                else:
                    return None
            return doc

        PLACEHOLDER_RE = re.compile(r"\$\{([^}]+)\}")

        def replace_one(spec: str):
            if spec == "workdir":
                return str(wd)
            if spec == "task_workdir":
                return str(task_workdir)
            if spec.startswith("task_path:"):
                _, _, tid = spec.partition(":")
                return str(store.task_output_path(wd, tid, plan=plan))
            if spec.startswith("verdict_path:"):
                # Sibling of task_path: points to <task_dir>/verdict.yaml.
                # Curator's prompts.py writes verdicts there; the engine
                # itself does not enforce that the file exists. Downstream
                # consumers should tolerate a missing file (e.g. tool
                # tasks that have no judge).
                _, _, tid = spec.partition(":")
                return str(store.task_dir(wd, tid, plan=plan) / "verdict.yaml")
            if spec.startswith("task:"):
                _, _, rest = spec.partition(":")
                if ":" in rest:
                    tid, _, field = rest.partition(":")
                    val = _walk(_load_output(tid), field)
                else:
                    val = _load_output(rest)
                if val is None:
                    return ""
                if isinstance(val, (dict, list)):
                    return _yaml.safe_dump(val, sort_keys=False).rstrip()
                return str(val)
            # Unknown placeholder — leave as-is so failures are visible.
            return "${" + spec + "}"

        out: list[str] = []
        for arg in cmd:
            new = PLACEHOLDER_RE.sub(lambda m: replace_one(m.group(1)), arg)
            out.append(new)
        return out

    def _action_spec(self, tasks: list[Task], plan: Plan) -> ActionSpec:
        out_tasks: list[dict] = []
        for task in tasks:
            store.ensure_task_dir(self.workdir, task.id, plan=plan)
            d = task.to_dict()
            d["task_workdir"] = str(store.task_dir(self.workdir, task.id, plan=plan))
            d["output_path"]  = str(store.task_output_path(self.workdir, task.id, plan=plan))
            out_tasks.append(d)
        return ActionSpec(workdir=self.workdir, tasks=out_tasks)
