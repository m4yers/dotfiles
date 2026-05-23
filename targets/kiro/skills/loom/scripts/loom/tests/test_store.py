'''Tests for plan.yaml I/O, atomic writes, task dirs.'''
from pathlib import Path

import pytest
import yaml

from loom.engine import store
from loom.engine.models import Task, LoomPlan


class TestPlanIO:
    def test_save_load_roundtrip(self, tmp_workdir):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema='/s.yaml'),
            Task(id='b', kind='agent', template='/t.j2', output_schema='/s.yaml',
                 depends_on=['a']),
        ])
        tmp_workdir.mkdir(parents=True)
        store.save_plan(tmp_workdir, plan)
        loaded = store.load_plan(tmp_workdir)
        assert loaded.ids() == {'a', 'b'}
        assert loaded.get('a').cmd == ['echo']
        assert loaded.get('b').depends_on == ['a']

    def test_save_creates_tasks_and_global_dirs(self, tmp_workdir):
        plan = LoomPlan(tasks=[Task(id='x', kind='tool', cmd=['echo'])])
        tmp_workdir.mkdir(parents=True)
        store.save_plan(tmp_workdir, plan)
        assert (tmp_workdir / 'tasks').is_dir()
        assert (tmp_workdir / 'global').is_dir()

    def test_load_missing_raises(self, tmp_workdir):
        tmp_workdir.mkdir(parents=True)
        with pytest.raises(FileNotFoundError, match='plan.yaml'):
            store.load_plan(tmp_workdir)

    def test_atomic_write_no_partial(self, tmp_workdir):
        '''Verify tmp file is used (no .tmp left behind on success).'''
        plan = LoomPlan(tasks=[Task(id='x', kind='tool', cmd=['echo'])])
        tmp_workdir.mkdir(parents=True)
        store.save_plan(tmp_workdir, plan)
        tmp_file = tmp_workdir / 'plan.yaml.tmp'
        assert not tmp_file.exists()
        assert (tmp_workdir / 'plan.yaml').exists()

    def test_preserves_status(self, tmp_workdir):
        t = Task(id='x', kind='tool', cmd=['echo'], status='done')
        plan = LoomPlan(tasks=[t])
        tmp_workdir.mkdir(parents=True)
        store.save_plan(tmp_workdir, plan)
        loaded = store.load_plan(tmp_workdir)
        assert loaded.get('x').status == 'done'


class TestTaskDir:
    def test_first_task_is_01(self, tmp_workdir):
        plan = LoomPlan(tasks=[
            Task(id='alpha', kind='tool', cmd=['echo']),
            Task(id='beta', kind='tool', cmd=['echo']),
        ])
        d = store.task_dir(tmp_workdir, plan, 'alpha')
        assert d == tmp_workdir / 'tasks' / '01-alpha'

    def test_second_task_is_02(self, tmp_workdir):
        plan = LoomPlan(tasks=[
            Task(id='alpha', kind='tool', cmd=['echo']),
            Task(id='beta', kind='tool', cmd=['echo']),
        ])
        d = store.task_dir(tmp_workdir, plan, 'beta')
        assert d == tmp_workdir / 'tasks' / '02-beta'

    def test_unknown_task_raises(self, tmp_workdir):
        plan = LoomPlan(tasks=[Task(id='x', kind='tool', cmd=['echo'])])
        with pytest.raises(KeyError, match='missing'):
            store.task_dir(tmp_workdir, plan, 'missing')

    def test_ensure_task_dir_creates(self, tmp_workdir):
        plan = LoomPlan(tasks=[Task(id='x', kind='tool', cmd=['echo'])])
        tmp_workdir.mkdir(parents=True)
        d = store.ensure_task_dir(tmp_workdir, plan, 'x')
        assert d.is_dir()

    def test_task_output_path(self, tmp_workdir):
        plan = LoomPlan(tasks=[Task(id='x', kind='tool', cmd=['echo'])])
        p = store.task_output_path(tmp_workdir, plan, 'x')
        assert p == tmp_workdir / 'tasks' / '01-x' / 'output.yaml'
