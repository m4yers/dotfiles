'''Rail renderer for loom plans, built on the ``renderdag`` library
(a Python port of Meta Sapling's commit-graph renderer).

Public entry point: ``render(plan, ...)``. Produces a multi-line string —
a git-log-style rail where each task is one row:

    glyph  NN id   <annotations>

Layout
------
* Rows are emitted dependents-first (see ``layout.render_order``) so each
  task sits above the dependencies it consumes, with parallel branches in
  separate rail columns.
* The node glyph encodes task kind (``layout``/``glyphs.node_glyph``).
* ``depends_on_all`` edges are direct parents (solid ``│``);
  ``depends_on_any`` edges are indirect ancestors (dotted ``╷``). This
  distinction is native to renderdag's parent/ancestor model — no glyph
  surgery required.
* Loop latches and ``when:`` predicates are appended inline on the node
  row (``glyphs.annotation``).

``ascii_only`` swaps renderdag's ``BoxDrawingRenderer`` for its
``AsciiRenderer`` and uses ASCII glyph/annotation fallbacks.
'''
from __future__ import annotations

from pathlib import Path  # noqa: F401  (kept for type parity with callers)

from renderdag import (
    Ancestor,
    AsciiRenderer,
    BoxDrawingRenderer,
    GraphRowRenderer,
)
from renderdag._output import OutputRendererOptions

from loom.engine.models import LoomPlan
from loom.visualise.glyphs import annotation, node_glyph
from loom.visualise.layout import render_order


def _legend(ascii_only: bool) -> str:
    if ascii_only:
        return ('legend: o tool * agent # human @ loop   '
                '| all-dep : any-dep   when:/loop inline')
    return ('legend: ○ tool · ◆ agent · ▣ human · ↻ loop   '
            '│ all-dep · ╷ any-dep   when:/↻ inline')


def render(
    plan: LoomPlan,
    *,
    show_when: bool = True,
    show_loops: bool = True,
    ascii_only: bool = False,
    workdir_basename: str | None = None,
) -> str:
    '''Render a plan as a dependents-first rail. Returns a multi-line str.'''
    if not plan.tasks:
        return 'PLAN — (empty)'

    title = f'PLAN  {workdir_basename}' if workdir_basename else 'PLAN'
    header = f'{title}  ·  {len(plan.tasks)} tasks'
    if ascii_only:
        header = header.replace(' · ', ' - ').replace('·', '-')

    id_set = plan.ids()
    index = {t.id: i + 1 for i, t in enumerate(plan.tasks)}

    options = OutputRendererOptions()
    options.min_row_height = 1
    inner = GraphRowRenderer()
    renderer = (AsciiRenderer(inner, options) if ascii_only
                else BoxDrawingRenderer(inner, options))

    chunks: list[str] = []
    for task_id in render_order(plan):
        task = plan.get(task_id)
        parents = (
            [Ancestor.parent(d) for d in task.depends_on_all if d in id_set]
            + [Ancestor.ancestor(d) for d in task.depends_on_any
               if d in id_set]
        )
        glyph = node_glyph(task, ascii_only=ascii_only)
        label = f'{index[task_id]:02d} {task.id}' + annotation(
            task, show_when=show_when, show_loops=show_loops,
            ascii_only=ascii_only,
        )
        chunks.append(renderer.next_row(task_id, parents, glyph, label))

    body = ''.join(chunks).rstrip('\n')
    return f'{header}\n\n{body}\n\n{_legend(ascii_only)}'
