'''Integration tests for the curator runtime loop.

Tests plan structure, predicate-based skipping, and status machinery.
All tasks are force-completed (bypassing subprocess and template
rendering). A module-scoped fixture drives the loop once; individual
tests assert against the final state.
'''
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import loom
from loom.engine import store, algorithm
from loom.engine.models import (
    STATUS_DONE, STATUS_SKIPPED, STATUS_PENDING, TERMINAL_STATUSES,
)
from curator.plan import derive_plan


# Known quintet: paper/research/non_fiction/cs/academic
CLASSIFY_OUTPUT = {
    'quintet': {
        'media': 'paper', 'form': 'research',
        'register': 'non_fiction', 'discipline': 'cs',
        'audience': 'academic',
    },
    'topic': 'distributed systems consensus algorithms',
}

# Extractors that should RUN with this quintet
EXPECTED_RUN = {
    'authors', 'abstract', 'citations', 'contributions',
    'methods', 'results', 'topics', 'models', 'keywords',
}

# Extractors that should be SKIPPED
EXPECTED_SKIP = {
    'chapters', 'characters', 'code_examples', 'exercises',
    'guests', 'key_points', 'people', 'quotes',
    'setting', 'speaker', 'story', 'themes',
}


def _stub_output(task_id: str, gate_proceed: bool = True) -> dict:
    if task_id == 'extract-classify':
        return CLASSIFY_OUTPUT
    if task_id.startswith('judge-'):
        return {'verdict': 'ACCEPT', 'reasons': []}
    if task_id == 'vault-gate':
        return {'proceed': gate_proceed}
    if task_id == 'source-fetch':
        return {'path': '/tmp/fake-source.txt'}
    if task_id == 'source-convert':
        return {'converted_path': '/tmp/fake-converted.md'}
    return {}


def _drive_all(rt, gate_proceed=True):
    '''Drive all tasks to terminal state using predicate evaluation.'''
    for _ in range(100):
        plan = store.load_plan(rt.workdir)
        if algorithm.is_done(plan):
            break
        candidates = algorithm.compute_ready_set(plan)
        if not candidates:
            break
        runnable, skipped, failed = algorithm.partition_ready(
            candidates, plan, rt.workdir)
        for t, reason in skipped:
            task = plan.get(t.id)
            td = store.ensure_task_dir(rt.workdir, plan, t.id)
            (td / 'skip-reason.log').write_text(reason, encoding='utf-8')
            task.status = STATUS_SKIPPED
        for t in runnable:
            task = plan.get(t.id)
            store.ensure_task_dir(rt.workdir, plan, t.id)
            op = store.task_output_path(rt.workdir, plan, t.id)
            op.write_text(
                yaml.safe_dump(_stub_output(t.id, gate_proceed),
                               sort_keys=False, allow_unicode=True),
                encoding='utf-8',
            )
            task.status = STATUS_DONE
        store.save_plan(rt.workdir, plan)


@pytest.fixture(scope='module')
def completed_runtime(tmp_path_factory):
    '''Module-scoped: drive the full plan once with gate.proceed=true.'''
    wd = tmp_path_factory.mktemp('runtime')
    plan = derive_plan(wd, '/tmp/test-source.txt')
    rt = loom.init(workdir=wd, plan=plan)
    _drive_all(rt)
    return rt


@pytest.fixture(scope='module')
def gate_false_runtime(tmp_path_factory):
    '''Module-scoped: drive with gate.proceed=false.'''
    wd = tmp_path_factory.mktemp('gate-false')
    plan = derive_plan(wd, '/tmp/test-source.txt')
    rt = loom.init(workdir=wd, plan=plan)
    _drive_all(rt, gate_proceed=False)
    return rt


class TestFullLoop:
    def test_completes(self, completed_runtime):
        assert completed_runtime.is_done()

    def test_expected_extractors_run(self, completed_runtime):
        plan = completed_runtime.plan()
        for kind in EXPECTED_RUN:
            t = plan.get(f'extract-{kind}')
            assert t.status == STATUS_DONE, \
                f'extract-{kind} should be DONE, got {t.status}'

    def test_expected_extractors_skip(self, completed_runtime):
        plan = completed_runtime.plan()
        for kind in EXPECTED_SKIP:
            t = plan.get(f'extract-{kind}')
            assert t.status == STATUS_SKIPPED, \
                f'extract-{kind} should be SKIPPED, got {t.status}'

    def test_status_counts(self, completed_runtime):
        summary = completed_runtime.status_summary()
        assert summary['is_done']
        counts = summary['counts']
        assert counts.get('pending', 0) == 0
        assert counts.get('ready', 0) == 0
        assert counts.get('running', 0) == 0
        assert counts['done'] > 0
        assert counts['skipped'] > 0

    def test_all_tasks_terminal(self, completed_runtime):
        plan = completed_runtime.plan()
        for t in plan.tasks:
            assert t.status in TERMINAL_STATUSES, \
                f'{t.id} not terminal: {t.status}'


class TestGateFalse:
    def test_completes(self, gate_false_runtime):
        assert gate_false_runtime.is_done()

    def test_apply_replica_skipped(self, gate_false_runtime):
        plan = gate_false_runtime.plan()
        assert plan.get('apply-replica').status == STATUS_SKIPPED

    def test_strip_dead_links_skipped(self, gate_false_runtime):
        plan = gate_false_runtime.plan()
        assert plan.get('strip-dead-links').status == STATUS_SKIPPED


class TestPlanStructure:
    def test_gate_is_human_task(self, tmp_path):
        plan = derive_plan(tmp_path, '/tmp/test.txt')
        gate = next(t for t in plan.tasks if t.id == 'vault-gate')
        assert gate.kind == 'human'

    def test_apply_replica_gated_by_proceed(self, tmp_path):
        plan = derive_plan(tmp_path, '/tmp/test.txt')
        apply_task = next(t for t in plan.tasks if t.id == 'apply-replica')
        assert 'vault-gate' in apply_task.when
        assert 'proceed' in apply_task.when

    def test_in_progress_before_done(self, tmp_path):
        wd = tmp_path / 'partial'
        plan = derive_plan(wd, '/tmp/test.txt')
        rt = loom.init(workdir=wd, plan=plan)

        # Complete only source-fetch
        p = store.load_plan(rt.workdir)
        t = p.get('source-fetch')
        store.ensure_task_dir(rt.workdir, p, 'source-fetch')
        op = store.task_output_path(rt.workdir, p, 'source-fetch')
        op.write_text(yaml.safe_dump({'path': '/tmp/x'}), encoding='utf-8')
        t.status = STATUS_DONE
        store.save_plan(rt.workdir, p)

        summary = rt.status_summary()
        assert not summary['is_done']
        assert summary['counts']['done'] == 1
        assert summary['counts']['pending'] > 0
