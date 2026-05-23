'''Reference + JMESPath static tracing + type compatibility checks.'''
from __future__ import annotations

from typing import Any

import jmespath

from loom.engine.models import LoomPlan, Task
from loom.engine.algorithm import desugar_predicate, _TASK_REF_RE
from loom.errors import ReferenceError as LoomReferenceError, TypeMismatchError, LoomPlanError
from loom.validate.schemas import SchemaCache


def validate_references(plan: LoomPlan, schemas: SchemaCache) -> None:
    '''Validate ${task:id:expr} references, JMESPath field tracing, and
    type compatibility for predicate comparators.
    '''
    by_id = {t.id: t for t in plan.tasks}
    for t in plan.tasks:
        contexts: list[tuple[str, str, bool]] = []
        if t.cmd:
            for arg in t.cmd:
                contexts.append((arg, f'task {t.id!r} cmd', False))
        if t.vars:
            for k, v in t.vars.items():
                if isinstance(v, str):
                    contexts.append((v, f'task {t.id!r} vars[{k!r}]', False))
        if t.when:
            contexts.append((t.when, f'task {t.id!r} when', True))

        for s, where, is_predicate in contexts:
            for m in _TASK_REF_RE.finditer(s):
                ref_tid = m.group(1)
                if ref_tid not in by_id:
                    raise LoomReferenceError(
                        f'{where}: ${{task:{ref_tid}:...}} references unknown task id')
                ref_path = m.group(2)
                if ref_path:
                    _trace_path(by_id[ref_tid], ref_path, schemas, where)

        if t.when:
            _validate_when_types(t, by_id, schemas)


def _trace_path(
    referenced: Task,
    jmes_path: str,
    schemas: SchemaCache,
    where: str,
) -> dict | None:
    '''Trace JMESPath through referenced task's output_schema.'''
    if not referenced.output_schema:
        return None
    schema = schemas.load(referenced.output_schema)
    try:
        parsed = jmespath.compile(jmes_path).parsed
    except Exception as e:
        raise LoomReferenceError(
            f'{where}: invalid JMESPath {jmes_path!r}: {e}')
    return _walk_subexpr(parsed, schema, where, jmes_path)


def _walk_subexpr(node: dict, schema: dict | None, where: str, expr: str) -> dict | None:
    '''Walk a JMESPath AST node and trace through schema.'''
    if schema is None:
        return None
    nt = node.get('type')

    if nt == 'identity':
        return schema

    if nt == 'field':
        name = node['value']
        if schema.get('type') == 'object' or 'properties' in schema:
            props = schema.get('properties', {})
            if name not in props:
                raise LoomReferenceError(
                    f'{where}: field {name!r} not declared in schema for {expr!r}')
            return props[name]
        return None

    if nt == 'index':
        if schema.get('type') == 'array' or 'items' in schema:
            return schema.get('items')
        return None

    if nt == 'subexpression':
        # Flat children list: walk sequentially
        cur = schema
        for child in node.get('children', []):
            cur = _walk_subexpr(child, cur, where, expr)
            if cur is None:
                return None
        return cur

    if nt == 'index_expression':
        cur = schema
        for child in node.get('children', []):
            cur = _walk_subexpr(child, cur, where, expr)
            if cur is None:
                return None
        return cur

    # Untraceable: filter_projection, flatten, function_expression, etc.
    return None


_PY_TO_JSONSCHEMA = {
    str:        ('string',),
    int:        ('integer', 'number'),
    float:      ('number',),
    bool:       ('boolean',),
    type(None): ('null',),
}


def _validate_when_types(t: Task, by_id: dict, schemas: SchemaCache) -> None:
    '''For comparators in t.when, check literal type vs field schema type.'''
    if not t.when:
        return
    desugared = desugar_predicate(t.when)
    try:
        parsed = jmespath.compile(desugared).parsed
    except Exception as e:
        raise LoomPlanError(
            f'task {t.id!r} when: predicate fails to parse: {e}')
    _walk_comparators(parsed, by_id, schemas, f'task {t.id!r} when', desugared)


def _walk_comparators(
    node: dict, by_id: dict, schemas: SchemaCache, where: str, expr: str,
) -> None:
    nt = node.get('type')
    if nt == 'comparator':
        children = node.get('children', [])
        if len(children) == 2:
            lhs, rhs = children
            # field == literal
            fs = _resolve_task_field(lhs, by_id, schemas, where, expr)
            lit = _extract_literal(rhs)
            if fs is not None and lit is not None:
                _check_compat(fs, lit, node.get('value', ''), where, expr)
            # literal == field
            fs2 = _resolve_task_field(rhs, by_id, schemas, where, expr)
            lit2 = _extract_literal(lhs)
            if fs2 is not None and lit2 is not None:
                _check_compat(fs2, lit2, node.get('value', ''), where, expr)
        return
    for c in node.get('children', []):
        _walk_comparators(c, by_id, schemas, where, expr)


def _resolve_task_field(
    node: dict, by_id: dict, schemas: SchemaCache, where: str, expr: str,
) -> dict | None:
    '''Resolve a subexpression starting with task."id".<rest> to a schema.'''
    if node.get('type') != 'subexpression':
        return None
    children = node.get('children', [])
    if len(children) < 3:
        return None
    # children[0] must be field 'task', children[1] must be field (the id)
    if children[0].get('type') != 'field' or children[0].get('value') != 'task':
        return None
    if children[1].get('type') != 'field':
        return None
    tid = children[1]['value']
    ref_task = by_id.get(tid)
    if ref_task is None or not ref_task.output_schema:
        return None
    schema = schemas.load(ref_task.output_schema)
    # Walk remaining children through schema
    cur = schema
    for child in children[2:]:
        cur = _walk_subexpr(child, cur, where, expr)
        if cur is None:
            return None
    return cur


def _extract_literal(node: dict) -> Any:
    if node.get('type') == 'literal':
        return node.get('value')
    return None


def _check_compat(
    field_schema: dict, literal: Any, op: str, where: str, expr: str,
) -> None:
    schema_types = field_schema.get('type')
    if schema_types is None:
        return
    if isinstance(schema_types, str):
        schema_types = (schema_types,)
    else:
        schema_types = tuple(schema_types)
    py_compat = _PY_TO_JSONSCHEMA.get(type(literal), ())
    if not any(t in schema_types for t in py_compat):
        raise TypeMismatchError(
            f'{where}: comparator {op!r} compares field of type '
            f'{schema_types!r} with literal of type '
            f'{type(literal).__name__!r} in {expr!r}')
