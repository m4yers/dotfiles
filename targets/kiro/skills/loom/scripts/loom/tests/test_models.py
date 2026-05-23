'''Tests for Task, LoomPlan, ActionSpec dataclass behavior; status constants.'''
from pathlib import Path

import pytest

from loom.engine.models import (
    Task, LoomPlan, ActionSpec,
    VALID_STATUSES, TERMINAL_STATUSES,
    STATUS_PENDING, STATUS_READY, STATUS_RUNNING,
    STATUS_DONE, STATUS_FAILED, STATUS_SKIPPED,
)


class TestStatusConstants:
    def test_valid_statuses_has_six(self):
        assert len(VALID_STATUSES) == 6
        assert set(VALID_STATUSES) == {
            'pending', 'ready', 'running', 'done', 'failed', 'skipped'}

    def test_terminal_statuses_has_three(self):
        assert set(TERMINAL_STATUSES) == {'done', 'failed', 'skipped'}

    def test_terminal_is_subset_of_valid(self):
        assert set(TERMINAL_STATUSES).issubset(set(VALID_STATUSES))


class TestTask:
    def test_construct_tool(self):
        t = Task(id='x', kind='tool', cmd=['echo'])
        assert t.id == 'x'
        assert t.kind == 'tool'
        assert t.status == STATUS_PENDING

    def test_construct_agent(self):
        t = Task(id='a', kind='agent', template='/t.j2', output_schema='/s.yaml')
        assert t.kind == 'agent'
        assert t.template == '/t.j2'

    def test_construct_human(self):
        t = Task(id='h', kind='human')
        assert t.kind == 'human'
        assert t.output_schema is None

    def test_defaults(self):
        t = Task(id='x', kind='tool')
        assert t.depends_on == []
        assert t.when is None
        assert t.vars == {}
        assert t.status == STATUS_PENDING

    def test_to_dict_omits_none_and_empty(self):
        t = Task(id='x', kind='tool', cmd=['echo'])
        d = t.to_dict()
        assert 'when' not in d
        assert 'template' not in d
        assert 'depends_on' not in d
        assert 'vars' not in d

    def test_to_dict_preserves_values(self):
        t = Task(id='x', kind='tool', cmd=['echo'], output_schema='/s.yaml',
                 depends_on=['a'])
        d = t.to_dict()
        assert d['id'] == 'x'
        assert d['cmd'] == ['echo']
        assert d['depends_on'] == ['a']

    def test_from_dict_roundtrip(self):
        t = Task(id='x', kind='agent', template='/t.j2',
                 output_schema='/s.yaml', depends_on=['a'],
                 vars={'k': 'v'}, when='task.a.val > `0`')
        d = t.to_dict()
        t2 = Task.from_dict(d)
        assert t2.id == t.id
        assert t2.kind == t.kind
        assert t2.template == t.template
        assert t2.depends_on == t.depends_on
        assert t2.vars == t.vars
        assert t2.when == t.when

    def test_from_dict_ignores_unknown_keys(self):
        d = {'id': 'x', 'kind': 'tool', 'cmd': ['echo'], 'unknown_field': 123}
        t = Task.from_dict(d)
        assert t.id == 'x'


class TestLoomPlan:
    def test_get_returns_task(self):
        t = Task(id='x', kind='tool', cmd=['echo'])
        plan = LoomPlan(tasks=[t])
        assert plan.get('x') is t

    def test_get_raises_keyerror(self):
        plan = LoomPlan(tasks=[Task(id='x', kind='tool', cmd=['echo'])])
        with pytest.raises(KeyError, match='missing'):
            plan.get('missing')

    def test_ids_returns_full_set(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo']),
            Task(id='b', kind='agent', template='/t.j2'),
        ])
        assert plan.ids() == {'a', 'b'}

    def test_to_dict_from_dict_roundtrip(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema='/s.yaml'),
            Task(id='b', kind='agent', template='/t.j2', output_schema='/s.yaml',
                 depends_on=['a']),
        ])
        d = plan.to_dict()
        plan2 = LoomPlan.from_dict(d)
        assert plan2.ids() == plan.ids()
        assert plan2.get('a').cmd == ['echo']
        assert plan2.get('b').depends_on == ['a']

    def test_empty_plan(self):
        plan = LoomPlan()
        assert plan.ids() == set()
        assert plan.to_dict() == {'tasks': []}


class TestActionSpec:
    def test_construct(self):
        spec = ActionSpec(workdir=Path('/tmp'), tasks=[{'id': 'x'}])
        assert spec.workdir == Path('/tmp')
        assert spec.tasks == [{'id': 'x'}]

    def test_empty_tasks(self):
        spec = ActionSpec(workdir=Path('/w'), tasks=[])
        assert len(spec.tasks) == 0
