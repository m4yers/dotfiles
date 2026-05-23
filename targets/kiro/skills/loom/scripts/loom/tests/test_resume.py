'''Tests for loom.resume: re-attach, missing files.'''
import pytest

import loom
from loom.errors import SchemaError
from loom.plan import tool, make_plan
from tests.helpers import write_schema


class TestResumeSuccess:
    def test_reattach_to_existing(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = make_plan(tool('x', cmd=['echo'], output_schema=s))
        wd = tmp_path / 'wd'
        loom.init(workdir=wd, plan=plan)

        rt = loom.resume(wd)
        assert rt.workdir == wd.resolve()
        p = rt.plan()
        assert p.ids() == {'x'}

    def test_resume_preserves_status(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'val': {'type': 'integer'}},
            'required': ['val'],
        })
        plan = make_plan(
            tool('t1', cmd=['python', '-c', 'import json; print(json.dumps({"val":1}))'],
                 output_schema=s),
        )
        wd = tmp_path / 'wd'
        rt = loom.init(workdir=wd, plan=plan)
        rt.next()  # runs tool to done
        assert rt.is_done()

        rt2 = loom.resume(wd)
        assert rt2.is_done()
        assert rt2.plan().get('t1').status == 'done'


class TestResumeMissing:
    def test_missing_workdir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match='workdir'):
            loom.resume(tmp_path / 'nonexistent')

    def test_missing_plan_yaml_raises(self, tmp_path):
        wd = tmp_path / 'wd'
        wd.mkdir()
        with pytest.raises(FileNotFoundError, match='plan.yaml'):
            loom.resume(wd)

    def test_deleted_schema_raises(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = make_plan(tool('x', cmd=['echo'], output_schema=s))
        wd = tmp_path / 'wd'
        loom.init(workdir=wd, plan=plan)

        # Delete the schema file
        s.unlink()
        with pytest.raises(SchemaError, match='not found'):
            loom.resume(wd)
