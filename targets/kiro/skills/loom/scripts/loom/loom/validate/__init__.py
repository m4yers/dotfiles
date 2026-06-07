'''Validation pipeline orchestration.'''
from __future__ import annotations

from loom.engine.models import LoomPlan
from loom.validate.dag import validate_dag, validate_kind_fields
from loom.validate.schemas import SchemaCache
from loom.validate.references import validate_references
from loom.validate.loops import validate_loops


def validate_plan(plan: LoomPlan, schemas: SchemaCache | None = None) -> SchemaCache:
    '''Run the full static-validation pipeline. Returns the populated
    SchemaCache so callers can pass it to runtime methods.'''
    if schemas is None:
        schemas = SchemaCache()
    validate_dag(plan)
    validate_kind_fields(plan)
    validate_loops(plan)
    for t in plan.tasks:
        if t.output_schema:
            schemas.load(t.output_schema)
    validate_references(plan, schemas)
    return schemas


__all__ = [
    'validate_plan', 'validate_dag', 'validate_kind_fields',
    'validate_references', 'validate_loops', 'SchemaCache',
]
