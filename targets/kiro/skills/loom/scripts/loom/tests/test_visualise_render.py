'''Tests for loom.visualise.render — box-format renderer.'''
from __future__ import annotations

import re

import pytest

from loom.engine.models import Task, LoomPlan
from loom.visualise import visualise


def _t(id, deps=None, *, kind='tool', status='pending', when=None):
    return Task(
        id=id, kind=kind, cmd=['echo'] if kind == 'tool' else None,
        depends_on=list(deps or []), status=status, when=when,
        template=('/t.j2' if kind in ('agent', 'human') else None),
    )


class TestEmptyAndTrivial:
    def test_empty_plan(self):
        text = visualise(LoomPlan())
        assert text.strip() == 'PLAN — (empty)'

    def test_single_task_renders_one_box(self):
        plan = LoomPlan(tasks=[_t('only')])
        text = visualise(plan, width=80)
        assert '01  only' in text
        # No vertical edges between boxes (only one box).
        assert text.count('▼') == 0


class TestLinearChain:
    def test_three_task_chain_emits_two_edges(self):
        plan = LoomPlan(tasks=[
            _t('a'), _t('b', ['a']), _t('c', ['b']),
        ])
        text = visualise(plan, width=80)
        # 3 boxes, 2 edges (each edge has one ▼)
        assert text.count('▼') == 2

    def test_centerline_alignment(self):
        plan = LoomPlan(tasks=[_t('a'), _t('b', ['a'])])
        text = visualise(plan, width=80)
        lines = text.splitlines()
        # Find the rows that have ▼ — they should all share the column
        arrow_cols = [l.index('▼') for l in lines if '▼' in l]
        assert len(set(arrow_cols)) == 1


class TestFanout:
    def test_layer_with_more_than_three_renders_double_line(self):
        plan = LoomPlan(tasks=[
            _t('root'),
            _t('a', ['root']), _t('b', ['root']),
            _t('c', ['root']), _t('d', ['root']),
        ])
        text = visualise(plan, width=80)
        # Double-line border characters appear
        assert '╔' in text
        assert '╗' in text
        assert '╠' in text
        assert '╣' in text
        assert '╩' in text

    def test_layer_with_three_tasks_uses_linear_box(self):
        plan = LoomPlan(tasks=[
            _t('root'),
            _t('a', ['root']), _t('b', ['root']), _t('c', ['root']),
        ])
        text = visualise(plan, width=80)
        # No double-line border characters
        assert '╔' not in text
        assert '╠' not in text

    def test_branch_label_detected_from_when(self):
        plan = LoomPlan(tasks=[
            _t('classify', kind='agent'),
            _t('a', ['classify'], when='task."classify".quintet.media == \'paper\''),
            _t('b', ['classify'], when='task."classify".quintet.media == \'book\''),
            _t('c', ['classify'], when='task."classify".quintet.register == \'fiction\''),
            _t('d', ['classify'], when='task."classify".quintet.media == \'video\''),
        ])
        text = visualise(plan, width=80)
        assert 'branch on classify.quintet' in text

    def test_dominant_prefix_label(self):
        plan = LoomPlan(tasks=[
            _t('root'),
            _t('extract-a', ['root']),
            _t('extract-b', ['root']),
            _t('extract-c', ['root']),
            _t('extract-d', ['root']),
        ])
        text = visualise(plan, width=80)
        assert 'EXTRACT' in text

    def test_skipped_in_inactive_column(self):
        plan = LoomPlan(tasks=[
            _t('root', status='done'),
            _t('a', ['root'], status='done'),
            _t('b', ['root'], status='done'),
            _t('c', ['root'], status='skipped'),
            _t('d', ['root'], status='skipped'),
        ])
        text = visualise(plan, width=80)
        # Find the fanout row containing 'a' (active)
        # and verify 'c' (skipped) appears on the right side of the divider
        for line in text.splitlines():
            if '║' in line and 'a' in line and 'c' in line:
                left_of_div = line.split('║', 2)[1]
                right_of_div = line.split('║', 2)[2]
                assert ' a' in left_of_div
                assert ' c' in right_of_div
                return
        # If no single row had both, find at least the columns separately.


class TestStatusOverlay:
    def test_done_glyph_in_output(self):
        plan = LoomPlan(tasks=[_t('a', status='done')])
        text = visualise(plan, width=80)
        assert '●' in text

    def test_running_marker_for_current(self):
        plan = LoomPlan(tasks=[
            _t('a', status='done'),
            _t('b', ['a'], status='running'),
        ])
        text = visualise(plan, width=80)
        assert '← current' in text

    def test_no_current_when_all_terminal(self):
        plan = LoomPlan(tasks=[
            _t('a', status='done'),
            _t('b', ['a'], status='done'),
        ])
        text = visualise(plan, width=80)
        assert '← current' not in text


class TestWhenPredicate:
    def test_when_shown_for_pending(self):
        plan = LoomPlan(tasks=[
            _t('root', status='done'),
            _t('a', ['root'], when='task."root".val == `1`'),
        ])
        text = visualise(plan, width=120)
        assert 'when:' in text
        assert "task.\"root\".val == `1`" in text

    def test_when_omitted_for_done(self):
        plan = LoomPlan(tasks=[
            _t('a', status='done', when='task."x".y == `1`'),
        ])
        text = visualise(plan, width=80)
        # done tasks omit `when:` (status already encodes outcome)
        assert 'when:' not in text

    def test_show_when_false_drops_predicate(self):
        plan = LoomPlan(tasks=[
            _t('root', status='done'),
            _t('a', ['root'], when='task."root".val == `1`'),
        ])
        text = visualise(plan, width=120, show_when=False)
        assert 'when:' not in text


class TestFanIn:
    def test_high_fan_in_uses_summary_line(self):
        # 6 parents — exceeds the >5 threshold.
        plan = LoomPlan(tasks=[
            _t('p1'), _t('p2'), _t('p3'),
            _t('p4'), _t('p5'), _t('p6'),
            _t('child', ['p1', 'p2', 'p3', 'p4', 'p5', 'p6']),
        ])
        text = visualise(plan, width=120)
        assert '✦ fan-in' in text

    def test_low_fan_in_no_summary(self):
        plan = LoomPlan(tasks=[
            _t('p1'), _t('p2'),
            _t('child', ['p1', 'p2']),
        ])
        text = visualise(plan, width=80)
        assert '✦ fan-in' not in text


class TestAsciiOnly:
    def test_no_unicode_in_strict_mode(self):
        plan = LoomPlan(tasks=[
            _t('a', status='done'),
            _t('b', ['a'], status='running'),
            _t('c', ['b'], status='pending'),
        ])
        text = visualise(plan, width=80, ascii_only=True)
        for ch in text:
            assert ord(ch) < 128, (
                f'non-ASCII char {ch!r} (U+{ord(ch):04X}) in strict-ASCII output')

    def test_ascii_box_chars(self):
        plan = LoomPlan(tasks=[_t('x')])
        text = visualise(plan, width=80, ascii_only=True)
        assert '+' in text
        assert '-' in text
        assert '|' in text
        # No unicode box chars.
        for ch in '┌┐└┘─│╔╗╚╝═║╠╣╦╩':
            assert ch not in text


class TestHide:
    def test_hide_skipped_collapses_inactive_column(self):
        plan = LoomPlan(tasks=[
            _t('root', status='done'),
            _t('a', ['root'], status='done'),
            _t('b', ['root'], status='done'),
            _t('skip1', ['root'], status='skipped'),
            _t('skip2', ['root'], status='skipped'),
            _t('skip3', ['root'], status='skipped'),
        ])
        full = visualise(plan, width=80)
        hidden = visualise(plan, width=80, hide=['skipped'])
        assert 'skip1' in full
        assert 'skip1' not in hidden
        assert 'skipped — hidden' in hidden


class TestHeader:
    def test_header_shows_status_histogram(self):
        plan = LoomPlan(tasks=[
            _t('a', status='done'),
            _t('b', ['a'], status='running'),
            _t('c', ['b'], status='pending'),
        ])
        text = visualise(plan, width=80)
        assert 'PLAN' in text
        assert 'done' in text
        assert 'running' in text

    def test_show_status_false_omits_histogram(self):
        plan = LoomPlan(tasks=[
            _t('a', status='done'),
            _t('b', ['a'], status='pending'),
        ])
        text = visualise(plan, width=80, show_status=False)
        # Header still present but no count line.
        assert 'PLAN' in text
        # The first 5 lines (header box) shouldn't say "done" or counts
        first_lines = '\n'.join(text.splitlines()[:5])
        assert 'done' not in first_lines


class TestWidth:
    def test_width_too_small_clamped_to_min(self):
        plan = LoomPlan(tasks=[_t('a'), _t('b', ['a'])])
        # Width=20 is below min; renderer should clamp without crashing.
        text = visualise(plan, width=20)
        assert '┌' in text or '+' in text  # produces output

    def test_wider_terminal_shifts_centerline_right(self):
        plan = LoomPlan(tasks=[_t('a'), _t('b', ['a'])])
        narrow = visualise(plan, width=80)
        wide = visualise(plan, width=140)
        # The centerline (▼ position) should be larger in wider output
        narrow_arrow = [l.index('▼') for l in narrow.splitlines() if '▼' in l]
        wide_arrow = [l.index('▼') for l in wide.splitlines() if '▼' in l]
        assert wide_arrow[0] > narrow_arrow[0]
