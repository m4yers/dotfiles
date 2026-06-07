'''Tests for loom.visualise.glyphs (kind glyphs + inline annotations).'''
from __future__ import annotations

from loom.engine.models import Task
from loom.visualise.glyphs import annotation, node_glyph


def _t(id='t', *, kind='tool', when=None, latch=None):
    return Task(id=id, kind=kind, when=when, latch=latch,
                cmd=['echo'] if kind == 'tool' else None,
                template='/t.j2' if kind in ('agent', 'human') else None)


class TestNodeGlyph:
    def test_kind_glyphs_unicode(self):
        assert node_glyph(_t(kind='tool')) == '○'
        assert node_glyph(_t(kind='agent')) == '◆'
        assert node_glyph(_t(kind='human')) == '▣'

    def test_latch_overrides_kind(self):
        t = _t(kind='agent', latch={'header': 'x', 'fuel': 3})
        assert node_glyph(t) == '↻'

    def test_kind_glyphs_ascii(self):
        assert node_glyph(_t(kind='tool'), ascii_only=True) == 'o'
        assert node_glyph(_t(kind='agent'), ascii_only=True) == '*'
        assert node_glyph(_t(kind='human'), ascii_only=True) == '#'

    def test_latch_ascii(self):
        t = _t(latch={'header': 'x', 'fuel': 1})
        assert node_glyph(t, ascii_only=True) == '@'

    def test_glyphs_are_single_char(self):
        for k in ('tool', 'agent', 'human'):
            assert len(node_glyph(_t(kind=k))) == 1
            assert len(node_glyph(_t(kind=k), ascii_only=True)) == 1


class TestAnnotation:
    def test_empty_when_nothing_to_show(self):
        assert annotation(_t()) == ''

    def test_when_annotation(self):
        a = annotation(_t(when='complex_count > 0'))
        assert 'when: complex_count > 0' in a

    def test_loop_annotation_fuel_and_while(self):
        t = _t(latch={'header': 'build', 'fuel': 3, 'while': '${x}'})
        a = annotation(t)
        assert '↻ loop → build' in a
        assert 'fuel 3' in a
        assert 'while' in a

    def test_loop_annotation_fuel_only(self):
        t = _t(latch={'header': 'refine', 'fuel': 4})
        a = annotation(t)
        assert '↻ loop → refine' in a
        assert 'fuel 4' in a
        assert 'while' not in a

    def test_loop_and_when_combined(self):
        t = _t(latch={'header': 'h', 'fuel': 2}, when='v == 1')
        a = annotation(t)
        assert '↻ loop → h' in a
        assert 'when: v == 1' in a

    def test_show_when_false(self):
        assert annotation(_t(when='x'), show_when=False) == ''

    def test_show_loops_false(self):
        t = _t(latch={'header': 'h', 'fuel': 1})
        assert annotation(t, show_loops=False) == ''

    def test_ascii_is_7bit(self):
        t = _t(latch={'header': 'build', 'fuel': 3, 'while': '${x}'},
               when='a == b')
        a = annotation(t, ascii_only=True)
        assert all(ord(c) < 128 for c in a)
        assert 'loop -> build' in a
        assert 'when: a == b' in a
