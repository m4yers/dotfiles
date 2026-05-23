'''Top-level lifecycle functions: init, extend, resume.

These are the primary public API. Skills call them; LoomRuntime is
returned but not user-instantiated.
'''
from __future__ import annotations

from pathlib import Path

from loom.engine import store
from loom.engine.models import LoomPlan
from loom.engine.runner import LoomRuntime
from loom.errors import LoomPlanError, WorkdirExistsError, WorkdirNotEmptyError
from loom.validate import validate_plan, SchemaCache


def init(*, workdir: str | Path, plan: LoomPlan) -> LoomRuntime:
    '''Validate the plan, prepare the workdir, lower to plan.yaml, return runtime.

    Workdir handling:
      - workdir does not exist:              create it; write plan.yaml
      - workdir exists, empty:               write plan.yaml inside it
      - workdir contains plan.yaml:          raise WorkdirExistsError
      - workdir non-empty without plan.yaml: raise WorkdirNotEmptyError

    Validation runs BEFORE any disk write.
    '''
    wd = Path(workdir).expanduser().resolve()
    plan_path = store.plan_path(wd)

    if wd.exists():
        if plan_path.exists():
            raise WorkdirExistsError(
                f'workdir {wd} already contains plan.yaml; use loom.resume()')
        contents = list(wd.iterdir())
        if contents:
            raise WorkdirNotEmptyError(
                f'workdir {wd} contains files but no plan.yaml')

    # Validate BEFORE creating any disk state.
    schemas = validate_plan(plan)

    # Validation passed — create workdir + write plan.yaml.
    wd.mkdir(parents=True, exist_ok=True)
    store.ensure_workdir_dirs(wd)
    store.save_plan(wd, plan)

    return LoomRuntime(workdir=wd, schemas=schemas)


def extend(runtime: LoomRuntime, plan: LoomPlan) -> None:
    '''Merge new tasks into the existing plan.yaml.

    Atomic: validation runs against the merged plan; on failure plan.yaml
    is left unchanged and LoomPlanError is raised.
    '''
    existing = store.load_plan(runtime.workdir)
    existing_ids = existing.ids()

    seen: set[str] = set()
    for t in plan.tasks:
        if t.id in seen:
            raise LoomPlanError(
                f'extend: duplicate id within new tasks: {t.id!r}')
        seen.add(t.id)
        if t.id in existing_ids:
            raise LoomPlanError(
                f'extend: id {t.id!r} already exists in current plan')

    merged = LoomPlan(tasks=list(existing.tasks) + list(plan.tasks))
    validate_plan(merged, runtime._schemas)
    store.save_plan(runtime.workdir, merged)


def resume(workdir: str | Path) -> LoomRuntime:
    '''Re-attach to an existing workdir. Reads plan.yaml, re-loads schemas.

    Does NOT re-validate plan structure.
    Raises FileNotFoundError if workdir or plan.yaml missing.
    Raises SchemaError if a referenced schema file is missing/invalid.
    '''
    wd = Path(workdir).expanduser().resolve()
    if not wd.exists():
        raise FileNotFoundError(f'workdir not found: {wd}')
    if not store.plan_path(wd).exists():
        raise FileNotFoundError(f'plan.yaml not found in workdir: {wd}')

    plan = store.load_plan(wd)
    schemas = SchemaCache()
    for t in plan.tasks:
        if t.output_schema:
            schemas.load(t.output_schema)

    return LoomRuntime(workdir=wd, schemas=schemas)
