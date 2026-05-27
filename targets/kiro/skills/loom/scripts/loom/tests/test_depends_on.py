'''Tests for depends_on_all / depends_on_any explicit fields and
the deprecation of legacy depends_on=.

Covers:
  - readiness (compute_ready_set, all_deps_terminal) for both lists
  - cascade-skip (partition_ready) for both lists
  - factory functions emit FutureWarning when depends_on= is used
  - Task.from_dict silently migrates legacy depends_on
  - Task.to_dict emits depends_on_all (not the legacy field)
  - mixing depends_on with depends_on_all raises
'''
from __future__ import annotations

import warnings

import pytest
import yaml

from loom.engine.models import Task, LoomPlan
from loom.engine.algorithm import (
    all_deps_terminal, compute_ready_set, partition_ready,
)
from loom.errors import LoomPlanError
from loom.plan import tool, agent, human, make_plan


# ---- readiness ----


class TestReadinessAllList:
    '''depends_on_all: every dep must be terminal.'''

    def test_all_done_ready(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['x'], status='done'),
            Task(id='b', kind='tool', cmd=['x'], status='done'),
            Task(id='c', kind='tool', cmd=['x'], depends_on_all=['a', 'b']),
        ])
        assert all_deps_terminal(plan.get('c'), plan)

    def test_one_pending_blocks(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['x'], status='done'),
            Task(id='b', kind='tool', cmd=['x'], status='pending'),
            Task(id='c', kind='tool', cmd=['x'], depends_on_all=['a', 'b']),
        ])
        assert not all_deps_terminal(plan.get('c'), plan)

    def test_failed_dep_satisfies(self):
        # Same as legacy depends_on: any terminal status counts.
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['x'], status='failed'),
            Task(id='c', kind='tool', cmd=['x'], depends_on_all=['a']),
        ])
        assert all_deps_terminal(plan.get('c'), plan)


class TestReadinessAnyList:
    '''depends_on_any: at least one dep must be terminal.'''

    def test_one_done_ready(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['x'], status='done'),
            Task(id='b', kind='tool', cmd=['x'], status='pending'),
            Task(id='c', kind='tool', cmd=['x'], depends_on_any=['a', 'b']),
        ])
        assert all_deps_terminal(plan.get('c'), plan)

    def test_none_terminal_blocks(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['x'], status='pending'),
            Task(id='b', kind='tool', cmd=['x'], status='running'),
            Task(id='c', kind='tool', cmd=['x'], depends_on_any=['a', 'b']),
        ])
        assert not all_deps_terminal(plan.get('c'), plan)

    def test_all_skipped_satisfies_terminal_check(self):
        # All-skipped is terminal, so the readiness predicate
        # accepts it. The cascade-skip path (tested below) is
        # what handles the "no upstream" case.
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['x'], status='skipped'),
            Task(id='b', kind='tool', cmd=['x'], status='skipped'),
            Task(id='c', kind='tool', cmd=['x'], depends_on_any=['a', 'b']),
        ])
        assert all_deps_terminal(plan.get('c'), plan)


class TestReadinessBothLists:
    '''Combined: all-list AND any-list must be satisfied.'''

    def test_all_done_any_done_ready(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['x'], status='done'),
            Task(id='b', kind='tool', cmd=['x'], status='done'),
            Task(id='x', kind='tool', cmd=['x'],
                 depends_on_all=['a'], depends_on_any=['b']),
        ])
        assert all_deps_terminal(plan.get('x'), plan)

    def test_all_done_any_pending_blocks(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['x'], status='done'),
            Task(id='b', kind='tool', cmd=['x'], status='pending'),
            Task(id='x', kind='tool', cmd=['x'],
                 depends_on_all=['a'], depends_on_any=['b']),
        ])
        assert not all_deps_terminal(plan.get('x'), plan)

    def test_all_pending_any_done_blocks(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['x'], status='pending'),
            Task(id='b', kind='tool', cmd=['x'], status='done'),
            Task(id='x', kind='tool', cmd=['x'],
                 depends_on_all=['a'], depends_on_any=['b']),
        ])
        assert not all_deps_terminal(plan.get('x'), plan)


# ---- cascade-skip ----


class TestCascadeAnyList:
    '''Cascade-skip when depends_on_any is non-empty and every
    listed task is skipped.'''

    def test_all_any_skipped_cascades(self, tmp_path):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['x'], status='skipped'),
            Task(id='b', kind='tool', cmd=['x'], status='skipped'),
            Task(id='c', kind='tool', cmd=['x'], depends_on_any=['a', 'b']),
        ])
        runnable, skipped = partition_ready(
            [plan.get('c')], plan, tmp_path)
        assert runnable == []
        assert len(skipped) == 1
        assert 'any-deps skipped' in skipped[0][1]

    def test_any_partial_skipped_runs(self, tmp_path):
        # One skipped, one done — task runs (any-list satisfied).
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['x'], status='skipped'),
            Task(id='b', kind='tool', cmd=['x'], status='done'),
            Task(id='c', kind='tool', cmd=['x'], depends_on_any=['a', 'b']),
        ])
        runnable, skipped = partition_ready(
            [plan.get('c')], plan, tmp_path)
        assert len(runnable) == 1 and runnable[0].id == 'c'
        assert skipped == []

    def test_all_list_alive_but_any_all_skipped_cascades(self, tmp_path):
        # depends_on_all is satisfied (a done) but depends_on_any
        # has no live upstream. Cascade.
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['x'], status='done'),
            Task(id='b', kind='tool', cmd=['x'], status='skipped'),
            Task(id='c', kind='tool', cmd=['x'], status='skipped'),
            Task(id='x', kind='tool', cmd=['x'],
                 depends_on_all=['a'], depends_on_any=['b', 'c']),
        ])
        runnable, skipped = partition_ready(
            [plan.get('x')], plan, tmp_path)
        assert runnable == []
        assert len(skipped) == 1
        assert 'any-deps skipped' in skipped[0][1]


# ---- factory deprecation ----


class TestFactoryDeprecation:
    '''Each factory emits FutureWarning when called with the
    deprecated depends_on= kwarg.'''

    def test_tool_warns(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            tool('x', cmd=['echo'], output_schema='/s.yaml',
                 depends_on=['a'])
        future_warnings = [w for w in caught
                           if issubclass(w.category, FutureWarning)]
        assert len(future_warnings) == 1
        assert 'depends_on=' in str(future_warnings[0].message)
        assert 'depends_on_all=' in str(future_warnings[0].message)

    def test_agent_warns(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            agent('x', template='/t.j2', output_schema='/s.yaml',
                  depends_on=['a'])
        future_warnings = [w for w in caught
                           if issubclass(w.category, FutureWarning)]
        assert len(future_warnings) == 1

    def test_human_warns(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            human('x', depends_on=['a'])
        future_warnings = [w for w in caught
                           if issubclass(w.category, FutureWarning)]
        assert len(future_warnings) == 1

    def test_no_warning_when_using_new_kwarg(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            tool('x', cmd=['echo'], output_schema='/s.yaml',
                 depends_on_all=['a'])
            agent('y', template='/t.j2', output_schema='/s.yaml',
                  depends_on_any=['a'])
        future_warnings = [w for w in caught
                           if issubclass(w.category, FutureWarning)]
        assert future_warnings == []

    def test_legacy_routes_to_all(self):
        '''depends_on= must populate depends_on_all (current
        wait-for-all semantics).'''
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', FutureWarning)
            t = tool('x', cmd=['echo'], output_schema='/s.yaml',
                     depends_on=['a', 'b'])
        assert t.depends_on_all == ['a', 'b']
        assert t.depends_on_any == []


class TestFactoryConflict:
    '''Mixing depends_on= and depends_on_all= raises immediately.'''

    def test_tool_conflict(self):
        with pytest.raises(ValueError, match='cannot coexist'):
            tool('x', cmd=['echo'], output_schema='/s.yaml',
                 depends_on=['a'], depends_on_all=['b'])

    def test_agent_conflict(self):
        with pytest.raises(ValueError, match='cannot coexist'):
            agent('x', template='/t.j2', output_schema='/s.yaml',
                  depends_on=['a'], depends_on_all=['b'])


# ---- Task constructor + (de)serialization ----


class TestTaskConstruction:
    def test_legacy_depends_on_migrates_silently(self):
        # __post_init__ migrates without warning (the warning fires
        # at the public entry points: factories + from_dict callers).
        t = Task(id='x', kind='tool', cmd=['echo'],
                 depends_on=['a', 'b'])
        assert t.depends_on_all == ['a', 'b']
        assert t.depends_on_any == []
        # The deprecated attribute stays populated as the union for
        # back-compat readers (templates, viz layout, etc.).
        assert t.depends_on == ['a', 'b']

    def test_depends_on_is_union(self):
        t = Task(id='x', kind='tool', cmd=['echo'],
                 depends_on_all=['a'], depends_on_any=['b'])
        assert t.depends_on == ['a', 'b']

    def test_depends_on_union_dedupes(self):
        # Same id in both lists should appear once in the union.
        t = Task(id='x', kind='tool', cmd=['echo'],
                 depends_on_all=['a'], depends_on_any=['a', 'b'])
        assert t.depends_on == ['a', 'b']

    def test_post_init_conflict_raises(self):
        with pytest.raises(LoomPlanError, match='cannot coexist'):
            Task(id='x', kind='tool', cmd=['echo'],
                 depends_on=['a'], depends_on_all=['b'])

    def test_all_deps_returns_union(self):
        t = Task(id='x', kind='tool', cmd=['echo'],
                 depends_on_all=['a'], depends_on_any=['b'])
        assert t.all_deps() == ['a', 'b']


class TestTaskSerialization:
    def test_to_dict_emits_new_fields(self):
        t = Task(id='x', kind='tool', cmd=['echo'], output_schema='/s.yaml',
                 depends_on_all=['a'], depends_on_any=['b'])
        d = t.to_dict()
        assert d['depends_on_all'] == ['a']
        assert d['depends_on_any'] == ['b']
        assert 'depends_on' not in d

    def test_to_dict_skips_legacy_after_migration(self):
        t = Task(id='x', kind='tool', cmd=['echo'], output_schema='/s.yaml',
                 depends_on=['a'])
        d = t.to_dict()
        assert d['depends_on_all'] == ['a']
        assert 'depends_on' not in d
        assert 'depends_on_any' not in d   # empty lists omitted

    def test_from_dict_legacy_silent(self):
        # Loading old plan.yaml carrying depends_on: must not warn
        # (data deserialization is silent; only code-level usage warns).
        d = {'id': 'x', 'kind': 'tool', 'cmd': ['echo'],
             'output_schema': '/s.yaml', 'depends_on': ['a']}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            t = Task.from_dict(d)
        future_warnings = [w for w in caught
                           if issubclass(w.category, FutureWarning)]
        assert future_warnings == []
        assert t.depends_on_all == ['a']

    def test_from_dict_conflict_raises(self):
        d = {'id': 'x', 'kind': 'tool', 'cmd': ['echo'],
             'output_schema': '/s.yaml',
             'depends_on': ['a'], 'depends_on_all': ['b']}
        with pytest.raises(LoomPlanError, match='cannot coexist'):
            Task.from_dict(d)

    def test_roundtrip_new_fields(self):
        t = Task(id='x', kind='tool', cmd=['echo'], output_schema='/s.yaml',
                 depends_on_all=['a'], depends_on_any=['b'])
        d = t.to_dict()
        t2 = Task.from_dict(d)
        assert t2.depends_on_all == ['a']
        assert t2.depends_on_any == ['b']
        assert t2.depends_on == ['a', 'b']

    def test_roundtrip_legacy_input_emits_new_format(self):
        # Construct with legacy field; round-trip yields new format.
        t = Task(id='x', kind='tool', cmd=['echo'], output_schema='/s.yaml',
                 depends_on=['a'])
        d = t.to_dict()
        # Re-loaded plan would carry the new field name on disk.
        assert 'depends_on' not in d
        assert d['depends_on_all'] == ['a']

        # Round-trip through YAML to make sure the format is stable.
        text = yaml.safe_dump(d)
        d2 = yaml.safe_load(text)
        t2 = Task.from_dict(d2)
        assert t2.depends_on_all == ['a']
