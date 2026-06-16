'''Curator runtime — thin wrappers over loom lifecycle and execution.'''
from __future__ import annotations

import datetime
import shutil
from pathlib import Path

from slugify import slugify

import loom
from loom.errors import (
    LoomPlanError, RunFailed, RenderFailed, OutputSchemaError, RunAborted,
)

from curator.config import WORKDIR_ROOT, derive_basename
from curator.plan import derive_plan
from curator.utils import emit, fail


def _curator_workdir(url_or_path: str) -> Path:
    '''Date-prefixed ephemeral workdir.

    `<WORKDIR_ROOT>/<YYYY-MM-DD>/<slug>/`
    Wipes any existing dir at the resolved path so re-runs start fresh.
    '''
    today = datetime.date.today().isoformat()
    # 60 chars: filesystem-friendly slug cap — fits in a typical
    # filesystem row and leaves headroom for the date prefix and
    # any per-task suffixes appended below the workdir.
    slug = slugify(derive_basename(url_or_path), max_length=60)
    wd = (Path(WORKDIR_ROOT) / today / slug).expanduser().resolve()
    if wd.exists():
        shutil.rmtree(wd)
    return wd


def cli_ingest(url_or_path: str) -> None:
    '''`curator.sh ingest <url-or-path>` — start a fresh run.'''
    try:
        wd = _curator_workdir(url_or_path)
        wd.parent.mkdir(parents=True, exist_ok=True)
        plan = derive_plan(wd, url_or_path)
        runtime = loom.init(workdir=wd, plan=plan)
    except LoomPlanError as e:
        fail(f'plan validation failed: {e}')
    except Exception as e:
        fail(f'ingest failed: {e}')
    print(runtime.workdir)


def cli_next(workdir: str) -> None:
    '''`curator.sh next <wd>` — advance internal tasks; emit next external
    batch (or done).'''
    wd = Path(workdir).expanduser().resolve()
    try:
        runtime = loom.resume(wd)
    except FileNotFoundError as e:
        fail(str(e))
    try:
        action = runtime.next()
    except RunAborted as e:
        fail(f'run aborted; failed tasks: {", ".join(e.failed_task_ids)}',
             failed_task_ids=e.failed_task_ids)
    except RunFailed as e:
        fail(f'tool task failed: {e.task_id}',
             task_id=e.task_id, detail=e.message)
    except RenderFailed as e:
        fail(f'prompt render failed: {e.task_id}',
             task_id=e.task_id,
             template_path=e.template_path,
             detail=e.message)
    except OutputSchemaError as e:
        fail(f'output schema validation failed: {e.task_id}',
             task_id=e.task_id, detail=e.message)

    if action is None:
        if runtime.is_done():
            emit({'done': True, 'workdir': str(wd)})
        else:
            summary = runtime.status_summary()
            emit({'done': False, 'stuck': True,
                  'workdir': str(wd), 'summary': summary})
        return

    runtime.commit_running([t['id'] for t in action.tasks])

    emit({
        'done': False,
        'workdir': str(action.workdir),
        'ready': action.tasks,
    })


def cli_complete(workdir: str, task_id: str) -> None:
    '''`curator.sh complete <wd> <task-id>` — mark agent/human task done.'''
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
        fail(f'output schema validation failed: {e.task_id}',
             task_id=e.task_id, detail=e.message)
    except (KeyError, ValueError) as e:
        fail(str(e), task_id=task_id)

    emit({'ok': True, 'task_id': task_id, 'workdir': str(wd)})



