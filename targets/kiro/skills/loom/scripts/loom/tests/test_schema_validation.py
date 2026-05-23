'''Tests for complete() schema check; human default schema.'''
import pytest

import loom
from loom.errors import OutputSchemaError
from loom.plan import tool, agent, human, make_plan
from tests.helpers import write_schema, write_template


class TestCompleteSchemaValidation:
    def test_conforming_output_passes(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'name': {'type': 'string'}},
            'required': ['name'],
        })
        tpl = write_template(tmp_path / 't.j2', 'hi {{ task.id }}')
        plan = make_plan(agent('a1', template=tpl, output_schema=s))
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        spec = rt.next()
        rt.commit_running(['a1'])
        rt.complete('a1', output={'name': 'test'})
        assert rt.plan().get('a1').status == 'done'

    def test_non_conforming_output_fails(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'name': {'type': 'string'}},
            'required': ['name'],
        })
        tpl = write_template(tmp_path / 't.j2', 'hi {{ task.id }}')
        plan = make_plan(agent('a1', template=tpl, output_schema=s))
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        rt.next()
        rt.commit_running(['a1'])
        with pytest.raises(OutputSchemaError) as exc_info:
            rt.complete('a1', output={'wrong': 123})
        assert exc_info.value.task_id == 'a1'
        assert rt.plan().get('a1').status == 'failed'

    def test_schema_error_log_written(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'val': {'type': 'integer'}},
            'required': ['val'],
        })
        tpl = write_template(tmp_path / 't.j2', '{{ task.id }}')
        plan = make_plan(agent('a1', template=tpl, output_schema=s))
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        rt.next()
        rt.commit_running(['a1'])
        with pytest.raises(OutputSchemaError):
            rt.complete('a1', output={'val': 'not_int'})
        td = rt.task_dir('a1')
        assert (td / 'schema-error.log').exists()


class TestHumanDefaultSchema:
    def test_human_no_schema_accepts_any_object(self, tmp_path):
        '''Human tasks without output_schema use default {type: object}.'''
        plan = make_plan(human('h1'))
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        spec = rt.next()
        assert spec is not None
        rt.commit_running(['h1'])
        # Any object should pass
        rt.complete('h1', output={'anything': 'goes', 'nested': {'ok': True}})
        assert rt.plan().get('h1').status == 'done'

    def test_human_with_schema_validates(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'proceed': {'type': 'boolean'}},
            'required': ['proceed'],
        })
        plan = make_plan(human('h1', output_schema=s))
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        rt.next()
        rt.commit_running(['h1'])
        with pytest.raises(OutputSchemaError):
            rt.complete('h1', output={'wrong': 'field'})
