"""Lifecycle: loom.init, loom.extend, loom.resume.

init / extend accept a ``loom_root`` path and load ``graph.yaml``
internally via the internal plan API (``loom.plan``). Consumers never
build plans in Python.

Each function's docstring documents its preconditions, side effects,
error surface, and returned runtime. These docstrings are the
lifecycle contract.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from loom.engine.inline import expand_subgraphs
from loom.engine.models import LoomPlan
from loom.engine.runner import LoomRuntime
from loom.engine.store import read_plan_yaml, write_plan_yaml


def init(workdir: Path, *, loom_root: Path, graph: Path | str | None = None) -> LoomRuntime:
    """Initialise a fresh workdir from ``<loom_root>/graph.yaml``.

    Preconditions:
      - ``<loom_root>/graph.yaml`` exists and validates.

    Side effects:
      - If ``workdir`` exists it is unconditionally wiped
        (``shutil.rmtree``) before recreation — existing contents are
        deleted, whether the workdir carries a stale ``plan.yaml`` or
        arbitrary unrelated files. There is no error path for
        non-empty or plan.yaml-bearing workdirs; wipe-and-recreate is
        the sole shape.
      - Loads and validates the plan (internal ``loom.plan`` API).
      - Runs static validation on the composed (post-inlining) plan.
      - Writes plan.yaml atomically.

    Raises:
      - LoomPlanError subclasses on validation failure (no state written).

    Returns a LoomRuntime bound to workdir.
    """
    from loom.plan import from_graph_yaml

    workdir = Path(workdir)
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    plan = from_graph_yaml(Path(loom_root), graph)
    composed = expand_subgraphs(plan)
    _static_validate(composed, pinning_graph=None)
    write_plan_yaml(workdir, composed)
    return LoomRuntime(workdir=workdir, plan=composed)


def extend(runtime: LoomRuntime, *, loom_root: Path) -> LoomRuntime:
    """Extend ``runtime``'s plan with tasks from ``<loom_root>/graph.yaml``.

    Loads the graph, inlines subgraphs, merges tasks into the runtime's
    plan, and re-runs static validation on the composed plan. Atomic
    plan.yaml write; unchanged on validation failure.
    """
    from loom.plan import from_graph_yaml

    more = from_graph_yaml(Path(loom_root))
    merged = LoomPlan(
        loom_root=runtime.plan.loom_root,
        tasks=list(runtime.plan.tasks) + list(more.tasks),
    )
    composed = expand_subgraphs(merged)
    _static_validate(composed, pinning_graph=None)
    write_plan_yaml(runtime.workdir, composed)
    runtime.plan = composed
    return runtime


def resume(workdir: Path) -> LoomRuntime:
    """Rebuild a LoomRuntime from an on-disk plan.yaml.

    Raises FileNotFoundError if the workdir does not exist,
    GraphYamlError if plan.yaml is malformed.
    """
    workdir = Path(workdir)
    plan = read_plan_yaml(workdir)
    return LoomRuntime(workdir=workdir, plan=plan)


def _static_validate(plan: LoomPlan, pinning_graph: Path | None) -> None:
    """Run every static validator against the composed plan.

    Delegates to validate/* modules. Kept here so the lifecycle is the
    single entry point for validation and any test can invoke it via
    loom.init.
    """
    from loom.validate.composition import validate_composition
    from loom.validate.dag import validate_dag
    from loom.validate.graph import validate_single_entry_exit
    from loom.validate.loops import validate_loops
    from loom.validate.mapping import validate_mapping
    from loom.validate.references import validate_references
    from loom.validate.subtype import validate_required_wiring, validate_subtype
    from loom.validate.templates import validate_templates
    from loom.validate.tool_entry import validate_tool_entry
    from loom.validate.versions import check_versions

    validate_composition(plan)
    validate_dag(plan)
    validate_single_entry_exit(plan)
    # validate_tool_entry runs before any pass that would try to load
    # a tool task's io.yaml or project through its output schema, so
    # an ambiguous or non-executable shim fails fast without any
    # workdir write.
    validate_tool_entry(plan)
    validate_references(plan)
    # validate_mapping runs BEFORE the subtype / required-wiring passes
    # so that reserved-shadow keys (`__loom` / `__task` in an
    # ``input:`` mapping) surface as :class:`ReservedShadowError`
    # without the alignment passes first attempting to load the
    # consumer's ``io.yaml`` (which the shadow may itself invalidate).
    validate_mapping(plan)
    validate_subtype(plan)
    validate_required_wiring(plan)
    validate_templates(plan)
    validate_loops(plan)
    if pinning_graph is not None:
        check_versions(plan, pinning_graph)
