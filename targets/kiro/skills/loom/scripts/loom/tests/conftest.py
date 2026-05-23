'''Shared fixtures for loom test suite.'''
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def tmp_workdir(tmp_path):
    '''Absolute Path to a fresh workdir.'''
    wd = tmp_path / 'workdir'
    return wd


@pytest.fixture
def schema_file_factory(tmp_path):
    '''Callable that writes a YAML schema file and returns its absolute path.'''
    counter = [0]

    def _make(schema_dict: dict, name: str | None = None) -> Path:
        counter[0] += 1
        fname = name or f'schema_{counter[0]}.yaml'
        p = tmp_path / 'schemas' / fname
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(schema_dict, sort_keys=False), encoding='utf-8')
        return p

    return _make


@pytest.fixture
def simple_int_schema(schema_file_factory):
    '''Schema: {type: object, properties: {val: {type: integer}}, required: [val]}'''
    return schema_file_factory({
        'type': 'object',
        'properties': {'val': {'type': 'integer'}},
        'required': ['val'],
    })


@pytest.fixture
def simple_str_schema(schema_file_factory):
    '''Schema: {type: object, properties: {name: {type: string}}, required: [name]}'''
    return schema_file_factory({
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    })


@pytest.fixture
def quintet_schema(schema_file_factory):
    '''Schema with quintet.form and quintet.media as strings.'''
    return schema_file_factory({
        'type': 'object',
        'properties': {
            'quintet': {
                'type': 'object',
                'properties': {
                    'form': {'type': 'string'},
                    'media': {'type': 'string'},
                },
                'required': ['form', 'media'],
            },
        },
        'required': ['quintet'],
    })
