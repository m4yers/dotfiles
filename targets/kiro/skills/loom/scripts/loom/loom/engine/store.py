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
    '''READ path: the output.yaml a consumer should read.

    For a non-loop task this is the flat ``<task_dir>/output.yaml``.
    For a loop-body task it is the latest *completed* round's output —
    the highest ``iter-NN/`` dir that contains an ``output.yaml`` (or
    ``iter-00`` before the first round completes, which resolves to a
    not-yet-existing file and is handled as "no output" by callers).
    '''
    td = task_dir(workdir, plan, task_id)
    if not _is_loop_body(plan, task_id):
        return td / 'output.yaml'
    completed = [d for d in _iter_dirs(td) if (d / 'output.yaml').exists()]
    if completed:
        return completed[-1] / 'output.yaml'
    return td / 'iter-00' / 'output.yaml'


def task_output_write_path(workdir: Path, plan: LoomPlan, task_id: str) -> Path:
    '''WRITE path: where the current round's output.yaml is written.

    For a non-loop task this equals ``task_output_path``. For a loop-body
    task it is the latest ``iter-NN/`` dir, regardless of whether
    ``output.yaml`` already exists in it — round identity comes from the
    directory existing, not from whether the round has been written. This
    keeps the path stable within a round across both ``next`` (which calls
    this before the agent writes) and ``complete`` (which calls it after).
    Round advancement is the exclusive responsibility of ``begin_round``.

    Before the first ``begin_round`` call, falls back to ``iter-00`` so
    early callers still see a deterministic path; that file will not exist
    yet and ``complete`` will surface the missing output.
    '''
    td = task_dir(workdir, plan, task_id)
    if not _is_loop_body(plan, task_id):
        return td / 'output.yaml'
    existing = _iter_dirs(td)
    if existing:
        return existing[-1] / 'output.yaml'
    return td / 'iter-00' / 'output.yaml'


def _is_loop_body(plan: LoomPlan, task_id: str) -> bool:
    '''True if the task participates in any loop region.

    A self-loop's body is its latch; a multi-node loop's body is the
    natural loop of the back-edge. Computed from the plan's latch blocks.
    '''
    from loom.engine import loops
    return task_id in loops.region_members(plan)


def _iter_dirs(task_dir_path: Path) -> list[Path]:
    '''Sorted list of existing ``iter-NN`` subdirs of a task dir.'''
    if not task_dir_path.exists():
        return []
    out = []
    for d in task_dir_path.iterdir():
        if d.is_dir() and d.name.startswith('iter-'):
            suffix = d.name[len('iter-'):]
            if suffix.isdigit():
                out.append(d)
    return sorted(out, key=lambda p: int(p.name[len('iter-'):]))


def begin_round(workdir: Path, plan: LoomPlan, task_id: str) -> Path:
    '''Create and return the iter dir for a fresh loop round.

    Called once per round when a loop-body task is activated
    (pending -> ready/running). The new index is one past the highest
    existing iter dir, so each activation gets its own round directory.
    Idempotent only across distinct rounds — call exactly once per
    activation.
    '''
    td = ensure_task_dir(workdir, plan, task_id)
    existing = _iter_dirs(td)
    nxt = (int(existing[-1].name[len('iter-'):]) + 1) if existing else 0
    d = td / f'iter-{nxt:02d}'
    d.mkdir(parents=True, exist_ok=True)
    return d

def clear_iterations(workdir: Path, plan: LoomPlan, task_id: str) -> None:
    '''Remove all iter-NN/ round dirs of a loop-body task so round
    indexing restarts at iter-00. No-op for missing dirs.'''
    import shutil
    td = task_dir(workdir, plan, task_id)
    for d in _iter_dirs(td):
        shutil.rmtree(d, ignore_errors=True)



def _completed_iter_indices(task_dir_path: Path) -> list[int]:
    '''Sorted indices of iter dirs that contain an output.yaml.'''
    return sorted(
        int(d.name[len('iter-'):])
        for d in _iter_dirs(task_dir_path)
        if (d / 'output.yaml').exists()
    )


def iteration_output_path(
    workdir: Path, plan: LoomPlan, task_id: str, selector: str | int,
) -> Path | None:
    '''Resolve a specific iteration's output.yaml for a loop-body task.

    ``selector`` is an absolute round index (int / digit string) or the
    literal ``'prev'`` — the iteration immediately before the latest
    *completed* one (i.e. ``completed[-2]``). Returns ``None`` when the
    requested iteration does not exist (e.g. ``prev`` with fewer than two
    completed rounds, or an out-of-range index), which callers treat as a
    missing value.

    ``prev`` is defined relative to the latest completed round, so it is
    meant for post-round contexts such as a ``while`` predicate. During a
    round's own execution the latest completed output already *is* the
    previous round, reachable with a plain ``${task:id}`` reference.
    '''
    td = task_dir(workdir, plan, task_id)
    completed = _completed_iter_indices(td)
    if selector == 'prev':
        if len(completed) >= 2:
            idx = completed[-2]
        else:
            return None
    else:
        try:
            idx = int(selector)
        except (TypeError, ValueError):
            return None
        if idx not in completed:
            return None
    return td / f'iter-{idx:02d}' / 'output.yaml'


def load_task_output(workdir: Path, plan: LoomPlan, task_id: str) -> dict:
    p = task_output_path(workdir, plan, task_id)
    if not p.exists():
        raise FileNotFoundError(f'output.yaml missing for {task_id!r}: {p}')
    data = yaml.safe_load(p.read_text(encoding='utf-8'))
    return data if data is not None else {}
