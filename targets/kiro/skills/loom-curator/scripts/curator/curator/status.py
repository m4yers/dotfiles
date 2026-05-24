'''Status oracle: aggregate verdicts across judge tasks.'''
from __future__ import annotations

from pathlib import Path

import loom
from loom.engine.models import STATUS_FAILED, TERMINAL_STATUSES

from curator.utils import emit, fail


VERDICT_ACCEPT = 'ACCEPT'
VERDICT_REVIEW = 'REVIEW'
VERDICT_REJECT = 'REJECT'
_VERDICTS = (VERDICT_ACCEPT, VERDICT_REVIEW, VERDICT_REJECT)


def cli_status(workdir: str) -> None:
    '''`curator.sh status <wd>` — aggregate verdicts; emit completion status.'''
    wd = Path(workdir).expanduser().resolve()
    if not (wd / 'plan.yaml').exists():
        emit({'status': 'NEEDS_CONTEXT',
              'reason': f'workdir or plan.yaml missing: {wd}',
              'workdir': str(wd)})
        return

    runtime = loom.resume(wd)
    plan = runtime.plan()

    counts = {VERDICT_ACCEPT: 0, VERDICT_REVIEW: 0, VERDICT_REJECT: 0}
    no_verdict = 0
    failed_ids: list[str] = []

    for task in plan.tasks:
        if task.status == STATUS_FAILED:
            failed_ids.append(task.id)
        if not task.id.startswith('judge-'):
            continue
        if task.status == STATUS_SKIPPED:
            continue
        out = runtime.task_output(task.id)
        v = (out or {}).get('verdict')
        if v in _VERDICTS:
            counts[v] += 1
        else:
            no_verdict += 1

    summary = {
        'workdir':      str(wd),
        'verdicts':     counts,
        'no_verdict':   no_verdict,
        'failed_tasks': failed_ids,
    }

    if failed_ids:
        emit({'status': 'BLOCKED', **summary})
        return
    if not runtime.is_done():
        non_terminal = [t.id for t in plan.tasks
                        if t.status not in TERMINAL_STATUSES]
        emit({'status': 'IN_PROGRESS',
              'pending_tasks': non_terminal, **summary})
        return
    if counts[VERDICT_REJECT] > 0:
        emit({'status': 'DONE_WITH_CONCERNS', **summary})
        return
    emit({'status': 'DONE', **summary})
