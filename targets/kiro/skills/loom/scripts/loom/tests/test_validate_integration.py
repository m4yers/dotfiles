'''Tests for validate_plan end-to-end pipeline.'''
import pytest

from loom.engine.models import Task, LoomPlan
from loom.validate import validate_plan, SchemaCache
from loom.errors import DAGError, LoomPlanError, SchemaError
from tests.helpers import write_schema, write_template


class TestValidatePlanPipeline:
    def test_valid_plan_passes(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'val': {'type': 'integer'}},
            'required': ['val'],
        })
        t = write_template(tmp_path / 't.j2', '{{ task.id }}')
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema=str(s)),
            Task(id='b', kind='agent', template=str(t), output_schema=str(s),
                 depends_on=['a']),
        ])
        schemas = validate_plan(plan)
        assert isinstance(schemas, SchemaCache)
        assert s in schemas

    def test_dag_error_propagates(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema=str(s),
                 depends_on=['a']),
        ])
        with pytest.raises(DAGError):
            validate_plan(plan)

    def test_kind_error_propagates(self, tmp_path):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool'),  # missing cmd and output_schema
        ])
        with pytest.raises(LoomPlanError):
            validate_plan(plan)

    def test_schema_error_propagates(self, tmp_path):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'],
                 output_schema=str(tmp_path / 'nonexistent.yaml')),
        ])
        with pytest.raises(SchemaError, match='not found'):
            validate_plan(plan)

    def test_existing_cache_reused(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema=str(s)),
        ])
        cache = SchemaCache()
        cache.load(s)
        result = validate_plan(plan, cache)
        assert result is cache

    def test_human_without_schema_passes(self, tmp_path):
        '''Human tasks with no output_schema should pass validation.'''
        plan = LoomPlan(tasks=[
            Task(id='h', kind='human'),
        ])
        validate_plan(plan)
