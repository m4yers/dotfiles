'''Glyph and box-drawing character tables.

Two modes:
  - unicode (default): pretty status glyphs and box-drawing chars
  - ascii_only: strict 7-bit fallback for logs / plaintext export

Tables here are the only place glyph choices live; the renderer never
hardcodes a character.
'''
from __future__ import annotations

from dataclasses import dataclass

# Status glyphs.
STATUS_GLYPHS_UNICODE = {
    'pending': '◇',
    'ready':   '▶',
    'running': '◐',
    'done':    '●',
    'failed':  '✗',
    'skipped': '⊘',
}

STATUS_GLYPHS_ASCII = {
    'pending': 'o',
    'ready':   '>',
    'running': '*',
    'done':    '+',
    'failed':  'x',
    'skipped': '-',
}

UNKNOWN_GLYPH_UNICODE = '?'
UNKNOWN_GLYPH_ASCII = '?'

# Kind tags. Always 7 chars wide, left-aligned, square-bracketed.
KIND_TAGS = {
    'tool':  '[tool ]',
    'agent': '[agent]',
    'human': '[human]',
}
UNKNOWN_KIND_TAG = '[?    ]'


@dataclass(frozen=True)
class BoxChars:
    '''Box-drawing character set for a single weight (single, double, ascii).'''
    tl: str   # top-left corner
    tr: str   # top-right corner
    bl: str   # bottom-left corner
    br: str   # bottom-right corner
    h:  str   # horizontal
    v:  str   # vertical
    # Tees — used by fan-out group's column divider.
    tee_top:    str   # top tee (vertical drops down)
    tee_bottom: str   # bottom tee (vertical comes up)
    tee_left:   str   # left tee (horizontal extends right)
    tee_right:  str   # right tee (horizontal extends left)


SINGLE = BoxChars(
    tl='┌', tr='┐', bl='└', br='┘', h='─', v='│',
    tee_top='┬', tee_bottom='┴', tee_left='├', tee_right='┤',
)

DOUBLE = BoxChars(
    tl='╔', tr='╗', bl='╚', br='╝', h='═', v='║',
    tee_top='╦', tee_bottom='╩', tee_left='╠', tee_right='╣',
)

# ASCII fallback uses a single set of characters for both weights;
# differentiation between "weight" is impossible without unicode.
ASCII_BOX = BoxChars(
    tl='+', tr='+', bl='+', br='+', h='-', v='|',
    tee_top='+', tee_bottom='+', tee_left='+', tee_right='+',
)

# Edge glyphs between boxes.
EDGE_VERTICAL_UNICODE = '│'
EDGE_ARROW_UNICODE = '▼'
EDGE_VERTICAL_ASCII = '|'
EDGE_ARROW_ASCII = 'v'


def status_glyph(status: str, ascii_only: bool = False) -> str:
    table = STATUS_GLYPHS_ASCII if ascii_only else STATUS_GLYPHS_UNICODE
    unknown = UNKNOWN_GLYPH_ASCII if ascii_only else UNKNOWN_GLYPH_UNICODE
    return table.get(status, unknown)


def kind_tag(kind: str) -> str:
    return KIND_TAGS.get(kind, UNKNOWN_KIND_TAG)


def box_chars(weight: str, ascii_only: bool = False) -> BoxChars:
    '''Return BoxChars for the given weight: 'single' or 'double'.

    In ascii_only mode the weight is ignored and ASCII_BOX is returned
    for both — there's no way to differentiate weights in 7-bit ASCII.
    '''
    if ascii_only:
        return ASCII_BOX
    if weight == 'single':
        return SINGLE
    if weight == 'double':
        return DOUBLE
    raise ValueError(f'unknown box weight: {weight!r}')


def edge_chars(ascii_only: bool = False) -> tuple[str, str]:
    '''Return (vertical, arrowhead) glyphs for inter-box edges.'''
    if ascii_only:
        return EDGE_VERTICAL_ASCII, EDGE_ARROW_ASCII
    return EDGE_VERTICAL_UNICODE, EDGE_ARROW_UNICODE
