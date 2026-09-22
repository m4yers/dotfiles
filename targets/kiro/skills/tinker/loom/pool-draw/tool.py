"""Tool body for the `pool-draw` task (loomv2 native contract).

Loop header of the implementation pool loop. Deterministically
draws the current task from the ordered pool using the previous
round's pool-advance output (`next_cursor`); on the first
iteration (`prev` is null) it draws index 0.

The latch predicate on pool-advance guarantees this task never
runs with an exhausted pool, so `current_task` is always a real
task.

The engine loads this module in-process and calls `pool_draw`;
all YAML IO and schema validation is engine-owned.
"""

from __future__ import annotations

from io_types import PoolDrawInput, PoolDrawOutput


def pool_draw(inp: PoolDrawInput) -> PoolDrawOutput:
    tasks = inp.tasks
    total = len(tasks)

    cursor = 0
    if inp.prev is not None:
        cursor = int(inp.prev.get("next_cursor", 0))

    if not 0 <= cursor < total:
        raise RuntimeError(
            f"pool-draw: cursor {cursor} out of range for pool of "
            f"{total} tasks — the latch predicate should have "
            "terminated the loop."
        )

    return PoolDrawOutput(
        cursor=cursor,
        total=total,
        current_task=tasks[cursor],
    )
