'''Tests for predicate eval, desugaring, skip_reason, truthiness.'''
import pytest
import yaml

import loom
from loom.engine.algorithm import desugar_predicate, eval_predicate
from loom.engine.models import Task, LoomPlan
from loom.engine import store
from loom.plan import tool, agent, make_plan
from tests.helpers import write_schema, write_template


class TestDesugaring:
    @pytest.mark.parametrize('input_expr,expected', [
        ("${task:classify:form} == 'paper'", 'task."classify".form == \'paper\''),
        ("${task:x}", 'task."x"'),
        ("${task:a-b:nested.field}", 'task."a-b".nested.field'),
        ("task.x.val == 'foo'", "task.x.val == 'foo'"),  # native passthrough
    ])
    def test_desugar(self, input_expr, expected):
        assert desugar_predicate(input_expr) == expected

    def test_non_task_placeholder_unchanged(self):
        assert desugar_predicate("${workdir}/foo") == "${workdir}/foo"

    def test_multiple_refs(self):
        expr = "${task:a:x} == 'y' && ${task:b:z} > `0`"
        result = desugar_predicate(expr)
        assert 'task."a".x' in result
        assert 'task."b".z' in result


class TestTruthiness:
    '''Truthiness table from design: JMESPath result -> bool.'''

    @pytest.mark.parametrize('output,expr,expected', [
        ({'flag': True}, 'task.x.flag', True),
        ({'flag': False}, 'task.x.flag', False),
        ({'val': 0}, 'task.x.val', False),
        ({'val': 1}, 'task.x.val', True),
        ({'s': ''}, 'task.x.s', False),
        ({'s': 'hello'}, 'task.x.s', True),
        ({'arr': []}, 'task.x.arr', False),
        ({'arr': [1]}, 'task.x.arr', True),
        ({'obj': {}}, 'task.x.obj', False),
        ({'obj': {'k': 'v'}}, 'task.x.obj', True),
        ({}, 'task.x.missing', False),  # null -> false
    ])
    def test_truthiness(self, tmp_path, output, expr, expected):
        plan = LoomPlan(tasks=[
            Task(id='x', kind='tool', cmd=['echo'], status='done'),
        ])
        td = store.ensure_task_dir(tmp_path, plan, 'x')
        (td / 'output.yaml').write_text(
            yaml.safe_dump(output), encoding='utf-8')
        ok, _ = eval_predicate(expr, plan, tmp_path)
        assert ok is expected


class TestMultiTaskPredicates:
    def test_cross_task_and(self, tmp_path):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='done'),
            Task(id='b', kind='tool', cmd=['echo'], status='done'),
        ])
        td_a = store.ensure_task_dir(tmp_path, plan, 'a')
        (td_a / 'output.yaml').write_text(
            yaml.safe_dump({'score': 8}), encoding='utf-8')
        td_b = store.ensure_task_dir(tmp_path, plan, 'b')
        (td_b / 'output.yaml').write_text(
            yaml.safe_dump({'confidence': 0.95}), encoding='utf-8')

        ok, _ = eval_predicate(
            "task.a.score > `7` && task.b.confidence > `0.9`", plan, tmp_path)
        assert ok is True

    def test_cross_task_one_false(self, tmp_path):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], status='done'),
            Task(id='b', kind='tool', cmd=['echo'], status='done'),
        ])
        td_a = store.ensure_task_dir(tmp_path, plan, 'a')
        (td_a / 'output.yaml').write_text(
            yaml.safe_dump({'score': 3}), encoding='utf-8')
        td_b = store.ensure_task_dir(tmp_path, plan, 'b')
        (td_b / 'output.yaml').write_text(
            yaml.safe_dump({'confidence': 0.95}), encoding='utf-8')

        ok, _ = eval_predicate(
            "task.a.score > `7` && task.b.confidence > `0.9`", plan, tmp_path)
        assert ok is False


class TestSkipReason:
    def test_skip_reason_recorded(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'form': {'type': 'string'}},
            'required': ['form'],
        })
        plan = make_plan(
            tool('src', cmd=['python', '-c', 'import json; print(json.dumps({"form":"video"}))'],
                 output_schema=s),
            tool('branch', cmd=['echo'], output_schema=s,
                 depends_on=['src'], when="task.src.form == 'paper'"),
        )
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        # next() runs src inline, then evaluates branch predicate
        try:
            rt.next()
        except Exception:
            pass
        p = rt.plan()
        branch = p.get('branch')
        assert branch.status == 'skipped'
        assert '_skip_reason' in branch.metadata


class TestSugarNativeEquivalence:
    def test_same_result(self, tmp_path):
        plan = LoomPlan(tasks=[
            Task(id='x', kind='tool', cmd=['echo'], status='done'),
        ])
        td = store.ensure_task_dir(tmp_path, plan, 'x')
        (td / 'output.yaml').write_text(
            yaml.safe_dump({'form': 'paper'}), encoding='utf-8')

        ok_sugar, _ = eval_predicate(
            "${task:x:form} == 'paper'", plan, tmp_path)
        ok_native, _ = eval_predicate(
            'task."x".form == \'paper\'', plan, tmp_path)
        assert ok_sugar == ok_native == True
