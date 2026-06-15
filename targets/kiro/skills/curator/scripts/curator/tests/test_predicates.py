'''Deep predicate compilation and evaluation tests.'''
from __future__ import annotations

import jmespath
import pytest
import yaml

from curator import predicates
from curator.plan import QUINTET
from curator.quintet import MEDIA, FORM, REGISTER, DISCIPLINE, AUDIENCE


@pytest.fixture(scope='module')
def rules():
    return yaml.safe_load(QUINTET.read_text(encoding='utf-8'))['rules']


VOCAB = {
    'media': set(MEDIA),
    'form': set(FORM),
    'register': set(REGISTER),
    'discipline': set(DISCIPLINE),
    'audience': set(AUDIENCE),
}


def _quintet(media='article', form='blog', register='non_fiction',
             discipline='cs', audience='general'):
    return {'media': media, 'form': form, 'register': register,
            'discipline': discipline, 'audience': audience}


def _valid(kw: dict) -> bool:
    '''Check all values in kw are in their slot vocabulary.'''
    for slot, val in kw.items():
        if val not in VOCAB.get(slot, set()):
            return False
    return True


def _eval(pred, quintet):
    '''Evaluate a compiled predicate against a quintet.'''
    if pred is None:
        return True  # None means always-run
    data = {'task': {'extract-classify': {'quintet': quintet}}}
    return bool(jmespath.search(pred, data))


# ---- Parametrized trigger/skip matrix ----

CASES = [
    ('authors', {'media': 'book'}, {'media': 'article'}),
    ('abstract', {'media': 'paper'}, {'media': 'book'}),
    ('citations-paper', {'media': 'paper'}, {'media': 'book', 'audience': 'general'}),
    ('citations-academic', {'audience': 'academic'}, {'media': 'article', 'audience': 'general'}),
    ('people', {'media': 'article'}, {'media': 'book'}),
    ('topics', {'register': 'non_fiction'}, {'register': 'fiction'}),
    ('models-nonfiction', {'register': 'non_fiction'}, {'register': 'fiction', 'media': 'article'}),
    ('models-popsci', {'media': 'book', 'form': 'pop_science'}, {'register': 'fiction', 'media': 'article'}),
    ('themes-fiction', {'register': 'fiction'}, {'media': 'paper', 'form': 'research', 'register': 'non_fiction'}),
    ('themes-popsci', {'media': 'book', 'form': 'pop_science'}, {'media': 'paper', 'form': 'research', 'register': 'non_fiction'}),
    ('chapters', {'media': 'book', 'form': 'textbook'}, {'media': 'book', 'form': 'novel'}),
    ('exercises', {'media': 'book', 'form': 'textbook'}, {'media': 'book', 'form': 'novel'}),
    ('story', {'media': 'book', 'form': 'novel'}, {'media': 'book', 'form': 'textbook'}),
    ('setting', {'media': 'book', 'form': 'novel'}, {'media': 'book', 'form': 'textbook'}),
    ('contributions-monograph', {'media': 'book', 'form': 'monograph'}, {'media': 'book', 'form': 'textbook'}),
    ('contributions-research', {'media': 'paper', 'form': 'research'}, {'media': 'book', 'form': 'textbook'}),
    ('contributions-review', {'media': 'paper', 'form': 'review'}, {'media': 'book', 'form': 'textbook'}),
    ('methods', {'media': 'paper', 'form': 'research'}, {'media': 'paper', 'form': 'review'}),
    ('results', {'media': 'paper', 'form': 'research'}, {'media': 'paper', 'form': 'review'}),
    # Podcast/talk concepts now mapped to audio/video media in rules.
    ('guests-audio-interview', {'media': 'audio', 'form': 'interview'}, {'media': 'paper', 'form': 'research'}),
    ('guests-audio-roundtable', {'media': 'audio', 'form': 'roundtable'}, {'media': 'paper', 'form': 'research'}),
    ('quotes-audio-interview', {'media': 'audio', 'form': 'interview'}, {'media': 'book', 'form': 'textbook'}),
    ('quotes-news', {'media': 'article', 'form': 'news'}, {'media': 'book', 'form': 'textbook'}),
    ('key_points-lecture', {'media': 'video', 'form': 'lecture'}, {'media': 'book'}),
    ('key_points-video-keynote', {'media': 'video', 'form': 'keynote'}, {'media': 'book'}),
    ('key_points-videotalk', {'media': 'video', 'form': 'talk'}, {'media': 'book'}),
    ('speaker-video-keynote', {'media': 'video', 'form': 'keynote'}, {'media': 'video', 'form': 'lecture'}),
    ('speaker-videotalk', {'media': 'video', 'form': 'talk'}, {'media': 'video', 'form': 'lecture'}),
    ('code_examples', {'media': 'article', 'form': 'tutorial', 'discipline': 'cs'},
     {'media': 'article', 'form': 'tutorial', 'discipline': 'physics'}),
]


@pytest.mark.parametrize('case_id,trigger_kw,skip_kw', CASES, ids=[c[0] for c in CASES])
def test_predicate_trigger_and_skip(rules, case_id, trigger_kw, skip_kw):
    # Skip if quintet uses values not in vocabulary
    if not _valid(trigger_kw) or not _valid(skip_kw):
        pytest.skip(f'quintet uses value not in slot vocabulary')

    kind = case_id.split('-')[0] if '-' in case_id else case_id
    # Handle multi-word kinds like key_points, code_examples
    for k in ('key_points', 'code_examples', 'pop_science'):
        if case_id.startswith(k):
            kind = k
            break

    pred = predicates.compile(kind, rules)
    assert _eval(pred, _quintet(**trigger_kw)), \
        f'{kind} should trigger on {trigger_kw}'
    assert not _eval(pred, _quintet(**skip_kw)), \
        f'{kind} should skip on {skip_kw}'


# ---- Base extractors always run ----

@pytest.mark.parametrize('kind', ['summary', 'keywords'])
def test_base_extractors_always_run(rules, kind):
    pred = predicates.compile(kind, rules)
    assert pred is None


# ---- Edge cases ----

def test_nonexistent_kind_returns_false(rules):
    assert predicates.compile('nonexistent_kind', rules) == 'false'


def test_empty_rules_returns_false():
    assert predicates.compile('anything', []) == 'false'


# ---- Compound clauses (||) ----

@pytest.mark.parametrize('kind', ['models', 'citations', 'themes',
                                   'quotes', 'key_points'])
def test_compound_clauses_have_or(rules, kind):
    pred = predicates.compile(kind, rules)
    assert pred is not None
    assert '||' in pred
