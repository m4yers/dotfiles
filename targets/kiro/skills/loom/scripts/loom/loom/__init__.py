'''loom — generic DAG task-execution library.'''
from __future__ import annotations

# Lifecycle
from loom._lifecycle import init, extend, resume

# Runtime + data models
from loom.engine.runner import LoomRuntime
from loom.engine.models import LoomPlan, Task, ActionSpec

# Plan builder factories
from loom.plan import tool, agent, human, make_plan

# Errors
from loom.errors import (
    LoomPlanError, DAGError, SchemaError,
    ReferenceError, TypeMismatchError,
    WorkdirExistsError, WorkdirNotEmptyError,
    RunFailed, OutputSchemaError, RenderFailed,
)

__version__ = '0.1.0'

__all__ = [
    '__version__',
    # Lifecycle
    'init', 'extend', 'resume',
    # Runtime + data models
    'LoomRuntime', 'LoomPlan', 'Task', 'ActionSpec',
    # Plan builder
    'tool', 'agent', 'human', 'make_plan',
    # Errors
    'LoomPlanError', 'DAGError', 'SchemaError',
    'ReferenceError', 'TypeMismatchError',
    'WorkdirExistsError', 'WorkdirNotEmptyError',
    'RunFailed', 'OutputSchemaError', 'RenderFailed',
]
