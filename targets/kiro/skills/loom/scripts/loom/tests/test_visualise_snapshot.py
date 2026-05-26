'''Snapshot test: visualise the curator plan fixture and compare against
a checked-in expected output.

Update protocol: when the renderer changes intentionally, run

    pytest tests/test_visualise_snapshot.py --snapshot-update

…or manually delete the snapshot file and let the test regenerate it.
'''
from __future__ import annotations

from pathlib import Path

import pytest

from loom.engine.models import LoomPlan
from loom.visualise import visualise


FIXTURES = Path(__file__).parent / 'fixtures'
CURATOR_PLAN = FIXTURES / 'curator-plan.yaml'
SNAPSHOT_DEFAULT = FIXTURES / 'curator-snapshot-default.txt'
SNAPSHOT_HIDE_SKIPPED = FIXTURES / 'curator-snapshot-hide-skipped.txt'
SNAPSHOT_ASCII = FIXTURES / 'curator-snapshot-ascii.txt'


def _maybe_write(path: Path, text: str) -> None:
    '''When snapshot doesn't exist, write it. Otherwise, do nothing.

    The first run after fixture changes will create the snapshot;
    subsequent runs compare.
    '''
    if not path.exists():
        path.write_text(text + '\n', encoding='utf-8')


def _normalize(s: str) -> str:
    # Trailing whitespace can drift; ignore.
    return '\n'.join(line.rstrip() for line in s.splitlines()).rstrip() + '\n'


@pytest.fixture
def plan():
    return LoomPlan.from_yaml(CURATOR_PLAN)


class TestSnapshot:
    def test_default_render(self, plan):
        text = visualise(
            plan, width=100,
            workdir_basename='youtube-k1njvbbmfsw',
        )
        text = _normalize(text)
        _maybe_write(SNAPSHOT_DEFAULT, text.rstrip('\n'))
        expected = SNAPSHOT_DEFAULT.read_text(encoding='utf-8')
        assert text == _normalize(expected)

    def test_hide_skipped(self, plan):
        text = visualise(
            plan, width=100,
            workdir_basename='youtube-k1njvbbmfsw',
            hide=['skipped'],
        )
        text = _normalize(text)
        _maybe_write(SNAPSHOT_HIDE_SKIPPED, text.rstrip('\n'))
        expected = SNAPSHOT_HIDE_SKIPPED.read_text(encoding='utf-8')
        assert text == _normalize(expected)

    def test_ascii_only(self, plan):
        text = visualise(
            plan, width=100,
            workdir_basename='youtube-k1njvbbmfsw',
            ascii_only=True,
        )
        text = _normalize(text)
        _maybe_write(SNAPSHOT_ASCII, text.rstrip('\n'))
        expected = SNAPSHOT_ASCII.read_text(encoding='utf-8')
        assert text == _normalize(expected)

    def test_ascii_only_is_pure_7bit(self, plan):
        text = visualise(
            plan, width=100,
            workdir_basename='youtube-k1njvbbmfsw',
            ascii_only=True,
        )
        for ch in text:
            assert ord(ch) < 128
