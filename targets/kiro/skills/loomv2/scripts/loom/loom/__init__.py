"""loom — DAG task-execution library with self-contained task folders.

Public (consumer) API:

    loom.init(workdir, loom_root=...)   -> LoomRuntime
    loom.extend(runtime, loom_root=...) -> LoomRuntime
    loom.resume(workdir)                -> LoomRuntime
    LoomRuntime.next()                  -> ActionSpec | None
    LoomRuntime.commit_running(ids)     -> None
    LoomRuntime.complete(id)            -> None
    LoomRuntime.task_output(id)         -> dict

init / extend load ``<loom_root>/graph.yaml`` internally; consumers do
not build plans in Python. Plan construction (make_plan, tool, agent,
human, subgraph, latch, LoomPlan.from_graph_yaml, LoomPlan.to_graph_yaml)
is INTERNAL and lives in ``loom.plan``; see its module docstrings for
advanced use.
"""
from __future__ import annotations

from loom._lifecycle import init, extend, resume
from loom.engine.models import ActionSpec
from loom.engine.runner import LoomRuntime
from loom.errors import (
    DAGError,
    GraphYamlError,
    InputSchemaError,
    IOYamlError,
    IrreducibleLoopError,
    KindMismatchError,
    LoomPlanError,
    LoopEscapeError,
    LoopNestingError,
    MultipleEntriesError,
    MultipleExitsError,
    NamespaceCollisionError,
    NoExitConditionError,
    OutputSchemaError,
    PredicateEvalError,
    ReferenceError,
    RenderFailed,
    RunAborted,
    RunFailed,
    SchemaError,
    SubgraphContractError,
    TaskFolderError,
    TaskVersionMismatchError,
    ToolIOVersionMismatchError,
    ToolTaskError,
    TypeMismatchError,
    WorkdirExistsError,
    WorkdirNotEmptyError,
)

__version__ = "0.2.0"

__all__ = [
    "__version__",
    # Lifecycle (public)
    "init",
    "extend",
    "resume",
    # Runtime and action spec (public return types)
    "LoomRuntime",
    "ActionSpec",
    # Errors (public exception surface)
    "LoomPlanError",
    "DAGError",
    "MultipleEntriesError",
    "MultipleExitsError",
    "TaskFolderError",
    "IOYamlError",
    "GraphYamlError",
    "KindMismatchError",
    "SchemaError",
    "ReferenceError",
    "TypeMismatchError",
    "NoExitConditionError",
    "IrreducibleLoopError",
    "LoopEscapeError",
    "LoopNestingError",
    "SubgraphContractError",
    "NamespaceCollisionError",
    "TaskVersionMismatchError",
    "ToolIOVersionMismatchError",
    "WorkdirExistsError",
    "WorkdirNotEmptyError",
    "RunFailed",
    "RunAborted",
    "OutputSchemaError",
    "InputSchemaError",
    "PredicateEvalError",
    "RenderFailed",
    "ToolTaskError",
]
