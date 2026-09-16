"""Dedicated io.yaml version-pin validator.

Compares each Task's ``pinned_version`` (stamped by
LoomPlan.from_graph_yaml) with the CURRENT ``io.yaml`` version on disk.
On mismatch raises TaskVersionMismatchError with the canonical address,
pinned version, current version, and pinning graph.yaml.

Runs BEFORE execution; no state written on failure.
"""
from __future__ import annotations

from pathlib import Path

from loom.discovery import load_io_yaml
from loom.engine.models import LoomPlan, Task
from loom.errors import TaskVersionMismatchError


def check_versions(plan: LoomPlan, pinning_graph_path: Path) -> None:
    """Raise TaskVersionMismatchError on any pin drift."""
    from loom.engine.runner import task_source_folder

    for t in plan.tasks:
        if not isinstance(t, Task) or t.pinned_version is None:
            continue
        folder = task_source_folder(plan.loom_root, t)
        current = load_io_yaml(folder).version
        if current != t.pinned_version:
            raise TaskVersionMismatchError(
                canonical_address=t.id,
                pinned_version=t.pinned_version,
                current_version=current,
                graph_yaml=Path(pinning_graph_path),
            )
