'''loom — generic DAG task-execution library.'''
from __future__ import annotations

# Lifecycle
from loom._lifecycle import init, extend, resume

# Runtime + data models
from loom.engine.runner import LoomRuntime
from loom.engine.models import LoomPlan, Task, ActionSpec

# Plan builder factories
from loom.plan import tool, agent, human, make_plan, latch

# Visualisation
from loom.visualise import visualise, visualise_workdir

# Errors
from loom.errors import (
    LoomPlanError, DAGError, SchemaError,
    ReferenceError, TypeMismatchError,
    LoopError, NoExitConditionError, IrreducibleLoopError,
    LoopEscapeError, LoopNestingError,
    WorkdirExistsError, WorkdirNotEmptyError,
    RunFailed, OutputSchemaError, RenderFailed, RunAborted,
)

__version__ = '0.1.0'

__all__ = [
    '__version__',
    # Lifecycle
    'init', 'extend', 'resume',
    # Runtime + data models
    'LoomRuntime', 'LoomPlan', 'Task', 'ActionSpec',
    # Plan builder
    'tool', 'agent', 'human', 'make_plan', 'latch',
    # Visualisation
    'visualise', 'visualise_workdir',
    # Errors
    'LoomPlanError', 'DAGError', 'SchemaError',
    'ReferenceError', 'TypeMismatchError',
    'LoopError', 'NoExitConditionError', 'IrreducibleLoopError',
    'LoopEscapeError', 'LoopNestingError',
    'WorkdirExistsError', 'WorkdirNotEmptyError',
    'RunFailed', 'OutputSchemaError', 'RenderFailed', 'RunAborted',
]
