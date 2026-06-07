'''Glyphs and inline annotations for the rail renderer.

The node glyph encodes task *kind* only (tool / agent / human), with a
loop latch taking precedence. Status is not encoded in the glyph — the
rail view is a structural map, not a live status dashboard.

Edge style (solid vs dotted) is owned by renderdag: ``depends_on_all``
edges are drawn as direct parents (solid ``│``) and ``depends_on_any``
edges as indirect ancestors (dotted ``╷``). See ``render.py``.
'''
from __future__ import annotations

from loom.engine.models import Task

# Node glyphs (unicode). Loop latch overrides kind.
KIND_GLYPHS = {'tool': '○', 'agent': '◆', 'human': '▣'}
LATCH_GLYPH = '↻'

# 7-bit ASCII fallbacks.
KIND_GLYPHS_ASCII = {'tool': 'o', 'agent': '*', 'human': '#'}
LATCH_GLYPH_ASCII = '@'


def node_glyph(task: Task, *, ascii_only: bool = False) -> str:
    '''Return the single-character node glyph for a task.

    Loop latches render as ``↻`` (``@`` in ascii); otherwise the glyph
    reflects the task kind.
    '''
    if task.latch:
        return LATCH_GLYPH_ASCII if ascii_only else LATCH_GLYPH
    table = KIND_GLYPHS_ASCII if ascii_only else KIND_GLYPHS
    default = 'o' if ascii_only else '○'
    return table.get(task.kind, default)


def annotation(
    task: Task,
    *,
    show_when: bool = True,
    show_loops: bool = True,
    ascii_only: bool = False,
) -> str:
    '''Return the inline annotation appended to a task's node row.

    Combines an optional loop-latch descriptor and an optional ``when:``
    predicate. Returns an empty string when there is nothing to annotate;
    otherwise the result is prefixed with separating whitespace so it can
    be concatenated directly onto the node label.
    '''
    sep = ' | ' if ascii_only else ' · '
    arrow = '->' if ascii_only else '→'
    ellipsis = '...' if ascii_only else '…'
    loop_mark = 'loop' if ascii_only else '↻ loop'

    parts: list[str] = []

    if show_loops and task.latch:
        latch = task.latch
        bits = [f'{loop_mark} {arrow} {latch.get("header", "?")}']
        if latch.get('fuel') is not None:
            bits.append(f'fuel {latch["fuel"]}')
        if latch.get('while'):
            bits.append(f'while {ellipsis}')
        parts.append(sep.join(bits))

    if show_when and task.when:
        parts.append(f'when: {task.when}')

    if not parts:
        return ''
    return '   ' + '   '.join(parts)
