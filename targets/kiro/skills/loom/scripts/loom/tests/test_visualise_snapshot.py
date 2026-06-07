'''Snapshot test: render the curator plan fixture and compare against a
checked-in expected output.

Update protocol: delete the snapshot file(s) under tests/fixtures/ and
re-run; the test regenerates any missing snapshot, then compares on
subsequent runs.
'''
from __future__ import annotations

from pathlib import Path

import pytest

from loom.engine.models import LoomPlan
from loom.visualise import visualise


FIXTURES = Path(__file__).parent / 'fixtures'
CURATOR_PLAN = FIXTURES / 'curator-plan.yaml'
SNAPSHOT_DEFAULT = FIXTURES / 'curator-snapshot-default.txt'
SNAPSHOT_ASCII = FIXTURES / 'curator-snapshot-ascii.txt'


def _maybe_write(path: Path, text: str) -> None:
    if not path.exists():
        path.write_text(text + '\n', encoding='utf-8')


def _normalize(s: str) -> str:
    return '\n'.join(line.rstrip() for line in s.splitlines()).rstrip() + '\n'


@pytest.fixture
def plan():
    return LoomPlan.from_yaml(CURATOR_PLAN)


class TestSnapshot:
    def test_default_render(self, plan):
        text = _normalize(visualise(
            plan, workdir_basename='youtube-k1njvbbmfsw'))
        _maybe_write(SNAPSHOT_DEFAULT, text.rstrip('\n'))
        assert text == _normalize(SNAPSHOT_DEFAULT.read_text(encoding='utf-8'))

    def test_ascii_only(self, plan):
        text = _normalize(visualise(
            plan, workdir_basename='youtube-k1njvbbmfsw', ascii_only=True))
        _maybe_write(SNAPSHOT_ASCII, text.rstrip('\n'))
        assert text == _normalize(SNAPSHOT_ASCII.read_text(encoding='utf-8'))

    def test_ascii_only_is_pure_7bit(self, plan):
        text = visualise(
            plan, workdir_basename='youtube-k1njvbbmfsw', ascii_only=True)
        assert all(ord(ch) < 128 for ch in text)
