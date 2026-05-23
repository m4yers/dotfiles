'''Curator runtime — thin wrappers over loom lifecycle and execution.'''
from __future__ import annotations

import datetime
import shutil
import sys
from pathlib import Path

import yaml
from slugify import slugify

import loom
from loom.errors import (
    LoomPlanError, RunFailed, RenderFailed, OutputSchemaError,
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
    emit({'workdir': str(runtime.workdir),
          'basename': runtime.workdir.name})


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


def cli_gate_list(workdir: str) -> None:
    '''`curator.sh gate-list <wd>` — emit gate review targets as TSV.

    Reads replica from <workdir>/global/vault-replica/.
    '''
    from curator.vault.config import VAULT_ROOT, SYNTHESIS_DIR

    wd = Path(workdir).expanduser().resolve()
    replica = wd / 'global' / 'vault-replica'
    if not replica.exists():
        fail(f'replica not built: {replica}')

    def _emit(*fields: str) -> None:
        print('\t'.join(fields))

    def _warn(msg: str) -> None:
        print(f'warning: {msg}', file=sys.stderr)

    report = replica / '_REPORT.md'
    if report.exists():
        _emit('report', str(report))
    else:
        _warn(f'_REPORT.md missing in replica: {replica}')

    manifest_path = replica / 'manifest.yaml'
    if manifest_path.exists():
        try:
            manifest = yaml.safe_load(
                manifest_path.read_text(encoding='utf-8')) or {}
        except Exception as e:
            fail(f'manifest parse failed: {e}')
        for entry in manifest.get('entries') or []:
            vp = entry.get('vault_path')
            op = entry.get('op')
            if not vp:
                continue
            replica_path = replica / vp
            if not replica_path.exists():
                _warn(f'manifest entry missing on disk: {replica_path}')
                continue
            if op == 'create':
                _emit('manifest-create', str(replica_path))
            else:
                vault_path = VAULT_ROOT / vp
                _emit('manifest-modify', str(vault_path), str(replica_path))

    synth_dir = replica / SYNTHESIS_DIR
    if synth_dir.exists():
        for entry in sorted(synth_dir.iterdir()):
            if not entry.is_file() or entry.suffix != '.md':
                continue
            existing = VAULT_ROOT / SYNTHESIS_DIR / entry.name
            if existing.exists():
                _emit('synthesis-modify', str(existing), str(entry))
            else:
                _emit('synthesis-create', str(entry))
