"""engine — generic plan-execution library.

Public API:

    from engine import EngineRun, ActionSpec, RunFailed
    from engine.models import Plan, Task, State

EngineRun is the only class applications need to interact with.
Workdir lifecycle, plan/state I/O, dispatcher invocation, and DAG
transitions are all hidden behind it.
"""
from __future__ import annotations

from engine.models import Plan, Task
from engine.runner import ActionSpec, EngineRun, RunFailed

__all__ = [
    "ActionSpec",
    "EngineRun",
    "Plan",
    "RunFailed",
        "Task",
]
