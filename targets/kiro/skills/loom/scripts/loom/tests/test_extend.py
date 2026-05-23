'''Tests for loom.extend: merge, dup id, atomic write.'''
import pytest

import loom
from loom.engine.models import LoomPlan, Task
from loom.errors import LoomPlanError
from loom.plan import tool, agent, make_plan
from tests.helpers import write_schema, write_template


class TestExtendMerge:
    def test_appends_new_tasks(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan1 = make_plan(tool('a', cmd=['echo'], output_schema=s))
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan1)

        plan2 = make_plan(tool('b', cmd=['echo'], output_schema=s, depends_on=['a']))
        loom.extend(rt, plan2)

        p = rt.plan()
        assert p.ids() == {'a', 'b'}
        assert p.get('b').depends_on == ['a']

    def test_new_task_references_existing(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'val': {'type': 'integer'}},
        })
        plan1 = make_plan(tool('a', cmd=['echo'], output_schema=s))
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan1)

        plan2 = make_plan(
            tool('b', cmd=['echo', '${task:a:val}'], output_schema=s,
                 depends_on=['a']),
        )
        loom.extend(rt, plan2)  # should not raise


class TestExtendDuplicateId:
    def test_dup_with_existing_raises(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan1 = make_plan(tool('a', cmd=['echo'], output_schema=s))
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan1)

        plan2 = make_plan(tool('a', cmd=['echo'], output_schema=s))
        with pytest.raises(LoomPlanError, match='already exists'):
            loom.extend(rt, plan2)

    def test_dup_within_new_raises(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan1 = make_plan(tool('a', cmd=['echo'], output_schema=s))
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan1)

        plan2 = LoomPlan(tasks=[
            Task(id='b', kind='tool', cmd=['echo'], output_schema=str(s)),
            Task(id='b', kind='tool', cmd=['echo'], output_schema=str(s)),
        ])
        with pytest.raises(LoomPlanError, match='duplicate'):
            loom.extend(rt, plan2)


class TestExtendAtomicity:
    def test_failed_validation_leaves_plan_unchanged(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan1 = make_plan(tool('a', cmd=['echo'], output_schema=s))
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan1)

        # Invalid: cycle in new tasks
        plan2 = LoomPlan(tasks=[
            Task(id='b', kind='tool', cmd=['echo'], output_schema=str(s),
                 depends_on=['c']),
            Task(id='c', kind='tool', cmd=['echo'], output_schema=str(s),
                 depends_on=['b']),
        ])
        with pytest.raises(LoomPlanError):
            loom.extend(rt, plan2)

        # Plan unchanged
        p = rt.plan()
        assert p.ids() == {'a'}
