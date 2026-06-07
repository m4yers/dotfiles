'''Tests for loom.visualise.layout.render_order (dependents-first DFS).'''
from __future__ import annotations

from loom.engine.models import Task, LoomPlan
from loom.visualise.layout import render_order


def _t(id, all=None, any=None):
    return Task(id=id, kind='tool', cmd=['echo'],
                depends_on_all=list(all or []),
                depends_on_any=list(any or []))


class TestRenderOrder:
    def test_empty_plan(self):
        assert render_order(LoomPlan()) == []

    def test_single_task(self):
        assert render_order(LoomPlan(tasks=[_t('a')])) == ['a']

    def test_chain_is_dependents_first(self):
        # a <- b <- c  ⇒  emit c, then b, then a (dependents first).
        plan = LoomPlan(tasks=[_t('a'), _t('b', ['a']), _t('c', ['b'])])
        assert render_order(plan) == ['c', 'b', 'a']

    def test_every_task_appears_once(self):
        plan = LoomPlan(tasks=[
            _t('root'), _t('x', ['root']), _t('y', ['root']),
            _t('z', ['x', 'y']),
        ])
        order = render_order(plan)
        assert sorted(order) == ['root', 'x', 'y', 'z']

    def test_dependent_precedes_dependency(self):
        plan = LoomPlan(tasks=[
            _t('root'), _t('x', ['root']), _t('y', ['root']),
            _t('z', ['x', 'y']),
        ])
        order = render_order(plan)
        assert order.index('z') < order.index('x')
        assert order.index('x') < order.index('root')
        assert order.index('y') < order.index('root')

    def test_branches_stay_contiguous(self):
        # setup -> {build, lint}; build -> test; lint -> scan.
        # DFS keeps each branch's chain adjacent rather than interleaving.
        plan = LoomPlan(tasks=[
            _t('setup'), _t('build', ['setup']), _t('lint', ['setup']),
            _t('test', ['build']), _t('scan', ['lint']),
        ])
        order = render_order(plan)
        assert abs(order.index('test') - order.index('build')) == 1
        assert abs(order.index('scan') - order.index('lint')) == 1

    def test_depends_on_any_counts_as_edge(self):
        plan = LoomPlan(tasks=[_t('a'), _t('b', any=['a'])])
        assert render_order(plan) == ['b', 'a']

    def test_missing_dep_ignored(self):
        plan = LoomPlan(tasks=[_t('a', ['ghost'])])
        assert render_order(plan) == ['a']
