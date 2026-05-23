'''Tests for placeholder substitution, type preservation, $$ escape.'''
import pytest
import yaml

from loom.engine.models import Task, LoomPlan
from loom.engine.resolve import resolve_value
from loom.engine import store


class TestWorkdirPlaceholder:
    def test_resolves_to_string(self, tmp_path):
        plan = LoomPlan(tasks=[Task(id='x', kind='tool', cmd=['echo'])])
        result = resolve_value('${workdir}', tmp_path, plan)
        assert result == str(tmp_path)

    def test_embedded(self, tmp_path):
        plan = LoomPlan(tasks=[])
        result = resolve_value('path=${workdir}/file', tmp_path, plan)
        assert result == f'path={tmp_path}/file'


class TestTaskWorkdirPlaceholder:
    def test_resolves_for_known_task(self, tmp_path):
        plan = LoomPlan(tasks=[Task(id='x', kind='tool', cmd=['echo'])])
        result = resolve_value('${task_workdir}', tmp_path, plan, task_id='x')
        expected = str(store.task_dir(tmp_path, plan, 'x'))
        assert result == expected

    def test_empty_when_no_task_id(self, tmp_path):
        plan = LoomPlan(tasks=[])
        result = resolve_value('${task_workdir}', tmp_path, plan)
        assert result == ''


class TestTaskRefPlaceholder:
    def test_full_output_native_type(self, tmp_path):
        plan = LoomPlan(tasks=[Task(id='a', kind='tool', cmd=['echo'])])
        td = store.ensure_task_dir(tmp_path, plan, 'a')
        (td / 'output.yaml').write_text(
            yaml.safe_dump({'val': 42}), encoding='utf-8')
        result = resolve_value('${task:a}', tmp_path, plan)
        assert result == {'val': 42}
        assert isinstance(result, dict)

    def test_jmespath_query(self, tmp_path):
        plan = LoomPlan(tasks=[Task(id='a', kind='tool', cmd=['echo'])])
        td = store.ensure_task_dir(tmp_path, plan, 'a')
        (td / 'output.yaml').write_text(
            yaml.safe_dump({'val': 42}), encoding='utf-8')
        result = resolve_value('${task:a:val}', tmp_path, plan)
        assert result == 42

    def test_missing_output_returns_none(self, tmp_path):
        plan = LoomPlan(tasks=[Task(id='a', kind='tool', cmd=['echo'])])
        result = resolve_value('${task:a}', tmp_path, plan)
        assert result is None


class TestTypePreservation:
    def test_whole_string_preserves_dict(self, tmp_path):
        plan = LoomPlan(tasks=[Task(id='a', kind='tool', cmd=['echo'])])
        td = store.ensure_task_dir(tmp_path, plan, 'a')
        (td / 'output.yaml').write_text(
            yaml.safe_dump({'nested': {'k': 'v'}}), encoding='utf-8')
        result = resolve_value('${task:a:nested}', tmp_path, plan)
        assert result == {'k': 'v'}

    def test_whole_string_preserves_int(self, tmp_path):
        plan = LoomPlan(tasks=[Task(id='a', kind='tool', cmd=['echo'])])
        td = store.ensure_task_dir(tmp_path, plan, 'a')
        (td / 'output.yaml').write_text(
            yaml.safe_dump({'count': 7}), encoding='utf-8')
        result = resolve_value('${task:a:count}', tmp_path, plan)
        assert result == 7
        assert isinstance(result, int)

    def test_embedded_coerces_to_string(self, tmp_path):
        plan = LoomPlan(tasks=[Task(id='a', kind='tool', cmd=['echo'])])
        td = store.ensure_task_dir(tmp_path, plan, 'a')
        (td / 'output.yaml').write_text(
            yaml.safe_dump({'count': 7}), encoding='utf-8')
        result = resolve_value('count=${task:a:count}!', tmp_path, plan)
        assert result == 'count=7!'
        assert isinstance(result, str)


class TestEscaping:
    def test_double_dollar_produces_literal(self, tmp_path):
        plan = LoomPlan(tasks=[])
        result = resolve_value('$${NOT_RESOLVED}', tmp_path, plan)
        assert result == '${NOT_RESOLVED}'

    def test_escape_mixed_with_real(self, tmp_path):
        plan = LoomPlan(tasks=[])
        result = resolve_value('$${LIT} ${workdir}', tmp_path, plan)
        assert '${LIT}' in result
        assert str(tmp_path) in result


class TestGlobalPlaceholder:
    def test_global_resolves(self, tmp_path):
        plan = LoomPlan(tasks=[])
        result = resolve_value('${global}', tmp_path, plan)
        assert result == str(tmp_path / 'global')

    def test_global_with_rel(self, tmp_path):
        plan = LoomPlan(tasks=[])
        result = resolve_value('${global:docs/readme.md}', tmp_path, plan)
        assert result == str(tmp_path / 'global' / 'docs/readme.md')


class TestTaskPathPlaceholder:
    def test_resolves_to_output_path(self, tmp_path):
        plan = LoomPlan(tasks=[Task(id='a', kind='tool', cmd=['echo'])])
        result = resolve_value('${task_path:a}', tmp_path, plan)
        expected = str(store.task_output_path(tmp_path, plan, 'a'))
        assert result == expected


class TestRecursion:
    def test_list_resolved(self, tmp_path):
        plan = LoomPlan(tasks=[])
        result = resolve_value(['${workdir}', 'literal'], tmp_path, plan)
        assert result == [str(tmp_path), 'literal']

    def test_dict_resolved(self, tmp_path):
        plan = LoomPlan(tasks=[])
        result = resolve_value({'k': '${workdir}'}, tmp_path, plan)
        assert result == {'k': str(tmp_path)}

    def test_non_string_passthrough(self, tmp_path):
        plan = LoomPlan(tasks=[])
        assert resolve_value(42, tmp_path, plan) == 42
        assert resolve_value(None, tmp_path, plan) is None
