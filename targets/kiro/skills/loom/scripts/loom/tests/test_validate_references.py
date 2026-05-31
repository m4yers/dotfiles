'''Tests for reference resolution, JMESPath tracing, and type compatibility.'''
import pytest

from loom.engine.models import Task, LoomPlan
from loom.validate.references import validate_references
from loom.validate.schemas import SchemaCache
from loom.errors import ReferenceError as LoomReferenceError, TypeMismatchError
from tests.helpers import write_schema


class TestReferenceResolution:
    def test_unknown_task_ref_in_cmd(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo', '${task:nonexistent:val}'],
                 output_schema=str(s)),
        ])
        cache = SchemaCache()
        cache.load(s)
        with pytest.raises(LoomReferenceError, match='unknown task id'):
            validate_references(plan, cache)

    def test_valid_ref_passes(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'val': {'type': 'integer'}},
        })
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema=str(s)),
            Task(id='b', kind='tool',
                 cmd=['echo', '${task:a:val}'],
                 output_schema=str(s), depends_on=['a']),
        ])
        cache = SchemaCache()
        cache.load(s)
        validate_references(plan, cache)  # no exception

    def test_workdir_placeholder_not_flagged(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo', '${workdir}'],
                 output_schema=str(s)),
        ])
        cache = SchemaCache()
        cache.load(s)
        validate_references(plan, cache)  # no exception

    def test_unknown_ref_in_vars(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = LoomPlan(tasks=[
            Task(id='a', kind='agent', template='/t.j2',
                 output_schema=str(s),
                 vars={'x': '${task:ghost:field}'}),
        ])
        cache = SchemaCache()
        cache.load(s)
        with pytest.raises(LoomReferenceError, match='unknown task id'):
            validate_references(plan, cache)

    def test_escaped_ref_in_vars_not_flagged(self, tmp_path):
        # $${task:...} is the escape syntax for a literal
        # ${task:...} in the rendered output. The validator
        # must mirror the resolver and skip escaped forms,
        # otherwise user-supplied vars (e.g. documentation
        # text describing loom's own placeholder grammar)
        # cannot contain literal placeholder examples.
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = LoomPlan(tasks=[
            Task(id='a', kind='agent', template='/t.j2',
                 output_schema=str(s),
                 vars={'doc': 'see $${task:other:field} for syntax'}),
        ])
        cache = SchemaCache()
        cache.load(s)
        validate_references(plan, cache)  # no exception

    def test_escaped_ref_in_cmd_not_flagged(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool',
                 cmd=['echo', '$${task:ghost:value}'],
                 output_schema=str(s)),
        ])
        cache = SchemaCache()
        cache.load(s)
        validate_references(plan, cache)  # no exception


class TestJMESPathTracing:
    def test_field_in_schema_passes(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'name': {'type': 'string'}},
        })
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema=str(s)),
            Task(id='b', kind='tool', cmd=['echo', '${task:a:name}'],
                 output_schema=str(s), depends_on=['a']),
        ])
        cache = SchemaCache()
        cache.load(s)
        validate_references(plan, cache)

    def test_field_not_in_schema_raises(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'name': {'type': 'string'}},
        })
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema=str(s)),
            Task(id='b', kind='tool', cmd=['echo', '${task:a:nonexistent}'],
                 output_schema=str(s), depends_on=['a']),
        ])
        cache = SchemaCache()
        cache.load(s)
        with pytest.raises(LoomReferenceError, match='not declared'):
            validate_references(plan, cache)

    def test_nested_field_traces(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {
                'quintet': {
                    'type': 'object',
                    'properties': {'form': {'type': 'string'}},
                },
            },
        })
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema=str(s)),
            Task(id='b', kind='tool', cmd=['echo', '${task:a:quintet.form}'],
                 output_schema=str(s), depends_on=['a']),
        ])
        cache = SchemaCache()
        cache.load(s)
        validate_references(plan, cache)

    def test_array_index_traces(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {
                'items': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {'title': {'type': 'string'}},
                    },
                },
            },
        })
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema=str(s)),
            Task(id='b', kind='tool', cmd=['echo', '${task:a:items[0].title}'],
                 output_schema=str(s), depends_on=['a']),
        ])
        cache = SchemaCache()
        cache.load(s)
        validate_references(plan, cache)


class TestTypeCompatibility:
    def test_string_vs_number_raises(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'count': {'type': 'number'}},
        })
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema=str(s)),
            Task(id='b', kind='tool', cmd=['echo'], output_schema=str(s),
                 depends_on=['a'],
                 when="${task:a:count} == 'hello'"),
        ])
        cache = SchemaCache()
        cache.load(s)
        with pytest.raises(TypeMismatchError):
            validate_references(plan, cache)

    def test_number_vs_number_passes(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'count': {'type': 'number'}},
        })
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema=str(s)),
            Task(id='b', kind='tool', cmd=['echo'], output_schema=str(s),
                 depends_on=['a'],
                 when="${task:a:count} > `5`"),
        ])
        cache = SchemaCache()
        cache.load(s)
        validate_references(plan, cache)

    def test_string_vs_string_passes(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {
            'type': 'object',
            'properties': {'name': {'type': 'string'}},
        })
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema=str(s)),
            Task(id='b', kind='tool', cmd=['echo'], output_schema=str(s),
                 depends_on=['a'],
                 when="${task:a:name} == 'foo'"),
        ])
        cache = SchemaCache()
        cache.load(s)
        validate_references(plan, cache)
