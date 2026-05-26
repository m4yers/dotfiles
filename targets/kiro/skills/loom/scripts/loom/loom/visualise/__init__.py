'''Plan visualisation as ASCII pipeline boxes.

Public API:
  - ``visualise(plan, ...)``: render an in-memory LoomPlan
  - ``visualise_workdir(workdir, ...)``: snapshot from disk

Both return a multi-line string. See render.py for layout specification.
'''
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from loom.engine.models import LoomPlan
from loom.visualise.render import render

__all__ = ['visualise', 'visualise_workdir']


def visualise(
    plan: LoomPlan,
    *,
    show_status: bool = True,
    show_when: bool = True,
    show_kind: bool = True,
    hide: Iterable[str] = (),
    width: int | None = None,
    ascii_only: bool = False,
    workdir_basename: str | None = None,
) -> str:
    '''Render a plan as a vertical box-style pipeline.

    Parameters mirror ``render``. Accepts a ``LoomRuntime`` via duck type:
    if the input has a ``.plan`` attribute, that's used.
    '''
    if hasattr(plan, 'plan') and not isinstance(plan, LoomPlan):
        plan = plan.plan
    return render(
        plan,
        show_status=show_status,
        show_when=show_when,
        show_kind=show_kind,
        hide=hide,
        width=width,
        ascii_only=ascii_only,
        workdir_basename=workdir_basename,
    )


def visualise_workdir(
    workdir: str | Path,
    *,
    show_status: bool = True,
    show_when: bool = True,
    show_kind: bool = True,
    hide: Iterable[str] = (),
    width: int | None = None,
    ascii_only: bool = False,
) -> str:
    '''Snapshot the plan at ``<workdir>/plan.yaml`` as a box-style render.

    Status reflects plan.yaml at call time. The header shows the workdir
    basename for context.
    '''
    wd = Path(workdir).expanduser().resolve()
    plan_path = wd / 'plan.yaml'
    if not plan_path.exists():
        raise FileNotFoundError(f'plan.yaml not found in workdir: {wd}')
    plan = LoomPlan.from_yaml(plan_path)
    return render(
        plan,
        show_status=show_status,
        show_when=show_when,
        show_kind=show_kind,
        hide=hide,
        width=width,
        ascii_only=ascii_only,
        workdir_basename=wd.name,
    )
