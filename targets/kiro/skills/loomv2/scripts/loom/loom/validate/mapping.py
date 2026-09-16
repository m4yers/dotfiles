"""Static graph.yaml ``input:`` mapping validation.

Walks every task's ``input_mapping`` and raises
:class:`ReservedShadowError` when a key is a reserved engine-provided
name (``__loom``, ``__task``). Reserved names are engine-filled at
dispatch; wiring them through the mapping would let a graph override
the engine's own values, so both static and dispatch layers reject the
shadow.

The locality check for cross-task refs stays in
``loom.validate.references``; this validator only owns the shadow
rule.
"""
from __future__ import annotations

from loom.engine.models import LoomPlan, Task
from loom.engine.reserved import RESERVED_FIELDS
from loom.errors import ReservedShadowError


def validate_mapping(plan: LoomPlan) -> None:
    """Reject reserved-name keys in every task's ``input_mapping``."""
    for t in plan.tasks:
        if not isinstance(t, Task):
            continue
        if not t.input_mapping:
            continue
        for key in t.input_mapping:
            if key in RESERVED_FIELDS:
                raise ReservedShadowError(
                    t.id, field=key, doc="references/io.md"
                )
