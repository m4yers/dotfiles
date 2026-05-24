'''Tests for plan derivation: discovery, predicates, plan construction.'''
from pathlib import Path

import yaml
import pytest

from curator import discovery, predicates
from curator.plan import derive_plan, TEMPLATES, QUINTET
from loom.validate import validate_plan


@pytest.fixture
def rules():
    return yaml.safe_load(QUINTET.read_text(encoding='utf-8'))['rules']


class TestDiscovery:
    def test_returns_expected_kinds(self):
        kinds = discovery.list_extractor_kinds(TEMPLATES)
        # Must include these core kinds
        for k in ('summary', 'keywords', 'authors', 'citations',
                  'classify', 'synthesis', 'models', 'themes'):
            assert k in kinds
        # Must not include _meta
        assert '_meta' not in kinds

    def test_all_have_both_templates(self):
        kinds = discovery.list_extractor_kinds(TEMPLATES)
        for k in kinds:
            d = TEMPLATES / 'extractors' / k
            assert (d / 'extractor.j2').exists()
            assert (d / 'judge.j2').exists()


class TestPredicates:
    def test_summary_always_runs(self, rules):
        assert predicates.compile('summary', rules) is None

    def test_keywords_always_runs(self, rules):
        assert predicates.compile('keywords', rules) is None

    def test_authors_mentions_book_and_paper(self, rules):
        pred = predicates.compile('authors', rules)
        assert pred is not None
        assert 'book' in pred
        assert 'paper' in pred

    def test_models_mentions_non_fiction_and_pop_science(self, rules):
        pred = predicates.compile('models', rules)
        assert pred is not None
        assert 'non_fiction' in pred
        assert 'pop_science' in pred

    def test_unknown_kind_returns_false(self, rules):
        assert predicates.compile('nonexistent_kind_xyz', rules) == 'false'


class TestDerivePlan:
    @pytest.fixture
    def plan(self, tmp_path):
        return derive_plan(tmp_path, 'fake://url')

    def test_returns_loom_plan(self, plan):
        from loom import LoomPlan
        assert isinstance(plan, LoomPlan)

    def test_task_count(self, plan):
        assert len(plan.tasks) == 58

    def test_unique_ids(self, plan):
        ids = [t.id for t in plan.tasks]
        assert len(ids) == len(set(ids))

    def test_no_orphan_judges(self, plan):
        '''Every judge task has at least one downstream consumer.'''
        judge_ids = {t.id for t in plan.tasks if t.id.startswith('judge-')}
        consumed = set()
        for t in plan.tasks:
            for dep in t.depends_on:
                if dep in judge_ids:
                    consumed.add(dep)
        orphans = judge_ids - consumed
        # judge-synthesis is consumed by prune-replica
        # judge-classify is consumed by build-replica
        assert not orphans, f'orphan judges: {orphans}'

    def test_validate_plan_passes(self, plan):
        validate_plan(plan)
