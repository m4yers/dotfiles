'''Jinja2 template rendering with default context bags.

Five bags (fixed, no skill extension):
  task     - {id, kind, workdir, output_path, depends_on}
  run      - {workdir}
  upstream - {<dep_id>: {output, status, task_path}, ...} for transitive deps
  global   - {path: <workdir>/global}
  vars     - the task's vars dict, with placeholders pre-resolved
'''
from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2
import yaml

from loom.engine.models import LoomPlan, Task
from loom.engine import store
from loom.engine.resolve import resolve_value
from loom.errors import RenderFailed


def render_task(
    task: Task,
    workdir: Path,
    plan: LoomPlan,
) -> str:
    '''Render task.template with the default context bags.

    Returns rendered text. Raises RenderFailed on jinja error or
    missing template.
    '''
    if not task.template:
        raise RenderFailed(
            task.id, '<no-template>',
            'task has no template path; cannot render',
        )
    template_path = Path(task.template)
    if not template_path.exists():
        raise RenderFailed(
            task.id, str(template_path),
            f'template file not found: {template_path}',
        )

    context = _build_context(task, workdir, plan)

    try:
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_path.parent)),
            undefined=jinja2.StrictUndefined,
            keep_trailing_newline=True,
        )
        template = env.get_template(template_path.name)
        return template.render(**context)
    except jinja2.exceptions.TemplateError as e:
        raise RenderFailed(task.id, str(template_path), str(e)) from e
    except Exception as e:
        raise RenderFailed(task.id, str(template_path), str(e)) from e


def _build_context(task: Task, workdir: Path, plan: LoomPlan) -> dict:
    return {
        'task':     _build_task_bag(task, workdir, plan),
        'run':      _build_run_bag(workdir),
        'upstream': _build_upstream_bag(task, workdir, plan),
        'global':   _build_global_bag(workdir),
        'vars':     _build_vars_bag(task, workdir, plan),
    }


def _build_task_bag(task: Task, workdir: Path, plan: LoomPlan) -> dict:
    try:
        td = store.task_dir(workdir, plan, task.id)
        op = store.task_output_path(workdir, plan, task.id)
    except KeyError:
        td = workdir / 'tasks' / task.id
        op = td / 'output.yaml'
    return {
        'id':          task.id,
        'kind':        task.kind,
        'workdir':     str(td),
        'output_path': str(op),
        'depends_on':  list(task.depends_on),
    }


def _build_run_bag(workdir: Path) -> dict:
    return {'workdir': str(workdir)}


def _build_upstream_bag(task: Task, workdir: Path, plan: LoomPlan) -> dict:
    by_id = {t.id: t for t in plan.tasks}
    deps = _transitive_deps(by_id, task.id)
    out = {}
    for dep_id in deps:
        dep_task = by_id[dep_id]
        try:
            tp = store.task_output_path(workdir, plan, dep_id)
        except KeyError:
            continue
        output = None
        if tp.exists():
            try:
                output = yaml.safe_load(tp.read_text(encoding='utf-8'))
            except Exception:
                output = None
        out[dep_id] = {
            'output':    output,
            'status':    dep_task.status,
            'task_path': str(tp),
        }
    return out


def _transitive_deps(by_id: dict, task_id: str) -> list[str]:
    seen: set[str] = set()
    order: list[str] = []
    def walk(tid: str) -> None:
        if tid in seen:
            return
        seen.add(tid)
        node = by_id.get(tid)
        if node is None:
            return
        for d in node.depends_on:
            walk(d)
        if tid != task_id:
            order.append(tid)
    walk(task_id)
    return order


def _build_global_bag(workdir: Path) -> dict:
    return {'path': str(store.global_dir(workdir))}


def _build_vars_bag(task: Task, workdir: Path, plan: LoomPlan) -> dict:
    if not task.vars:
        return {}
    return {k: resolve_value(v, workdir, plan, task_id=task.id)
            for k, v in task.vars.items()}
