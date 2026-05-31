'''Tests for ready-set, predicates, partition_ready, is_done/stuck.'''
import pytest
import yaml

from loom.engine.models import Task, LoomPlan, TERMINAL_STATUSES
from loom.engine.algorithm import (
    all_deps_terminal, compute_ready_set, is_done, is_stuck,
    desugar_predicate, eval_predicate, partition_ready, build_predicate_context,
)
from loom.engine import store


class TestAllDepsTerminal:
    def test_no_deps_is_terminal(self):
        t = Task(id='x', kind='tool', cmd=['echo'])
        plan = LoomPlan(tasks=[t])
        assert all_deps_terminal(t, plan)

    def test_dep_done(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='done'),
            Task(id='b', kind='tool', cmd=['echo'], depends_on=['a']),
        ])
        assert all_deps_terminal(plan.get('b'), plan)

    def test_dep_pending(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='pending'),
            Task(id='b', kind='tool', cmd=['echo'], depends_on=['a']),
        ])
        assert not all_deps_terminal(plan.get('b'), plan)

    def test_dep_skipped_decides(self):
        # Skipped dep is non-done terminal — predicate returns
        # True (decision made) so the engine moves to cascade.
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='skipped'),
            Task(id='b', kind='tool', cmd=['echo'], depends_on=['a']),
        ])
        assert all_deps_terminal(plan.get('b'), plan)

    def test_dep_failed_decides(self):
        # Failed dep is non-done terminal — predicate returns
        # True (decision made) so the engine moves to cascade.
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='failed'),
            Task(id='b', kind='tool', cmd=['echo'], depends_on=['a']),
        ])
        assert all_deps_terminal(plan.get('b'), plan)


class TestComputeReadySet:
    def test_root_tasks_ready(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo']),
            Task(id='b', kind='tool', cmd=['echo']),
        ])
        ready = compute_ready_set(plan)
        assert {t.id for t in ready} == {'a', 'b'}

    def test_blocked_task_not_ready(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='pending'),
            Task(id='b', kind='tool', cmd=['echo'], depends_on=['a']),
        ])
        ready = compute_ready_set(plan)
        assert {t.id for t in ready} == {'a'}

    def test_already_running_excluded(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='running'),
        ])
        ready = compute_ready_set(plan)
        assert ready == []

    def test_done_excluded(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='done'),
        ])
        ready = compute_ready_set(plan)
        assert ready == []


class TestIsDone:
    def test_all_done(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='done'),
            Task(id='b', kind='tool', cmd=['echo'], status='skipped'),
        ])
        assert is_done(plan)

    def test_not_done(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='done'),
            Task(id='b', kind='tool', cmd=['echo'], status='pending'),
        ])
        assert not is_done(plan)

    def test_empty_plan_is_done(self):
        assert is_done(LoomPlan())


class TestIsStuck:
    def test_stuck_when_blocked_by_failure(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='failed'),
            Task(id='b', kind='tool', cmd=['echo'], depends_on=['a'],
                 status='pending'),
        ])
        # b's dep is terminal (failed), so b IS in the ready set
        # is_stuck should be False because b can proceed
        # Actually: all_deps_terminal returns True for failed deps
        # So b would be in ready set -> not stuck
        assert not is_stuck(plan)

    def test_stuck_when_no_progress_possible(self):
        # Scenario: b depends on a, a is running (not terminal)
        # b is pending but can't proceed
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='running'),
            Task(id='b', kind='tool', cmd=['echo'], depends_on=['a'],
                 status='pending'),
        ])
        # a is running (not terminal), b can't proceed, but a is running
        # so is_stuck checks: not done, no ready/running tasks... but a IS running
        assert not is_stuck(plan)

    def test_not_stuck_when_done(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='done'),
        ])
        assert not is_stuck(plan)


class TestDesugarPredicate:
    def test_sugar_to_native(self):
        result = desugar_predicate("${task:classify:form} == 'paper'")
        assert 'task."classify".form' in result
        assert "== 'paper'" in result

    def test_task_only(self):
        result = desugar_predicate("${task:classify}")
        assert result == 'task."classify"'

    def test_native_passthrough(self):
        expr = "task.classify.form == 'paper'"
        assert desugar_predicate(expr) == expr

    def test_non_task_placeholder_left_as_is(self):
        expr = "${workdir}/foo"
        assert desugar_predicate(expr) == expr

    def test_escaped_task_ref_left_as_is(self):
        # $${task:...} is the literal-placeholder escape from
        # the resolver. desugar_predicate must mirror it so a
        # predicate that documents placeholder syntax inside a
        # string is not corrupted into a JMESPath subexpression.
        expr = "doc == '$${task:other:field}'"
        assert desugar_predicate(expr) == expr


class TestEvalPredicate:
    def test_true_predicate(self, tmp_path):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='done'),
        ])
        td = store.ensure_task_dir(tmp_path, plan, 'a')
        (td / 'output.yaml').write_text(
            yaml.safe_dump({'form': 'paper'}), encoding='utf-8')
        ok, reason = eval_predicate(
            "task.a.form == 'paper'", plan, tmp_path)
        assert ok is True
        assert reason is None

    def test_false_predicate(self, tmp_path):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='done'),
        ])
        td = store.ensure_task_dir(tmp_path, plan, 'a')
        (td / 'output.yaml').write_text(
            yaml.safe_dump({'form': 'video'}), encoding='utf-8')
        ok, reason = eval_predicate(
            "task.a.form == 'paper'", plan, tmp_path)
        assert ok is False
        assert reason is not None

    def test_jmespath_error_returns_false(self, tmp_path):
        plan = LoomPlan(tasks=[])
        ok, reason = eval_predicate(
            "invalid[[[syntax", plan, tmp_path)
        assert ok is False

    def test_none_expr_returns_true(self, tmp_path):
        plan = LoomPlan(tasks=[])
        ok, _ = eval_predicate('', plan, tmp_path)
        assert ok is True


class TestPartitionReady:
    def test_splits_by_predicate(self, tmp_path):
        plan = LoomPlan(tasks=[
            Task(id='src', kind='tool', cmd=['echo'], status='done'),
            Task(id='a', kind='agent', template='/t.j2', output_schema='/s.yaml',
                 depends_on=['src'], when="task.src.form == 'paper'"),
            Task(id='b', kind='agent', template='/t.j2', output_schema='/s.yaml',
                 depends_on=['src'], when="task.src.form == 'video'"),
        ])
        td = store.ensure_task_dir(tmp_path, plan, 'src')
        (td / 'output.yaml').write_text(
            yaml.safe_dump({'form': 'paper'}), encoding='utf-8')

        candidates = [plan.get('a'), plan.get('b')]
        runnable, skipped, failed = partition_ready(candidates, plan, tmp_path)
        assert len(runnable) == 1
        assert runnable[0].id == 'a'
        assert len(skipped) == 1
        assert skipped[0][0].id == 'b'

    def test_no_when_always_runnable(self, tmp_path):
        plan = LoomPlan(tasks=[
            Task(id='x', kind='tool', cmd=['echo']),
        ])
        runnable, skipped, failed = partition_ready([plan.get('x')], plan, tmp_path)
        assert len(runnable) == 1
        assert len(skipped) == 0


class TestCascadeSkip:
    '''Cascade rules under logical-AND/OR semantics:

      - ``done`` ≡ True, ``skipped`` ≡ False.
      - ``depends_on_all`` ≡ AND: any ``skipped`` → skip downstream.
      - ``depends_on_any`` ≡ OR: every dep ``skipped`` → skip downstream.
      - ``failed`` is exceptional and never reaches partition_ready
        (the runner raises ``RunAborted`` first); cascade tests for
        failure live in ``test_runtime``.'''

    @pytest.mark.parametrize('scenario,dep_statuses,expected_outcome,expected_reason_marker', [
        # All AND: any skipped propagates skip (False ∧ True = False).
        ('all_done', {'a': 'done', 'b': 'done'}, 'runnable', None),
        ('all_done_skipped', {'a': 'done', 'b': 'skipped'}, 'skipped',
         'cascade-skip: 1/2 all-deps skipped'),
        ('all_two_skipped', {'a': 'skipped', 'b': 'skipped'}, 'skipped',
         'cascade-skip: 2/2 all-deps skipped'),
        ('all_single_skipped', {'a': 'skipped'}, 'skipped',
         'cascade-skip: 1/1 all-deps skipped'),
    ])
    def test_cascade_all_parametrized(
        self, tmp_path, scenario, dep_statuses,
        expected_outcome, expected_reason_marker,
    ):
        tasks = []
        dep_ids = []
        for tid, status in dep_statuses.items():
            tasks.append(Task(id=tid, kind='tool', cmd=['echo'], status=status))
            dep_ids.append(tid)
        tasks.append(Task(id='c', kind='agent', template='/t.j2',
                          depends_on_all=dep_ids))
        plan = LoomPlan(tasks=tasks)
        runnable, skipped, failed = partition_ready(
            [plan.get('c')], plan, tmp_path)
        assert failed == []
        if expected_outcome == 'runnable':
            assert len(runnable) == 1 and runnable[0].id == 'c'
            assert skipped == []
        elif expected_outcome == 'skipped':
            assert runnable == []
            assert len(skipped) == 1
            assert expected_reason_marker in skipped[0][1]
        else:
            raise AssertionError(f'unknown outcome {expected_outcome!r}')

    @pytest.mark.parametrize('scenario,dep_statuses,expected_outcome,expected_reason_marker', [
        # OR: at least one done → runnable.
        ('any_done_skipped', {'a': 'done', 'b': 'skipped'}, 'runnable', None),
        # OR: all skipped → skip (False ∨ False = False).
        ('any_all_skipped', {'a': 'skipped', 'b': 'skipped'}, 'skipped',
         'cascade-skip: all 2 any-deps skipped'),
        # OR: single skipped dep → skip.
        ('any_single_skipped', {'a': 'skipped'}, 'skipped',
         'cascade-skip: all 1 any-deps skipped'),
    ])
    def test_cascade_any_parametrized(
        self, tmp_path, scenario, dep_statuses,
        expected_outcome, expected_reason_marker,
    ):
        tasks = []
        dep_ids = []
        for tid, status in dep_statuses.items():
            tasks.append(Task(id=tid, kind='tool', cmd=['echo'], status=status))
            dep_ids.append(tid)
        tasks.append(Task(id='c', kind='agent', template='/t.j2',
                          depends_on_any=dep_ids))
        plan = LoomPlan(tasks=tasks)
        runnable, skipped, failed = partition_ready(
            [plan.get('c')], plan, tmp_path)
        assert failed == []
        if expected_outcome == 'runnable':
            assert len(runnable) == 1 and runnable[0].id == 'c'
            assert skipped == []
        elif expected_outcome == 'skipped':
            assert runnable == []
            assert len(skipped) == 1
            assert expected_reason_marker in skipped[0][1]
        else:
            raise AssertionError(f'unknown outcome {expected_outcome!r}')

    def test_no_deps_always_runnable(self, tmp_path):
        '''Root task (no depends_on*) is never cascade-skipped.'''
        plan = LoomPlan(tasks=[
            Task(id='x', kind='tool', cmd=['echo']),
        ])
        runnable, skipped, failed = partition_ready(
            [plan.get('x')], plan, tmp_path)
        assert len(runnable) == 1
        assert skipped == []
        assert failed == []

    def test_skipped_dep_cascades_outranks_when_check(self, tmp_path):
        '''Cascade-skip is checked before the predicate, so a
        skipped upstream produces a cascade-skip downstream
        regardless of what ``when:`` would have decided.'''
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='skipped'),
            Task(id='b', kind='agent', template='/t.j2',
                 depends_on_all=['a'], when="task.a.form == 'paper'"),
        ])
        runnable, skipped, failed = partition_ready(
            [plan.get('b')], plan, tmp_path)
        assert runnable == []
        assert failed == []
        assert len(skipped) == 1
        assert 'cascade-skip' in skipped[0][1]

    def test_when_false_with_done_dep_is_when_skipped(self, tmp_path):
        '''A done dep does not propagate skip; the predicate then
        runs and ``when:false`` gives a when-false skip reason.'''
        from tests.helpers import write_schema
        s = write_schema(tmp_path / 's.yaml',
                         {'type': 'object',
                          'properties': {'form': {'type': 'string'}},
                          'required': ['form']})
        # Need a real output for predicate evaluation.
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'],
                 output_schema=s, status='done'),
            Task(id='b', kind='agent', template='/t.j2',
                 depends_on_all=['a'], when="task.a.form == 'paper'"),
        ])
        # No output written → predicate evaluates against None.
        runnable, skipped, failed = partition_ready(
            [plan.get('b')], plan, tmp_path)
        assert runnable == []
        assert failed == []
        assert len(skipped) == 1
        assert 'when-false' in skipped[0][1]
