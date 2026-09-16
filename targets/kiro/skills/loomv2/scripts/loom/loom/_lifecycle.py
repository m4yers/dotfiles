"""Lifecycle: loom.init, loom.extend, loom.resume.

init / extend accept a ``loom_root`` path and load ``graph.yaml``
internally via the internal plan API (``loom.plan``). Consumers never
build plans in Python.

Each function's docstring documents its preconditions, side effects,
error surface, and returned runtime. These docstrings are the
lifecycle contract.
"""
from __future__ import annotations

from pathlib import Path

from loom.engine.inline import expand_subgraphs
from loom.engine.models import LoomPlan
from loom.engine.runner import LoomRuntime
from loom.engine.store import read_plan_yaml, write_plan_yaml
from loom.errors import WorkdirExistsError, WorkdirNotEmptyError


def init(workdir: Path, *, loom_root: Path) -> LoomRuntime:
    """Initialise a fresh workdir from ``<loom_root>/graph.yaml``.

    Preconditions:
      - ``workdir`` does not exist, or is an empty directory.
      - ``<loom_root>/graph.yaml`` exists and validates.

    Side effects:
      - Loads and validates the plan (internal ``loom.plan`` API).
      - Runs static validation on the composed (post-inlining) plan.
      - Writes plan.yaml atomically.

    Raises:
      - WorkdirExistsError if workdir already contains plan.yaml.
      - WorkdirNotEmptyError if workdir has unrecognised contents.
      - LoomPlanError subclasses on validation failure (no state written).

    Returns a LoomRuntime bound to workdir.
    """
    from loom.plan import from_graph_yaml

    workdir = Path(workdir)
    if (workdir / "plan.yaml").exists():
        raise WorkdirExistsError(f"workdir already has plan.yaml: {workdir}")
    if workdir.exists() and any(workdir.iterdir()):
        raise WorkdirNotEmptyError(f"workdir has unexpected contents: {workdir}")
    workdir.mkdir(parents=True, exist_ok=True)

    plan = from_graph_yaml(Path(loom_root))
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
    from loom.validate.templates import validate_templates
    from loom.validate.versions import check_versions

    validate_composition(plan)
    validate_dag(plan)
    validate_single_entry_exit(plan)
    validate_references(plan)
    validate_mapping(plan)
    validate_templates(plan)
    validate_loops(plan)
    if pinning_graph is not None:
        check_versions(plan, pinning_graph)
