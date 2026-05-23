'''Tests for loom.init: workdir modes, validation rollback.'''
import pytest

import loom
from loom.engine.models import LoomPlan, Task
from loom.errors import (
    WorkdirExistsError, WorkdirNotEmptyError, LoomPlanError, DAGError,
)
from loom.plan import tool, make_plan
from tests.helpers import write_schema


class TestWorkdirCreation:
    def test_creates_new_workdir(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = make_plan(tool('x', cmd=['echo'], output_schema=s))
        wd = tmp_path / 'new_wd'
        rt = loom.init(workdir=wd, plan=plan)
        assert wd.exists()
        assert (wd / 'plan.yaml').exists()
        assert (wd / 'tasks').is_dir()
        assert (wd / 'global').is_dir()

    def test_uses_empty_existing_dir(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = make_plan(tool('x', cmd=['echo'], output_schema=s))
        wd = tmp_path / 'empty_wd'
        wd.mkdir()
        rt = loom.init(workdir=wd, plan=plan)
        assert (wd / 'plan.yaml').exists()

    def test_refuses_existing_plan_yaml(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = make_plan(tool('x', cmd=['echo'], output_schema=s))
        wd = tmp_path / 'wd'
        loom.init(workdir=wd, plan=plan)
        with pytest.raises(WorkdirExistsError, match='plan.yaml'):
            loom.init(workdir=wd, plan=plan)

    def test_refuses_non_empty_dir(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = make_plan(tool('x', cmd=['echo'], output_schema=s))
        wd = tmp_path / 'wd'
        wd.mkdir()
        (wd / 'random.txt').write_text('stuff')
        with pytest.raises(WorkdirNotEmptyError):
            loom.init(workdir=wd, plan=plan)


class TestValidationRollback:
    def test_invalid_plan_leaves_no_disk_state(self, tmp_path):
        wd = tmp_path / 'wd'
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], depends_on=['a']),
        ])
        with pytest.raises(DAGError):
            loom.init(workdir=wd, plan=plan)
        assert not wd.exists()

    def test_missing_schema_leaves_no_disk_state(self, tmp_path):
        wd = tmp_path / 'wd'
        plan = make_plan(
            tool('x', cmd=['echo'], output_schema='/nonexistent.yaml'),
        )
        with pytest.raises(LoomPlanError):
            loom.init(workdir=wd, plan=plan)
        assert not wd.exists()


class TestInitReturnsRuntime:
    def test_runtime_functional(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'val': {'type': 'integer'}},
            'required': ['val'],
        })
        plan = make_plan(
            tool('t1', cmd=['python', '-c', 'import json; print(json.dumps({"val":1}))'],
                 output_schema=s),
        )
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        assert not rt.is_done()
        rt.next()
        assert rt.is_done()
