'''LoomRuntime — the execution engine.

Lifecycle:
  - Created by loom.init() or loom.resume().
  - Caller drives via runtime.next(), commit_running(), complete(), fail(),
    reset(), and read-only queries.
  - All methods reload plan.yaml on entry and persist atomically on mutation.
'''
from __future__ import annotations

import copy
import os
import subprocess
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from loom.engine import store, algorithm
from loom.engine.models import (
    ActionSpec, LoomPlan, Task,
    STATUS_PENDING, STATUS_READY, STATUS_RUNNING,
    STATUS_DONE, STATUS_FAILED, STATUS_SKIPPED,
    TERMINAL_STATUSES,
)
from loom.engine.resolve import resolve_value
from loom.errors import OutputSchemaError, RunFailed, RenderFailed, RunAborted
from loom.render import render_task


class LoomRuntime:
    def __init__(self, workdir: Path, schemas) -> None:
        self.workdir = Path(workdir).resolve()
        self._schemas = schemas

    # ---- main loop ----

    def next(self) -> ActionSpec | None:
        '''Compute ready set, run tool tasks inline, render external tasks,
        return ActionSpec for external batch (or None if done/stuck).

        Raises ``RunAborted`` if any task in the plan is already in
        ``failed`` status. Failure halts the whole run; in-flight
        tasks finish naturally (their outputs are persisted) but
        no new tasks are dispatched.
        '''
        while True:
            plan = store.load_plan(self.workdir)

            failed_ids = algorithm.find_failed_tasks(plan)
            if failed_ids:
                raise RunAborted(failed_ids)

            if algorithm.is_done(plan):
                return None

            candidates = algorithm.compute_ready_set(plan)
            if not candidates:
                return None

            runnable, skipped, _ = algorithm.partition_ready(
                candidates, plan, self.workdir)

            for t, reason in skipped:
                t.status = STATUS_SKIPPED
                td = store.ensure_task_dir(self.workdir, plan, t.id)
                (td / 'skip-reason.log').write_text(reason, encoding='utf-8')
            if skipped:
                store.save_plan(self.workdir, plan)

            internal = [t for t in runnable if t.kind == 'tool']
            external = [t for t in runnable if t.kind != 'tool']

            if internal:
                for t in internal:
                    self._dispatch_tool(t, plan)
                    plan = store.load_plan(self.workdir)
                continue

            if not external:
                continue

            for t in external:
                if t.status == STATUS_PENDING:
                    t.status = STATUS_READY
            store.save_plan(self.workdir, plan)

            spec_tasks: list[dict] = []
            for t in external:
                td = store.ensure_task_dir(self.workdir, plan, t.id)
                op = store.task_output_path(self.workdir, plan, t.id)
                prompt_path = None
                if t.template:
                    try:
                        rendered = render_task(t, self.workdir, plan)
                    except RenderFailed as e:
                        t.status = STATUS_FAILED
                        (td / 'render-error.log').write_text(
                            str(e), encoding='utf-8')
                        store.save_plan(self.workdir, plan)
                        raise
                    prompt_path = td / 'prompt.md'
                    prompt_path.write_text(rendered, encoding='utf-8')

                d = t.to_dict()
                d['task_workdir'] = str(td)
                d['output_path'] = str(op)
                if prompt_path is not None:
                    d['prompt_path'] = str(prompt_path)
                spec_tasks.append(d)

            return ActionSpec(workdir=self.workdir, tasks=spec_tasks)

    # ---- tool dispatcher ----

    def _dispatch_tool(self, task: Task, plan: LoomPlan) -> None:
        if task.status == STATUS_PENDING:
            task.status = STATUS_READY
            store.save_plan(self.workdir, plan)
        if task.status == STATUS_READY:
            task.status = STATUS_RUNNING
            store.save_plan(self.workdir, plan)

        td = store.ensure_task_dir(self.workdir, plan, task.id)
        op = store.task_output_path(self.workdir, plan, task.id)
        stderr_path = td / 'stderr.log'

        env = os.environ.copy()
        env['WORKDIR'] = str(self.workdir)
        env['TASK_ID'] = task.id
        env['OUTPUT_PATH'] = str(op)
        env['TASK_WORKDIR'] = str(td)

        resolved_cmd = resolve_value(task.cmd, self.workdir, plan, task_id=task.id)

        with op.open('w') as out_f, stderr_path.open('w') as err_f:
            proc = subprocess.run(
                resolved_cmd, env=env,
                stdout=out_f, stderr=err_f, text=True,
            )

        if proc.returncode != 0 or not op.exists():
            task.status = STATUS_FAILED
            store.save_plan(self.workdir, plan)
            stderr_tail = ''
            if stderr_path.exists():
                tail = stderr_path.read_text(encoding='utf-8').splitlines()[-20:]
                stderr_tail = '\n'.join(tail)
            raise RunFailed(
                task.id,
                f'exit={proc.returncode} output_exists={op.exists()}\n'
                f'stderr_tail:\n{stderr_tail}')

        if task.output_schema:
            try:
                doc = yaml.safe_load(op.read_text(encoding='utf-8'))
                schema = self._schemas.load(task.output_schema)
                jsonschema.validate(doc, schema)
            except (jsonschema.ValidationError, yaml.YAMLError) as e:
                task.status = STATUS_FAILED
                (td / 'schema-error.log').write_text(str(e), encoding='utf-8')
                store.save_plan(self.workdir, plan)
                raise OutputSchemaError(task.id, str(e)) from e

        task.status = STATUS_DONE
        store.save_plan(self.workdir, plan)

    # ---- state-changing methods ----

    def commit_running(self, task_ids: list[str]) -> None:
        '''Flip ready->running for the given tasks.'''
        plan = store.load_plan(self.workdir)
        for tid in task_ids:
            t = plan.get(tid)
            if t.status != STATUS_READY:
                raise ValueError(
                    f'task {tid!r} is not in ready status (status={t.status!r})')
            t.status = STATUS_RUNNING
        store.save_plan(self.workdir, plan)

    def complete(self, task_id: str, output: dict | None = None) -> None:
        '''Mark a task done. Validates output against schema.'''
        plan = store.load_plan(self.workdir)
        t = plan.get(task_id)
        td = store.ensure_task_dir(self.workdir, plan, task_id)
        op = store.task_output_path(self.workdir, plan, task_id)

        if output is not None:
            op.write_text(
                yaml.safe_dump(output, sort_keys=False, allow_unicode=True,
                               default_flow_style=False),
                encoding='utf-8',
            )

        if not op.exists():
            raise FileNotFoundError(
                f'output.yaml missing for task {task_id!r} at {op}')

        schema_path = t.output_schema
        if schema_path:
            schema = self._schemas.load(schema_path)
        elif t.kind == 'human':
            schema = {'type': 'object'}
        else:
            schema = None

        if schema is not None:
            try:
                doc = yaml.safe_load(op.read_text(encoding='utf-8'))
                jsonschema.validate(doc, schema)
            except (jsonschema.ValidationError, yaml.YAMLError) as e:
                t.status = STATUS_FAILED
                (td / 'schema-error.log').write_text(str(e), encoding='utf-8')
                store.save_plan(self.workdir, plan)
                raise OutputSchemaError(task_id, str(e)) from e

        t.status = STATUS_DONE
        store.save_plan(self.workdir, plan)

    def fail(self, task_id: str, error: str | dict) -> None:
        '''Mark a task failed.'''
        plan = store.load_plan(self.workdir)
        t = plan.get(task_id)
        td = store.ensure_task_dir(self.workdir, plan, task_id)
        msg = str(error) if not isinstance(error, dict) else \
            yaml.safe_dump(error, sort_keys=False, default_flow_style=False)
        (td / 'stderr.log').write_text(msg, encoding='utf-8')
        t.status = STATUS_FAILED
        store.save_plan(self.workdir, plan)

    def reset(self, task_id: str) -> None:
        '''Flip a task back to pending. Removes artifacts.'''
        plan = store.load_plan(self.workdir)
        t = plan.get(task_id)
        td = store.ensure_task_dir(self.workdir, plan, task_id)
        for fname in ('output.yaml', 'prompt.md',
                      'render-error.log', 'schema-error.log',
                      'stderr.log', 'skip-reason.log'):
            f = td / fname
            if f.exists():
                f.unlink()
        t.status = STATUS_PENDING
        store.save_plan(self.workdir, plan)

    # ---- read-only queries ----

    def is_done(self) -> bool:
        return algorithm.is_done(store.load_plan(self.workdir))

    def is_stuck(self) -> bool:
        return algorithm.is_stuck(store.load_plan(self.workdir))

    def plan(self) -> LoomPlan:
        return copy.deepcopy(store.load_plan(self.workdir))

    def task_dir(self, task_id: str) -> Path:
        plan = store.load_plan(self.workdir)
        return store.task_dir(self.workdir, plan, task_id)

    def task_output_path(self, task_id: str) -> Path:
        plan = store.load_plan(self.workdir)
        return store.task_output_path(self.workdir, plan, task_id)

    def task_output(self, task_id: str) -> dict | None:
        p = self.task_output_path(task_id)
        if not p.exists():
            return None
        return yaml.safe_load(p.read_text(encoding='utf-8'))

    def global_dir(self) -> Path:
        return store.global_dir(self.workdir)

    def global_path(self, *parts: str) -> Path:
        return store.global_dir(self.workdir).joinpath(*parts)

    def resolve_value(self, value: Any, task_id: str | None = None) -> Any:
        plan = store.load_plan(self.workdir)
        return resolve_value(value, self.workdir, plan, task_id=task_id)

    def status_summary(self) -> dict:
        plan = store.load_plan(self.workdir)
        counts = {s: 0 for s in (STATUS_PENDING, STATUS_READY, STATUS_RUNNING,
                                  STATUS_DONE, STATUS_FAILED, STATUS_SKIPPED)}
        for t in plan.tasks:
            counts[t.status] = counts.get(t.status, 0) + 1
        return {
            'total': len(plan.tasks),
            'is_done': algorithm.is_done(plan),
            'is_stuck': algorithm.is_stuck(plan),
            'counts': counts,
        }
