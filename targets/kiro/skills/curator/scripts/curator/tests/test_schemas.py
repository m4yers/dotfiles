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
    'pipeline/source-fetch.yaml': {'path': '/tmp/source.txt'},
    'pipeline/source-convert.yaml': {'converted_path': '/tmp/out.md'},
    'pipeline/vault-gate.yaml': {'proceed': True},
    'pipeline/judge-verdict.yaml': {
        'verdict': 'ACCEPT',
        'reasoning': 'all rubric dimensions pass per evidence',
        '_rubric': {'overall': 'whole-output verdict per rubric'},
        'item_verdicts': [{
            'target': None,
            'verdict': 'ACCEPT',
            'scores': {'overall': 'PASS'},
            'rationale': 'evidence-cited rationale',
        }],
        'issues': [],
    },
    'extractors/classify.yaml': {
        'quintet': {
            'media': 'paper', 'form': 'research',
            'register': 'non_fiction', 'discipline': 'cs',
            'audience': 'academic',
        }
    },
    'extractors/recipes.yaml': {
        'recipes': [{
            'name': 'Chocolate Chip Cookies',
            'description': 'Soft, chewy cookies with crisp edges.',
            'source_quote': 'Chocolate Chip Cookies',
            'ingredients': [
                {'quantity': '2 1/4 cups', 'amount': 2.25,
                 'unit': 'cup', 'item': 'all-purpose flour'},
                {'quantity': 'a pinch', 'amount': None,
                 'unit': None, 'item': 'salt'},
            ],
            'steps': [
                {'text': 'Prep',
                 'sub_steps': ['Preheat oven to 190°C.',
                               'Cream butter and sugar.']},
            ],
        }]
    },
}

INVALID_SAMPLES = {
    'pipeline/source-fetch.yaml': {'not_path': 123},
    'pipeline/source-convert.yaml': {'converted_path': 123},
    'pipeline/vault-gate.yaml': {'proceed': 'yes'},
    'pipeline/judge-verdict.yaml': {'verdict': 'INVALID_VALUE'},
    'extractors/classify.yaml': {
        'quintet': {'media': 'paper'}  # missing required fields
    },
    'extractors/recipes.yaml': {
        # Missing required fields (description, source_quote);
        # ingredients empty (minItems: 1).
        'recipes': [{
            'name': 'X',
            'ingredients': [],
            'steps': ['ok'],
        }]
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


# ---- Quintet vocabulary <-> classify schema sync ----------------------------

QUINTET_PATH = (
    Path(__file__).resolve().parents[1] / 'curator' / 'quintet.yaml'
)


@pytest.mark.parametrize(
    'slot',
    ['media', 'form', 'register', 'discipline', 'audience'],
)
def test_classify_schema_covers_quintet_vocab(slot):
    '''Every value declared in quintet.yaml must be in the classify
    schema enum for that slot. Otherwise classify-stage extraction
    fails at schema validation for any source needing that value.
    '''
    quintet = yaml.safe_load(QUINTET_PATH.read_text(encoding='utf-8'))
    schema = yaml.safe_load(
        (SCHEMAS_ROOT / 'extractors' / 'classify.yaml').read_text(
            encoding='utf-8'))

    vocab = set(quintet['slots'][slot]['values'].keys())
    enum = set(
        schema['properties']['quintet']['properties'][slot]['enum'])

    missing = vocab - enum
    assert not missing, (
        f'classify.yaml {slot}.enum is missing values declared in '
        f'quintet.yaml: {sorted(missing)}'
    )
