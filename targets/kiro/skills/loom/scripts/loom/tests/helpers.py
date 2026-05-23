'''Test helpers: schema-file builders, plan-construction helpers.'''
from pathlib import Path

import yaml

from loom import LoomPlan, Task
from loom.plan import tool, agent, human, make_plan


def write_schema(path: Path, schema: dict) -> Path:
    '''Write a schema YAML file and return its path.'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(schema, sort_keys=False), encoding='utf-8')
    return path


def write_template(path: Path, content: str) -> Path:
    '''Write a Jinja2 template file and return its path.'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return path


def write_output(path: Path, data: dict) -> Path:
    '''Write an output.yaml file.'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
    return path


def any_object_schema() -> dict:
    return {'type': 'object'}


def int_val_schema() -> dict:
    return {
        'type': 'object',
        'properties': {'val': {'type': 'integer'}},
        'required': ['val'],
    }


def str_name_schema() -> dict:
    return {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }


def simple_tool_plan(tmp_path: Path, cmd=None) -> tuple[LoomPlan, Path]:
    '''Build a minimal tool plan with schema on disk. Returns (plan, schema_path).'''
    schema_path = write_schema(tmp_path / 'schemas' / 's.yaml', int_val_schema())
    plan = make_plan(
        tool('t1', cmd=cmd or ['echo', '{"val": 42}'], output_schema=schema_path),
    )
    return plan, schema_path


def two_tool_chain(tmp_path: Path) -> LoomPlan:
    '''Two tool tasks: t1 -> t2 where t2 references t1 output.'''
    s = write_schema(tmp_path / 'schemas' / 's.yaml', int_val_schema())
    return make_plan(
        tool('t1', cmd=['python', '-c',
                        'import json,os; print(json.dumps({"val":1}))'],
             output_schema=s),
        tool('t2', cmd=['python', '-c',
                        'import json,os; print(json.dumps({"val":2}))'],
             output_schema=s, depends_on=['t1']),
    )
