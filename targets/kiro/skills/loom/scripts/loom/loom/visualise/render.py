'''Box-format renderer for loom plans.

Public entry point: ``render(plan, ...)``. Produces a multi-line string of
ASCII box-drawn pipeline stages stacked along a centerline rail.

See `~/shared/projects/loom/artifacts/20260525-201800-design-viz.md`
for the layout specification this module implements.
'''
from __future__ import annotations

import os
import re
import shutil
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from loom.engine.models import LoomPlan, Task, TERMINAL_STATUSES
from loom.visualise.glyphs import (
    box_chars, edge_chars, kind_tag, status_glyph,
    STATUS_GLYPHS_UNICODE,
)
from loom.visualise.layout import layer_of_all


# ---- layout constants ----

LINEAR_INNER = 42
LINEAR_OUTER = LINEAR_INNER + 2  # 44
FANOUT_INNER = 70
FANOUT_OUTER = FANOUT_INNER + 2  # 72

# Inside the fanout's inner area (70 cols), col1 is 34 wide, divider is 1,
# col2 is 35 wide. The divider sits at inner col 34 (0-indexed).
FANOUT_COL1_WIDTH = 34
FANOUT_DIVIDER_INNER_POS = 34
FANOUT_COL2_WIDTH = FANOUT_INNER - FANOUT_COL1_WIDTH - 1  # 35

# Inside the linear box's inner area (42 cols), the bottom-border tee
# sits at inner col 20 (0-indexed) — the natural visual centerline.
LINEAR_TEE_INNER_POS = 20

DEFAULT_WIDTH = 100
MIN_WIDTH = FANOUT_OUTER + 4  # 76


def _current_marker(ascii_only: bool) -> str:
    return '<- current' if ascii_only else '← current'


def _sep(ascii_only: bool) -> str:
    return ' | ' if ascii_only else ' · '


def _fan_in_marker(ascii_only: bool) -> str:
    return '* fan-in' if ascii_only else '✦ fan-in'


# ---- entry points ----

def render(
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

    See module docstring and design.md for layout specification.
    '''
    width = _resolve_width(width)
    centerline, linear_indent, fanout_indent = _resolve_centerline(width)
    hide_set = set(hide)

    if not plan.tasks:
        return f'PLAN — (empty)'

    task_index = {t.id: i + 1 for i, t in enumerate(plan.tasks)}
    current_id = _find_current_task_id(plan)
    layers = layer_of_all(plan)

    lines: list[str] = []

    # Header.
    lines.extend(_render_header(
        plan, linear_indent, ascii_only,
        show_status=show_status,
        workdir_basename=workdir_basename,
    ))
    lines.append('')

    # Layers, with edges between.
    for i, layer in enumerate(layers):
        if i > 0:
            lines.extend(_render_edge(centerline, ascii_only))
        if _is_fanout(layer):
            lines.extend(_render_fanout_box(
                layer, i, plan, fanout_indent, ascii_only,
                hide=hide_set, show_when=show_when,
                task_index=task_index, current_id=current_id,
            ))
        else:
            lines.extend(_render_linear_box(
                layer, plan, linear_indent, ascii_only,
                show_when=show_when, show_kind=show_kind,
                task_index=task_index, current_id=current_id,
            ))

    lines.append('')
    lines.append(_legend_line(ascii_only))

    return '\n'.join(lines)


def _resolve_width(width: int | None) -> int:
    if width is None:
        col_env = os.environ.get('COLUMNS')
        if col_env:
            try:
                return max(MIN_WIDTH, int(col_env))
            except ValueError:
                pass
        try:
            cols = shutil.get_terminal_size((DEFAULT_WIDTH, 24)).columns
            return max(MIN_WIDTH, cols)
        except OSError:
            return DEFAULT_WIDTH
    return max(MIN_WIDTH, width)


def _resolve_centerline(width: int) -> tuple[int, int, int]:
    '''Compute (centerline_col, linear_indent, fanout_indent) given width.

    The centerline is the column where edges, linear ┬, and fanout ╦ align.
    '''
    fanout_indent = max(0, (width - FANOUT_OUTER) // 2)
    centerline = fanout_indent + 1 + FANOUT_DIVIDER_INNER_POS
    linear_indent = max(0, centerline - 1 - LINEAR_TEE_INNER_POS)
    return centerline, linear_indent, fanout_indent


# ---- helpers ----

def _find_current_task_id(plan: LoomPlan) -> str | None:
    '''Return id of first task whose status is non-terminal.'''
    for t in plan.tasks:
        if t.status not in TERMINAL_STATUSES:
            return t.id
    return None


def _is_fanout(layer: list[Task]) -> bool:
    return len(layer) > 3


def _status_counts(plan: LoomPlan) -> dict[str, int]:
    c: Counter = Counter()
    for t in plan.tasks:
        c[t.status] += 1
    return dict(c)


def _detect_layer_label(layer: list[Task], layer_idx: int) -> str:
    '''Auto-detect a label for a fanout layer.

    Uses the dominant id prefix (split on '-') if ≥80% of tasks share it.
    Falls back to "Layer N".
    '''
    prefixes = [t.id.split('-', 1)[0] for t in layer]
    cnt = Counter(prefixes)
    common, count = cnt.most_common(1)[0]
    if count / len(layer) >= 0.8 and len(common) >= 3:
        return common.upper()
    return f'Layer {layer_idx}'


_TASK_REF_RE = re.compile(r'task\."?([A-Za-z_][A-Za-z0-9_\-]*)"?(\.[\w.]*)?')


def _detect_branch_root(layer: list[Task]) -> str | None:
    '''Return common upstream path prefix of `when:` predicates in
    the layer, or None.

    Tasks without `when:` are skipped (they are unconditional and
    don't fit the branch concept). Requires at least 2 tasks with
    `when:` predicates that share a path prefix.

    e.g. all task."classify".quintet.{media,form,...} → "classify.quintet".
    '''
    paths: list[list[str]] = []
    for t in layer:
        if not t.when:
            continue
        m = _TASK_REF_RE.search(t.when)
        if not m:
            continue
        upstream = m.group(1)
        rest = (m.group(2) or '').lstrip('.')
        segs = [upstream]
        if rest:
            for s in rest.split('.'):
                s2 = re.match(r'[a-zA-Z_]\w*', s)
                if not s2:
                    break
                segs.append(s2.group(0))
        paths.append(segs)

    if len(paths) < 2:
        return None
    common: list[str] = []
    for i in range(min(len(p) for p in paths)):
        seg = paths[0][i]
        if all(p[i] == seg for p in paths):
            common.append(seg)
        else:
            break
    if not common:
        return None
    return '.'.join(common)


def _classify_for_fanout(t: Task) -> str:
    '''Returns 'active' or 'inactive' for fanout column placement.'''
    if t.status in ('skipped', 'failed'):
        return 'inactive'
    return 'active'


def _format_dep_summary(task: Task, plan: LoomPlan) -> str | None:
    '''Render dep info for a linear-box sub-line. Returns None when deps
    are short enough to imply via the layer connector alone.

    Long lists collapse via prefix grouping (e.g. "24 judges + vault-match").
    '''
    deps = task.depends_on
    if len(deps) <= 5:
        return None
    by_prefix: Counter = Counter()
    others: list[str] = []
    for d in deps:
        parts = d.split('-', 1)
        if len(parts) == 2:
            by_prefix[parts[0]] += 1
        else:
            others.append(d)
    if by_prefix:
        prefix, count = by_prefix.most_common(1)[0]
        # Only treat as a group if at least 3 share the prefix.
        if count >= 3:
            chunks: list[str] = [f'{count} {prefix}s']
            # Tasks NOT matching the prefix:
            extras = [d for d in deps
                      if not d.startswith(prefix + '-') and d != prefix]
            if extras:
                if len(extras) <= 2:
                    chunks.extend(extras)
                else:
                    chunks.append(f'+{len(extras)} others')
            return ' + '.join(chunks)
    return f'{len(deps)} deps'


def _truncate(s: str, width: int) -> str:
    '''Truncate s to width with trailing ellipsis if needed.'''
    if len(s) <= width:
        return s
    if width <= 1:
        return '…'
    return s[: width - 1] + '…'


def _pad(s: str, width: int) -> str:
    if len(s) >= width:
        return s
    return s + ' ' * (width - len(s))


# ---- header ----

def _render_header(
    plan: LoomPlan, indent: int, ascii_only: bool,
    *, show_status: bool, workdir_basename: str | None,
) -> list[str]:
    chars = box_chars('single', ascii_only)
    inner = LINEAR_INNER
    pad = ' ' * indent

    name = workdir_basename or ''
    title = f'PLAN  {name}'.rstrip()

    rows: list[str] = []
    rows.append(_truncate(title, inner - 4))

    if show_status:
        counts = _status_counts(plan)
        glyphs = STATUS_GLYPHS_UNICODE if not ascii_only else None
        # Order matches legend.
        lines = _format_status_lines(counts, ascii_only, max_inner=inner - 4)
        rows.extend(lines)

    out: list[str] = []
    out.append(pad + chars.tl + chars.h * inner + chars.tr)
    for r in rows:
        body = '  ' + _pad(r, inner - 2)
        out.append(pad + chars.v + body + chars.v)
    out.append(pad + chars.bl + chars.h * inner + chars.br)
    return out


def _format_status_lines(
    counts: dict[str, int], ascii_only: bool, max_inner: int,
) -> list[str]:
    '''Format status histogram as 1-2 lines that fit in max_inner.'''
    order = ['done', 'running', 'ready', 'pending', 'failed', 'skipped']
    items: list[str] = []
    total = sum(counts.values())
    for s in order:
        n = counts.get(s, 0)
        if n == 0:
            continue
        glyph = status_glyph(s, ascii_only)
        items.append(f'{glyph} {n} {s}')
    if not items:
        items.append(f'{total} total')
    items.append(f'{total} total')

    # Pack items into lines no wider than max_inner.
    sep = _sep(ascii_only)
    lines: list[str] = []
    cur = ''
    for item in items:
        cand = (cur + sep + item) if cur else item
        if len(cand) <= max_inner:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = item
    if cur:
        lines.append(cur)
    return lines


# ---- linear box ----

def _render_linear_box(
    layer: list[Task], plan: LoomPlan, indent: int, ascii_only: bool,
    *, show_when: bool, show_kind: bool,
    task_index: dict[str, int], current_id: str | None,
) -> list[str]:
    chars = box_chars('single', ascii_only)
    inner = LINEAR_INNER
    pad = ' ' * indent

    rows: list[tuple[str, bool]] = []  # (content, is_current)
    for t in layer:
        rows.append((_format_linear_task_main(
            t, inner, ascii_only, show_kind=show_kind,
            task_index=task_index,
        ), t.id == current_id))
        # Sub-lines for dep summary / when:
        sub = _linear_subline(t, plan, ascii_only)
        if sub:
            rows.append((_pad('       ' + sub, inner), False))
        if show_when and t.when and t.status not in TERMINAL_STATUSES:
            wlines = _format_when_lines(t.when, inner - 7)
            for wl in wlines:
                rows.append((_pad('       ' + wl, inner), False))

    out: list[str] = []
    out.append(pad + chars.tl + chars.h * inner + chars.tr)
    for r, is_current in rows:
        line = pad + chars.v + r + chars.v
        if is_current:
            line += '  ' + _current_marker(ascii_only)
        out.append(line)
    # Bottom border with ┬ at centerline (LINEAR_TEE_INNER_POS).
    bottom = (
        pad
        + chars.bl
        + chars.h * LINEAR_TEE_INNER_POS
        + chars.tee_top
        + chars.h * (inner - LINEAR_TEE_INNER_POS - 1)
        + chars.br
    )
    out.append(bottom)
    return out


def _format_linear_task_main(
    t: Task, inner: int, ascii_only: bool, *,
    show_kind: bool, task_index: dict[str, int],
) -> str:
    '''Format the main (first) row of a linear task content.

    Layout: ` <glyph> <NN>  <name><pad>[<kind>] `
    '''
    glyph = status_glyph(t.status, ascii_only)
    num = f'{task_index[t.id]:02d}'
    kind = kind_tag(t.kind) if show_kind else ' ' * 7
    # ' G NN  ' = 1+1+1+2+2 = 7
    # ' KIND ' = 1+7+1 = 9
    fixed_left = f' {glyph} {num}  '  # 7
    fixed_right = f' {kind} '  # 9
    avail = inner - len(fixed_left) - len(fixed_right)
    name = _truncate(t.id, avail)
    body = fixed_left + name + ' ' * (avail - len(name)) + fixed_right
    return body


def _linear_subline(t: Task, plan: LoomPlan, ascii_only: bool) -> str | None:
    summary = _format_dep_summary(t, plan)
    if summary:
        return f'{_fan_in_marker(ascii_only)} {summary}'
    return None


def _format_when_lines(when_expr: str, max_width: int) -> list[str]:
    '''Wrap a `when:` predicate to fit max_width per line.'''
    text = f'when: {when_expr}'
    if len(text) <= max_width:
        return [text]
    # Wrap on whitespace.
    words = text.split(' ')
    lines: list[str] = []
    cur = ''
    for w in words:
        cand = (cur + ' ' + w) if cur else w
        if len(cand) <= max_width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            if len(w) <= max_width:
                cur = w
            else:
                cur = _truncate(w, max_width)
                lines.append(cur)
                cur = ''
    if cur:
        lines.append(cur)
    return lines


# ---- fanout box ----

def _render_fanout_box(
    layer: list[Task], layer_idx: int, plan: LoomPlan,
    indent: int, ascii_only: bool,
    *, hide: set[str], show_when: bool,
    task_index: dict[str, int], current_id: str | None,
) -> list[str]:
    chars = box_chars('double', ascii_only)
    inner = FANOUT_INNER
    pad = ' ' * indent

    label = _detect_layer_label(layer, layer_idx)
    branch = _detect_branch_root(layer)

    actives = [t for t in layer if _classify_for_fanout(t) == 'active']
    inactives = [t for t in layer if _classify_for_fanout(t) == 'inactive']

    actives.sort(key=lambda t: task_index[t.id])
    inactives.sort(key=lambda t: task_index[t.id])

    # Header line.
    header_bits: list[str] = [label, 'fan-out']
    if branch:
        header_bits.append(f'branch on {branch}')
    header_bits.append(
        f'{len(layer)} tasks ({len(actives)}/{len(inactives)})')
    sep = _sep(ascii_only)
    header_text = '   '.join([header_bits[0]] + [sep.join(header_bits[1:]).strip()])
    header_text = _truncate(header_text, inner - 4)

    out: list[str] = []
    # Top border.
    out.append(pad + chars.tl + chars.h * inner + chars.tr)
    # Header row (full-width).
    body = '  ' + _pad(header_text, inner - 2)
    out.append(pad + chars.v + body + chars.v)
    # Divider row introducing column structure.
    out.append(
        pad
        + chars.tee_left
        + chars.h * FANOUT_COL1_WIDTH
        + chars.tee_top
        + chars.h * FANOUT_COL2_WIDTH
        + chars.tee_right
    )
    # Content rows.
    skipped_collapsed = ('skipped' in hide and inactives) and all(
        t.status == 'skipped' for t in inactives
    )
    if skipped_collapsed:
        right_cells = [_collapsed_inactive_cell(len(inactives))]
        for _ in range(max(0, len(actives) - 1)):
            right_cells.append(' ' * FANOUT_COL2_WIDTH)
    else:
        right_cells = [
            _format_fanout_cell(t, FANOUT_COL2_WIDTH, ascii_only,
                                plan=plan)
            for t in inactives
        ]
    left_cells = [
        _format_fanout_cell(t, FANOUT_COL1_WIDTH, ascii_only,
                            plan=plan)
        for t in actives
    ]
    rows = max(len(left_cells), len(right_cells))
    for i in range(rows):
        left = left_cells[i] if i < len(left_cells) else ' ' * FANOUT_COL1_WIDTH
        right = right_cells[i] if i < len(right_cells) else ' ' * FANOUT_COL2_WIDTH
        out.append(pad + chars.v + left + chars.v + right + chars.v)
    # Bottom border with ╩ at centerline.
    out.append(
        pad
        + chars.bl
        + chars.h * FANOUT_COL1_WIDTH
        + chars.tee_bottom
        + chars.h * FANOUT_COL2_WIDTH
        + chars.br
    )
    return out


def _format_fanout_cell(
    t: Task, width: int, ascii_only: bool, *, plan: LoomPlan,
) -> str:
    '''Format a single task cell inside a fanout column.

    Layout: `  <glyph>  <name>[  ✦ fan-in N]<trailing pad>`
    '''
    glyph = status_glyph(t.status, ascii_only)
    fan_in_count = len(t.depends_on) if len(t.depends_on) > 5 else 0
    prefix = f'  {glyph}  '  # 5
    if fan_in_count:
        annotation = f'{_fan_in_marker(ascii_only)} {fan_in_count}'
        gap = '  '
    else:
        annotation = ''
        gap = ''
    fixed = len(prefix) + len(gap) + len(annotation)
    remaining = width - fixed
    # Reserve 1 trailing space before the divider when annotation exists,
    # so it doesn't sit flush against the column border.
    name_budget = remaining - 1 if annotation else remaining
    name = _truncate(t.id, max(1, name_budget))
    cell = prefix + name + gap + annotation
    return _pad(cell, width)


def _collapsed_inactive_cell(n: int) -> str:
    text = f'  {n} skipped — hidden'
    return _pad(text, FANOUT_COL2_WIDTH)


# ---- edges & legend ----

def _render_edge(centerline: int, ascii_only: bool) -> list[str]:
    v, arrow = edge_chars(ascii_only)
    pad = ' ' * centerline
    return [pad + v, pad + arrow]


def _legend_line(ascii_only: bool) -> str:
    items = []
    for s in ('pending', 'ready', 'running', 'done', 'failed', 'skipped'):
        g = status_glyph(s, ascii_only)
        items.append(f'{g} {s}')
    return 'Legend: ' + _sep(ascii_only).join(items)
