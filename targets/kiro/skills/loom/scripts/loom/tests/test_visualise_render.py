'''Tests for loom.visualise.render — renderdag rail renderer.'''
from __future__ import annotations

from loom.engine.models import Task, LoomPlan
from loom.visualise import visualise


def _t(id, all=None, any=None, *, kind='tool', when=None, latch=None):
    return Task(
        id=id, kind=kind, cmd=['echo'] if kind == 'tool' else None,
        depends_on_all=list(all or []), depends_on_any=list(any or []),
        when=when, latch=latch,
        template='/t.j2' if kind in ('agent', 'human') else None,
    )


class TestEmptyAndTrivial:
    def test_empty_plan(self):
        assert visualise(LoomPlan()).strip() == 'PLAN — (empty)'

    def test_single_task(self):
        text = visualise(LoomPlan(tasks=[_t('only')]))
        assert '01 only' in text
        assert '○' in text
        assert 'PLAN' in text
        assert '1 tasks' in text


class TestHeaderAndLegend:
    def test_header_shows_basename_and_count(self):
        plan = LoomPlan(tasks=[_t('a'), _t('b', ['a'])])
        text = visualise(plan, workdir_basename='demo-wd')
        assert 'demo-wd' in text
        assert '2 tasks' in text

    def test_legend_present(self):
        text = visualise(LoomPlan(tasks=[_t('a')]))
        assert 'legend:' in text


class TestKindGlyphs:
    def test_all_three_kinds(self):
        plan = LoomPlan(tasks=[
            _t('a', kind='tool'),
            _t('b', ['a'], kind='agent'),
            _t('c', ['b'], kind='human'),
        ])
        text = visualise(plan)
        assert '○' in text and '◆' in text and '▣' in text

    def test_latch_glyph(self):
        plan = LoomPlan(tasks=[
            _t('a'),
            _t('b', ['a'], kind='agent',
               latch={'header': 'a', 'fuel': 3}),
        ])
        text = visualise(plan)
        assert '↻' in text


class TestOrderingAndEdges:
    def test_dependents_first(self):
        plan = LoomPlan(tasks=[_t('a'), _t('b', ['a']), _t('c', ['b'])])
        text = visualise(plan)
        lines = text.splitlines()
        ia = next(i for i, l in enumerate(lines) if '01 a' in l)
        ib = next(i for i, l in enumerate(lines) if '02 b' in l)
        ic = next(i for i, l in enumerate(lines) if '03 c' in l)
        assert ic < ib < ia  # dependents above dependencies

    def test_rail_vertical_edge(self):
        plan = LoomPlan(tasks=[_t('a'), _t('b', ['a'])])
        assert '│' in visualise(plan)

    def test_depends_on_any_dotted(self):
        # build depends on either path -> dotted ancestor rail somewhere.
        plan = LoomPlan(tasks=[
            _t('x'), _t('y'),
            _t('build', all=['x'], any=['y']),
        ])
        assert '╷' in visualise(plan)


class TestAnnotations:
    def test_when_inline(self):
        plan = LoomPlan(tasks=[
            _t('root'),
            _t('a', ['root'], when='complex_count > 0'),
        ])
        text = visualise(plan)
        assert 'when: complex_count > 0' in text

    def test_loop_inline(self):
        plan = LoomPlan(tasks=[
            _t('build'),
            _t('test', ['build'], kind='agent',
               latch={'header': 'build', 'fuel': 3, 'while': '${x}'}),
        ])
        text = visualise(plan)
        assert '↻ loop → build' in text
        assert 'fuel 3' in text

    def test_no_when_flag(self):
        plan = LoomPlan(tasks=[_t('root'), _t('a', ['root'], when='v == 1')])
        assert 'when: v == 1' not in visualise(plan, show_when=False)

    def test_no_loops_flag(self):
        plan = LoomPlan(tasks=[
            _t('b'),
            _t('t', ['b'], latch={'header': 'b', 'fuel': 2}),
        ])
        assert 'loop → b' not in visualise(plan, show_loops=False)


class TestAsciiOnly:
    def test_pure_7bit(self):
        plan = LoomPlan(tasks=[
            _t('a'), _t('b', ['a'], kind='agent'),
            _t('c', all=['b'], any=['a'], kind='human'),
        ])
        text = visualise(plan, ascii_only=True)
        assert all(ord(ch) < 128 for ch in text)

    def test_ascii_has_no_unicode_box(self):
        plan = LoomPlan(tasks=[_t('a'), _t('b', ['a'])])
        text = visualise(plan, ascii_only=True)
        for ch in '○◆▣↻│╷╮╯╰├┬─':
            assert ch not in text
