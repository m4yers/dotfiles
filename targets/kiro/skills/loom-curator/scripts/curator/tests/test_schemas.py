'''Validate that all pre-authored schemas are valid JSON Schemas.'''
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
import jsonschema

SCHEMAS_ROOT = Path(__file__).resolve().parents[3] / 'schemas'


def _all_schema_files():
    '''Yield (relative_name, path) for every schema yaml.'''
    for subdir in ('pipeline', 'extractors'):
        d = SCHEMAS_ROOT / subdir
        if not d.exists():
            continue
        for f in sorted(d.glob('*.yaml')):
            yield f'{subdir}/{f.name}', f


ALL_SCHEMAS = list(_all_schema_files())


@pytest.mark.parametrize('name,path', ALL_SCHEMAS, ids=[s[0] for s in ALL_SCHEMAS])
def test_schema_is_valid(name, path):
    doc = yaml.safe_load(path.read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator.check_schema(doc)


# ---- Representative valid/invalid samples for schemas with required fields ----

VALID_SAMPLES = {
    'pipeline/fetch.yaml': {'path': '/tmp/source.txt'},
    'pipeline/convert.yaml': {'converted_path': '/tmp/out.md'},
    'pipeline/gate.yaml': {'proceed': True},
    'pipeline/judge-verdict.yaml': {'verdict': 'ACCEPT', 'reasons': []},
    'extractors/classify.yaml': {
        'quintet': {
            'media': 'paper', 'form': 'research',
            'register': 'non_fiction', 'discipline': 'cs',
            'audience': 'academic',
        }
    },
}

INVALID_SAMPLES = {
    'pipeline/fetch.yaml': {'not_path': 123},
    'pipeline/convert.yaml': {'converted_path': 123},
    'pipeline/gate.yaml': {'proceed': 'yes'},
    'pipeline/judge-verdict.yaml': {'verdict': 'INVALID_VALUE'},
    'extractors/classify.yaml': {
        'quintet': {'media': 'paper'}  # missing required fields
    },
}


@pytest.mark.parametrize('name', list(VALID_SAMPLES.keys()))
def test_valid_sample_passes(name):
    path = SCHEMAS_ROOT / name
    schema = yaml.safe_load(path.read_text(encoding='utf-8'))
    jsonschema.validate(VALID_SAMPLES[name], schema)


@pytest.mark.parametrize('name', list(INVALID_SAMPLES.keys()))
def test_invalid_sample_fails(name):
    path = SCHEMAS_ROOT / name
    schema = yaml.safe_load(path.read_text(encoding='utf-8'))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(INVALID_SAMPLES[name], schema)
