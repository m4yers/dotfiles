#!/usr/bin/env python3
'''Generate schemas/extractors/classify.yaml from quintet.yaml slots.'''
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # skill root
QUINTET = ROOT / 'scripts' / 'curator' / 'curator' / 'quintet.yaml'
OUT = ROOT / 'schemas' / 'extractors' / 'classify.yaml'

doc = yaml.safe_load(QUINTET.read_text())
slots = doc['slots']

schema = {
    'type': 'object',
    'required': ['quintet'],
    'properties': {
        'quintet': {
            'type': 'object',
            'required': sorted(slots.keys()),
            'properties': {
                slot: {'type': 'string',
                       'enum': sorted(info['values'].keys())}
                for slot, info in slots.items()
            },
        },
    },
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(yaml.safe_dump(schema, sort_keys=False))
print(f'wrote {OUT}')
