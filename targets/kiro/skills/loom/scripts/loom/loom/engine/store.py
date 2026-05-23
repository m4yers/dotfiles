'''Persistence layer: plan.yaml + task subdirs + output.yaml.'''
from __future__ import annotations

import os
from pathlib import Path

import yaml

from loom.engine.models import LoomPlan


def _dump_yaml(data) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True,
                          default_flow_style=False)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, path)


def plan_path(workdir: Path) -> Path:
    return Path(workdir) / 'plan.yaml'


def tasks_dir(workdir: Path) -> Path:
    return Path(workdir) / 'tasks'


def global_dir(workdir: Path) -> Path:
    return Path(workdir) / 'global'


def ensure_workdir_dirs(workdir: Path) -> None:
    '''Create tasks/ and global/ if missing.'''
    tasks_dir(workdir).mkdir(parents=True, exist_ok=True)
    global_dir(workdir).mkdir(parents=True, exist_ok=True)


def load_plan(workdir: Path) -> LoomPlan:
    p = plan_path(workdir)
    if not p.exists():
        raise FileNotFoundError(f'plan.yaml not found at {p}')
    data = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
    return LoomPlan.from_dict(data)


def save_plan(workdir: Path, plan: LoomPlan) -> None:
    ensure_workdir_dirs(workdir)
    _atomic_write(plan_path(workdir), _dump_yaml(plan.to_dict()))


def _numbered_name(index: int, task_id: str) -> str:
    return f'{index:02d}-{task_id}'


def task_dir(workdir: Path, plan: LoomPlan, task_id: str) -> Path:
    '''Per-task subdir at <workdir>/tasks/<NN-task_id>/.'''
    for i, t in enumerate(plan.tasks, start=1):
        if t.id == task_id:
            return Path(workdir) / 'tasks' / _numbered_name(i, task_id)
    raise KeyError(f'task not in plan: {task_id}')


def ensure_task_dir(workdir: Path, plan: LoomPlan, task_id: str) -> Path:
    d = task_dir(workdir, plan, task_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def task_output_path(workdir: Path, plan: LoomPlan, task_id: str) -> Path:
    return task_dir(workdir, plan, task_id) / 'output.yaml'


def load_task_output(workdir: Path, plan: LoomPlan, task_id: str) -> dict:
    p = task_output_path(workdir, plan, task_id)
    if not p.exists():
        raise FileNotFoundError(f'output.yaml missing for {task_id!r}: {p}')
    data = yaml.safe_load(p.read_text(encoding='utf-8'))
    return data if data is not None else {}
