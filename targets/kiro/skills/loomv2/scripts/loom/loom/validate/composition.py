"""Static composition validation for subgraphs.

Runs before generic validators. Per subgraph:
  - Child loom root must exist and be valid.
  - Child graph.yaml must meta-validate.
  - Child must have single-entry / single-exit.
  - Parent bindings match child entry input.
  - Parent consumers match child exit output.
  - Sibling instance ids unique.
  - Composed plan is acyclic (delegated to validate/dag).

Delegates io.yaml version-pin checking per child root to
validate/versions.py so drift inside any nested subgraph surfaces at
the parent boundary.
"""
from __future__ import annotations

from pathlib import Path

from loom.engine.models import LoomPlan, SubgraphSpec
from loom.errors import NamespaceCollisionError, SubgraphContractError


def validate_composition(plan: LoomPlan) -> None:
    """Run subgraph-side checks against ``plan``.

    ``plan`` may or may not be pre-expanded. This function inspects
    SubgraphSpec entries directly, so it works on the pre-expansion
    plan; the fully-composed plan is validated by the other validators
    afterwards.
    """
    from loom.discovery import load_graph_yaml
    from loom.validate.graph import validate_single_entry_exit
    from loom.validate.versions import check_versions

    seen_ids: set[str] = set()
    for entry in plan.tasks:
        if not isinstance(entry, SubgraphSpec):
            continue
        if entry.id in seen_ids:
            raise NamespaceCollisionError(
                f"sibling subgraph instance id {entry.id!r} used twice"
            )
        seen_ids.add(entry.id)
        child_root = Path(entry.root_path)
        if not child_root.is_dir():
            raise SubgraphContractError(
                f"subgraph {entry.id!r}: root {child_root} not found"
            )
        # Meta-validate child graph.yaml.
        load_graph_yaml(child_root)
        # Load child plan and check its single-entry/exit rule.
        from loom.plan import from_graph_yaml as _child

        child_plan = _child(child_root)
        validate_single_entry_exit(child_plan)
        # Recursively validate composition of the child.
        validate_composition(child_plan)
        # Version pins per child root.
        check_versions(child_plan, child_root / "graph.yaml")
