'''Plan visualisation as a dependents-first ASCII rail (renderdag-backed).

Public API:
  - ``visualise(plan, ...)``: render an in-memory LoomPlan
  - ``visualise_workdir(workdir, ...)``: snapshot from disk

Both return a multi-line string. See render.py for the layout spec.
'''
from __future__ import annotations

from pathlib import Path

from loom.engine.models import LoomPlan
from loom.visualise.render import render

__all__ = ['visualise', 'visualise_workdir']


def visualise(
    plan: LoomPlan,
    *,
    show_when: bool = True,
    show_loops: bool = True,
    ascii_only: bool = False,
    workdir_basename: str | None = None,
) -> str:
    '''Render a plan as a dependents-first rail.

    Accepts a ``LoomRuntime`` via duck type: if the input has a ``.plan``
    attribute, that is used.
    '''
    if hasattr(plan, 'plan') and not isinstance(plan, LoomPlan):
        plan = plan.plan
    return render(
        plan,
        show_when=show_when,
        show_loops=show_loops,
        ascii_only=ascii_only,
        workdir_basename=workdir_basename,
    )


def visualise_workdir(
    workdir: str | Path,
    *,
    show_when: bool = True,
    show_loops: bool = True,
    ascii_only: bool = False,
) -> str:
    '''Snapshot the plan at ``<workdir>/plan.yaml`` as a rail render.

    The header shows the workdir basename for context.
    '''
    wd = Path(workdir).expanduser().resolve()
    plan_path = wd / 'plan.yaml'
    if not plan_path.exists():
        raise FileNotFoundError(f'plan.yaml not found in workdir: {wd}')
    plan = LoomPlan.from_yaml(plan_path)
    return render(
        plan,
        show_when=show_when,
        show_loops=show_loops,
        ascii_only=ascii_only,
        workdir_basename=wd.name,
    )
