'''Tests for tool task subprocess execution, env vars, schema-on-exit.'''
import json
import os
import pytest

import loom
from loom.errors import RunFailed, OutputSchemaError
from loom.plan import tool, make_plan
from tests.helpers import write_schema


class TestToolSuccess:
    def test_stdout_to_output_yaml(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'val': {'type': 'integer'}},
            'required': ['val'],
        })
        plan = make_plan(
            tool('t1', cmd=['python', '-c', 'import json; print(json.dumps({"val": 42}))'],
                 output_schema=s),
        )
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        rt.next()
        assert rt.task_output('t1') == {'val': 42}
        assert rt.plan().get('t1').status == 'done'

    def test_env_vars_set(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        # Script that outputs env vars as JSON
        script = (
            'import json, os; print(json.dumps({'
            '"workdir": os.environ["WORKDIR"],'
            '"task_id": os.environ["TASK_ID"],'
            '"output_path": os.environ["OUTPUT_PATH"],'
            '"task_workdir": os.environ["TASK_WORKDIR"]'
            '}))'
        )
        plan = make_plan(
            tool('t1', cmd=['python', '-c', script], output_schema=s),
        )
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        rt.next()
        out = rt.task_output('t1')
        assert out['task_id'] == 't1'
        assert 'workdir' in out['workdir'].lower() or os.sep in out['workdir']
        assert out['output_path'].endswith('output.yaml')
        assert 't1' in out['task_workdir']


class TestToolFailure:
    def test_nonzero_exit_raises_run_failed(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = make_plan(
            tool('t1', cmd=['python', '-c', 'import sys; sys.exit(1)'],
                 output_schema=s),
        )
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        with pytest.raises(RunFailed) as exc_info:
            rt.next()
        assert exc_info.value.task_id == 't1'
        assert rt.plan().get('t1').status == 'failed'

    def test_stderr_captured(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = make_plan(
            tool('t1', cmd=['python', '-c',
                            'import sys; sys.stderr.write("oops\\n"); sys.exit(1)'],
                 output_schema=s),
        )
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        with pytest.raises(RunFailed):
            rt.next()
        td = rt.task_dir('t1')
        assert 'oops' in (td / 'stderr.log').read_text()


class TestToolSchemaValidation:
    def test_exit_zero_but_schema_mismatch(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'val': {'type': 'integer'}},
            'required': ['val'],
        })
        # Outputs wrong shape
        plan = make_plan(
            tool('t1', cmd=['python', '-c', 'import json; print(json.dumps({"wrong": "key"}))'],
                 output_schema=s),
        )
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        with pytest.raises(OutputSchemaError):
            rt.next()
        assert rt.plan().get('t1').status == 'failed'
        td = rt.task_dir('t1')
        assert (td / 'schema-error.log').exists()


class TestToolPlaceholderResolution:
    def test_cmd_placeholders_resolved(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        # Use ${workdir} in cmd — script echoes it back
        plan = make_plan(
            tool('t1', cmd=['python', '-c',
                            'import json,sys; print(json.dumps({"wd": sys.argv[1]}))'],
                 output_schema=s),
        )
        # Manually add a placeholder arg
        plan.tasks[0].cmd.append('${workdir}')
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        rt.next()
        out = rt.task_output('t1')
        assert str((tmp_path / 'wd').resolve()) in out['wd']

    def test_escape_in_cmd(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        # $${VAR} should become literal ${VAR}
        plan = make_plan(
            tool('t1', cmd=['python', '-c',
                            'import json,sys; print(json.dumps({"arg": sys.argv[1]}))'],
                 output_schema=s),
        )
        plan.tasks[0].cmd.append('$${NOT_RESOLVED}')
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        rt.next()
        out = rt.task_output('t1')
        assert out['arg'] == '${NOT_RESOLVED}'
