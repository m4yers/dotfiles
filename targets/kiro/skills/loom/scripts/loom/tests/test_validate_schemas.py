'''Tests for SchemaCache: load, meta-validate, cache identity.'''
import pytest
import yaml

from loom.validate.schemas import SchemaCache
from loom.errors import SchemaError


class TestSchemaLoad:
    def test_valid_schema_loads(self, schema_file_factory):
        path = schema_file_factory({'type': 'object', 'properties': {'x': {'type': 'string'}}})
        cache = SchemaCache()
        schema = cache.load(path)
        assert schema['type'] == 'object'
        assert 'x' in schema['properties']

    def test_missing_file_raises(self, tmp_path):
        cache = SchemaCache()
        with pytest.raises(SchemaError, match='not found'):
            cache.load(tmp_path / 'nonexistent.yaml')

    def test_invalid_yaml_raises(self, tmp_path):
        bad = tmp_path / 'bad.yaml'
        bad.write_text(': : : not valid yaml [[[', encoding='utf-8')
        cache = SchemaCache()
        with pytest.raises(SchemaError, match='not valid YAML'):
            cache.load(bad)

    def test_non_dict_raises(self, tmp_path):
        bad = tmp_path / 'list.yaml'
        bad.write_text('- item1\n- item2\n', encoding='utf-8')
        cache = SchemaCache()
        with pytest.raises(SchemaError, match='mapping'):
            cache.load(bad)

    def test_invalid_json_schema_raises(self, tmp_path):
        bad = tmp_path / 'bad_schema.yaml'
        bad.write_text(yaml.safe_dump({'type': 'not-a-real-type'}), encoding='utf-8')
        cache = SchemaCache()
        with pytest.raises(SchemaError, match='not a valid JSON Schema'):
            cache.load(bad)


class TestCacheIdentity:
    def test_same_path_returns_same_object(self, schema_file_factory):
        path = schema_file_factory({'type': 'object'})
        cache = SchemaCache()
        s1 = cache.load(path)
        s2 = cache.load(path)
        assert s1 is s2

    def test_different_paths_return_different_objects(self, schema_file_factory):
        p1 = schema_file_factory({'type': 'object'}, name='a.yaml')
        p2 = schema_file_factory({'type': 'object', 'properties': {}}, name='b.yaml')
        cache = SchemaCache()
        s1 = cache.load(p1)
        s2 = cache.load(p2)
        assert s1 is not s2

    def test_contains_check(self, schema_file_factory):
        path = schema_file_factory({'type': 'object'})
        cache = SchemaCache()
        assert path not in cache
        cache.load(path)
        assert path in cache
