"""Tool task: wave planner (loop header), port of code-review's
cr-shard-plan.

Resumes at the previous wave's offset and fills fixed slots with up to
3 checks each, never mixing reference files in one slot. Emits
``has_more`` so the audit-aggregate latch loops until every check is
covered.
"""
from __future__ import annotations

# 16 parallel audit-shard agents per wave; matches the audit-shard-NN
# graph entries and the shard_NN output fields.
SLOTS = 16
# 3 checks per agent keeps each judgement focused; pinned by
# schemas/shard.yaml maxItems.
PER_SHARD = 3


def _empty_slot() -> dict:
    return {"populated": False, "file": "", "checks": []}


def run(checks: list[dict], prev: dict | None) -> dict:
    prev = prev or {}
    offset = int(prev.get("next_offset", 0))
    wave = int(prev.get("wave", 0)) + 1

    slots: list[dict] = []
    i = offset
    while len(slots) < SLOTS and i < len(checks):
        file = checks[i]["file"]
        batch: list[dict] = []
        while (len(batch) < PER_SHARD and i < len(checks)
               and checks[i]["file"] == file):
            batch.append(checks[i])
            i += 1
        slots.append({"populated": True, "file": file, "checks": batch})
    while len(slots) < SLOTS:
        slots.append(_empty_slot())

    out = {f"shard_{n:02d}": slots[n - 1] for n in range(1, SLOTS + 1)}
    out.update(next_offset=i, has_more=i < len(checks), wave=wave,
               total_checks=len(checks))
    return out
