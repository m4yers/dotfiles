'''Tests for loom.visualise.layout.'''
from __future__ import annotations

import pytest

from loom.engine.models import Task, LoomPlan
from loom.visualise.layout import layer_of, layer_of_all


def _t(id, deps=None):
    return Task(id=id, kind='tool', cmd=['echo'], depends_on=list(deps or []))


class TestLayerOf:
    def test_no_deps_is_layer_zero(self):
        plan = LoomPlan(tasks=[_t('a')])
        assert layer_of(plan.tasks[0], plan) == 0

    def test_single_chain(self):
        plan = LoomPlan(tasks=[
            _t('a'), _t('b', ['a']), _t('c', ['b']),
        ])
        depths = [layer_of(t, plan) for t in plan.tasks]
        assert depths == [0, 1, 2]

    def test_diamond_uses_longest_path(self):
        # a -> b, a -> c, c -> d, b -> d  (longest path a-c-d-...)
        plan = LoomPlan(tasks=[
            _t('a'), _t('b', ['a']), _t('c', ['b']),
            _t('d', ['a', 'c']),
        ])
        # d depends on a (depth 0) and c (depth 2) → depth 3
        assert layer_of(plan.get('d'), plan) == 3

    def test_missing_dep_is_ignored(self):
        # Validation rejects missing deps, but at viz time be permissive.
        plan = LoomPlan(tasks=[_t('a', ['ghost'])])
        # No real deps → treat as layer 0
        assert layer_of(plan.tasks[0], plan) == 0


class TestLayerOfAll:
    def test_empty_plan(self):
        assert layer_of_all(LoomPlan()) == []

    def test_single_task(self):
        plan = LoomPlan(tasks=[_t('a')])
        layers = layer_of_all(plan)
        assert len(layers) == 1
        assert [t.id for t in layers[0]] == ['a']

    def test_linear_chain(self):
        plan = LoomPlan(tasks=[
            _t('a'), _t('b', ['a']), _t('c', ['b']),
        ])
        layers = layer_of_all(plan)
        assert [[t.id for t in lay] for lay in layers] == [
            ['a'], ['b'], ['c'],
        ]

    def test_fork_layer_two_siblings(self):
        plan = LoomPlan(tasks=[
            _t('root'), _t('left', ['root']), _t('right', ['root']),
            _t('joined', ['left', 'right']),
        ])
        layers = layer_of_all(plan)
        assert len(layers) == 3
        assert [t.id for t in layers[0]] == ['root']
        assert sorted(t.id for t in layers[1]) == ['left', 'right']
        assert [t.id for t in layers[2]] == ['joined']

    def test_stable_order_within_layer(self):
        # Two roots; output preserves plan-author order.
        plan = LoomPlan(tasks=[
            _t('first'), _t('second'), _t('third'),
        ])
        layers = layer_of_all(plan)
        assert [t.id for t in layers[0]] == ['first', 'second', 'third']

    def test_multiple_roots(self):
        plan = LoomPlan(tasks=[
            _t('root1'), _t('root2'),
            _t('child', ['root1', 'root2']),
        ])
        layers = layer_of_all(plan)
        assert len(layers) == 2
        assert sorted(t.id for t in layers[0]) == ['root1', 'root2']
        assert [t.id for t in layers[1]] == ['child']
