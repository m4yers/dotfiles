'''Tests for loom.visualise.glyphs.'''
from __future__ import annotations

import pytest

from loom.visualise.glyphs import (
    SINGLE, DOUBLE, ASCII_BOX,
    box_chars, edge_chars, kind_tag, status_glyph,
)


class TestStatusGlyph:
    def test_unicode_distinct(self):
        statuses = ['pending', 'ready', 'running',
                    'done', 'failed', 'skipped']
        glyphs = [status_glyph(s) for s in statuses]
        assert len(set(glyphs)) == len(statuses)

    def test_ascii_distinct(self):
        statuses = ['pending', 'ready', 'running',
                    'done', 'failed', 'skipped']
        glyphs = [status_glyph(s, ascii_only=True) for s in statuses]
        assert len(set(glyphs)) == len(statuses)

    def test_unknown_status(self):
        assert status_glyph('mystery') == '?'
        assert status_glyph('mystery', ascii_only=True) == '?'

    def test_ascii_glyphs_are_7bit(self):
        for s in ['pending', 'ready', 'running',
                  'done', 'failed', 'skipped']:
            g = status_glyph(s, ascii_only=True)
            assert ord(g) < 128


class TestKindTag:
    def test_known_tags_seven_chars(self):
        for k in ('tool', 'agent', 'human'):
            tag = kind_tag(k)
            assert len(tag) == 7
            assert tag.startswith('[') and tag.endswith(']')

    def test_unknown_kind(self):
        assert kind_tag('weird') == '[?    ]'
        assert len(kind_tag('weird')) == 7


class TestBoxChars:
    def test_single_unicode_set(self):
        c = box_chars('single')
        assert c.tl == '┌'
        assert c.tr == '┐'
        assert c.h == '─'

    def test_double_unicode_set(self):
        c = box_chars('double')
        assert c.tl == '╔'
        assert c.h == '═'
        assert c.tee_top == '╦'
        assert c.tee_bottom == '╩'

    def test_ascii_mode_single_set(self):
        c = box_chars('single', ascii_only=True)
        assert c.tl == '+'
        assert c.h == '-'
        assert c.v == '|'

    def test_ascii_mode_double_set_same_as_single(self):
        c1 = box_chars('single', ascii_only=True)
        c2 = box_chars('double', ascii_only=True)
        assert c1 == c2

    def test_unknown_weight_raises(self):
        with pytest.raises(ValueError):
            box_chars('triple')

    def test_all_ascii_chars_are_7bit(self):
        c = box_chars('single', ascii_only=True)
        for ch in (c.tl, c.tr, c.bl, c.br, c.h, c.v,
                   c.tee_top, c.tee_bottom, c.tee_left, c.tee_right):
            assert ord(ch) < 128


class TestEdgeChars:
    def test_unicode_edges(self):
        v, a = edge_chars()
        assert v == '│'
        assert a == '▼'

    def test_ascii_edges(self):
        v, a = edge_chars(ascii_only=True)
        assert v == '|'
        assert a == 'v'
        assert ord(v) < 128
        assert ord(a) < 128
