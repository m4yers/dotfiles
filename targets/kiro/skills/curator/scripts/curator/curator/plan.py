'''Derive the loom plan for a curator ingest run.

The plan is data-driven:
  - Extractor kinds discovered from templates/extractors/ (discovery.py)
  - Predicates compiled from quintet.yaml rules (predicates.py)
  - Pipeline scaffold is fixed

Result: a single static loom plan declared at ingest time.
'''
from __future__ import annotations

from pathlib import Path

import yaml
from loom import LoomPlan, tool, agent, human, make_plan

from curator import discovery, predicates
from curator.vault.config import VAULT_ROOT


SKILL_ROOT = Path(__file__).resolve().parents[3]  # curator/
TEMPLATES  = SKILL_ROOT / 'templates'
SCHEMAS    = SKILL_ROOT / 'schemas'
SCRIPTS    = SKILL_ROOT / 'scripts'
CURATOR_SH = SCRIPTS / 'curator.sh'
SECURITY_SCAN_SH = Path(__file__).resolve().parents[4] / 'secure-llm' / 'scripts' / 'security-scan.sh'
SECURE_LLM_TEMPLATES = Path(__file__).resolve().parents[4] / 'secure-llm' / 'templates'
LOOM_SH = Path(__file__).resolve().parents[4] / 'loom' / 'scripts' / 'loom.sh'
QUINTET    = SKILL_ROOT / 'scripts' / 'curator' / 'curator' / 'quintet.yaml'

# Kinds whose extractor outputs are reconciled against existing
# vault pages. Each matchable kind that participates in a run also
# gets a merge-<kind> agent task between vault-match and
# build-replica. Keep in sync with vault.match._KIND_TO_FOLDER.
_MATCHABLE_KINDS = ('keywords', 'people', 'models')

_SEARCH_PATHS = [
    str(TEMPLATES),
    str(TEMPLATES / 'extractors' / '_meta'),
    str(SECURE_LLM_TEMPLATES),
    str(QUINTET.parent.parent),
]


def _load_destinations() -> dict:
    data = yaml.safe_load(QUINTET.read_text(encoding='utf-8'))
    return data.get('destinations', {})


# Read once. Synthesis tasks need this dict; no other template does.
# Injecting it into every task's vars would duplicate ~50 lines per task
# in plan.yaml; the synthesis tasks pull it explicitly instead.
_DESTINATIONS = _load_destinations()


_VARS = {
    'quintet_path':        str(QUINTET),
    'wiki_template_path':  str(TEMPLATES / 'vault' / 'wiki.j2'),
    'vault_templates_dir': str(TEMPLATES / 'vault'),
    'replica_root':        '${global:vault-replica}',
    'loom_sh':             str(LOOM_SH),
}


def _ensure_classify_schema() -> None:
    """Regenerate schemas/extractors/classify.yaml from quintet.yaml.

    Keeps the classify task's output_schema enum in sync with the
    slot vocabularies. Called from derive_plan so loom validates
    against the current vocabulary on every ingest.
    """
    rules_doc = yaml.safe_load(QUINTET.read_text())
    slots = rules_doc['slots']
    schema = {
        'type': 'object',
        'required': ['quintet'],
        'properties': {
            'quintet': {
                'type': 'object',
                'required': sorted(slots.keys()),
                'properties': {
                    slot: {'type': 'string',
                           'enum': sorted(info['values'].keys())}
                    for slot, info in slots.items()
                },
            },
        },
    }
    out = SCHEMAS / 'extractors' / 'classify.yaml'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(schema, sort_keys=False))


def derive_plan(workdir: Path, source_url: str) -> LoomPlan:
    '''Build the full loom plan for an ingest run.'''
    kinds = discovery.list_extractor_kinds(TEMPLATES)
    rules = _load_rules()
    preds = {k: predicates.compile(k, rules) for k in kinds}
    parallel = [k for k in kinds if k not in ('summary', 'classify', 'synthesis')]

    tasks = []
    tasks += _pipeline_head(source_url)
    tasks += _extractors(parallel, preds)
    tasks += _summary_extractor(parallel)
    tasks += _pipeline_tail(parallel)

    return make_plan(*tasks)


def _load_rules() -> list[dict]:
    return yaml.safe_load(QUINTET.read_text(encoding='utf-8'))['rules']


def _schema_pipeline(name: str) -> str:
    return str(SCHEMAS / 'pipeline' / f'{name}.yaml')


def _schema_extractor(kind: str) -> str:
    return str(SCHEMAS / 'extractors' / f'{kind}.yaml')


PROMPTS    = TEMPLATES / 'prompts'

def _template(kind: str, judge: bool = False) -> str:
    """Resolve the prompt template path for an extractor task.

    All per-task prompts live in ``templates/prompts/<task-id>.md.j2``
    (symlinks to the ``extractors/<kind>/{extractor,judge}.j2``
    sources). plan.py routes through the prompts dir so the
    task-id ↔ prompt mapping is discoverable via ``ls``.
    """
    prefix = 'judge' if judge else 'extract'
    return str(PROMPTS / f'{prefix}-{kind}.md.j2')


def _pipeline_head(source_url: str) -> list:
    return [
        tool('source-fetch',
             cmd=[str(CURATOR_SH), 'source', 'fetch', source_url],
             output_schema=_schema_pipeline('source-fetch')),
        tool('source-convert',
             cmd=[str(CURATOR_SH), 'source', 'convert',
                  '${task:source-fetch:path}',
                  '--task-workdir', '${task_workdir}'],
             depends_on=['source-fetch'],
             output_schema=_schema_pipeline('source-convert')),
        tool('security-scan',
             cmd=[str(SECURITY_SCAN_SH),
                  '${task:source-convert:converted_path}'],
             depends_on=['source-convert'],
             output_schema=_schema_pipeline('security-scan')),
        agent('extract-classify',
              template=_template('classify'),
              depends_on=['source-convert', 'security-scan'],
              output_schema=_schema_extractor('classify'),
              vars={**_VARS, 'kind_name': 'classify'},
              template_search_paths=_SEARCH_PATHS),
        agent('judge-classify',
              template=_template('classify', judge=True),
              depends_on=['extract-classify'],
              output_schema=_schema_pipeline('judge-verdict'),
              vars={**_VARS, 'kind_name': 'classify'},
              template_search_paths=_SEARCH_PATHS),
    ]


def _extractors(parallel: list[str], preds: dict[str, str | None]) -> list:
    out = []
    for kind in parallel:
        extract_id = f'extract-{kind}'
        kw: dict = {
            'template': _template(kind),
            'depends_on': ['extract-classify', 'source-convert'],
            'output_schema': _schema_extractor(kind),
            'vars': {**_VARS, 'kind_name': kind},
            'template_search_paths': _SEARCH_PATHS,
        }
        if preds[kind] is not None:
            kw['when'] = preds[kind]
        out.append(agent(extract_id, **kw))
        # Judge inherits via cascade: if extract-X is skipped, judge-X is
        # auto-skipped because its only dep is skipped.
        out.append(agent(f'judge-{kind}',
                         template=_template(kind, judge=True),
                         depends_on=[extract_id],
                         output_schema=_schema_pipeline('judge-verdict'),
                         vars={**_VARS, 'kind_name': kind},
                         template_search_paths=_SEARCH_PATHS))
    return out


def _summary_extractor(parallel: list[str]) -> list:
    # Summary needs classify+convert (always present) AND at
    # least one extract output to summarise. Under loom's
    # done-only semantics, listing every extract in
    # depends_on_all would cascade-skip summary whenever a kind
    # was when-skipped (the common case). Use depends_on_any so
    # summary fires as soon as any extract finishes.
    return [
        agent('extract-summary',
              template=_template('summary'),
              depends_on_all=['extract-classify', 'source-convert'],
              depends_on_any=[f'extract-{k}' for k in parallel],
              output_schema=_schema_extractor('summary'),
              vars={**_VARS, 'kind_name': 'summary'},
              template_search_paths=_SEARCH_PATHS),
        agent('judge-summary',
              template=_template('summary', judge=True),
              depends_on=['extract-summary'],
              output_schema=_schema_pipeline('judge-verdict'),
              vars={**_VARS, 'kind_name': 'summary'},
              template_search_paths=_SEARCH_PATHS),
    ]


def _merge_tasks(matchable: list[str]) -> list:
    """One ``merge-<kind>`` agent per matchable kind that ran.

    Each task reconciles this run's extractor output for that kind
    against existing vault pages whose stems matched in
    vault-match. Output is consumed by build-replica, which
    prefers ``merged_item`` over the raw extractor item when both
    exist. Cascade-skipped via ``judge-<kind>`` when its extractor
    was skipped; ``when:`` predicate skips it when no items
    matched the vault.
    """
    out = []
    for kind in matchable:
        merge_id = f'merge-{kind}'
        # JMESPath predicate: skip if the kind has zero matches.
        # The ``|| `[]```` guard handles the case where vault-match
        # did not include this kind at all (e.g. extractor was
        # skipped via its own when-predicate before vault-match
        # ran). In that case the projection result is null;
        # ``null || `[]```` collapses to an empty list and
        # ``length([]) > 0`` is false, so merge is skipped.
        when = (
            f'length(task."vault-match"."{kind}"[?match != `null`] '
            f'|| `[]`) > `0`'
        )
        out.append(agent(
            merge_id,
            template=str(PROMPTS / f'merge-{kind}.md.j2'),
            depends_on=[f'judge-{kind}', 'vault-match'],
            when=when,
            output_schema=_schema_pipeline('merge'),
            vars={**_VARS, 'kind_name': kind,
                  'vault_root': str(VAULT_ROOT)},
            template_search_paths=_SEARCH_PATHS,
        ))
    return out


def _pipeline_tail(parallel: list[str]) -> list:
    matchable = [k for k in _MATCHABLE_KINDS if k in parallel]
    match_args = [str(CURATOR_SH), 'vault', 'match']
    for k in matchable:
        match_args += [f'--{k}', f'${{task_path:extract-{k}}}']

    all_judges = ([f'judge-{k}' for k in parallel]
                  + ['judge-summary', 'judge-classify'])

    merge_ids = [f'merge-{k}' for k in matchable]

    return [
        tool('vault-match',
             cmd=match_args,
             depends_on=[f'judge-{k}' for k in matchable],
             output_schema=_schema_pipeline('vault-match')),
        *_merge_tasks(matchable),
        tool('build-replica',
             cmd=[str(CURATOR_SH), 'vault', 'replica', 'build', '${workdir}'],
             depends_on_any=all_judges + ['vault-match'] + merge_ids,
             output_schema=_schema_pipeline('build-replica')),
        agent('extract-synthesis',
              template=str(PROMPTS / 'extract-synthesis.md.j2'),
              depends_on=['build-replica'],
              output_schema=_schema_extractor('synthesis'),
              vars={**_VARS, 'kind_name': 'synthesis',
                    'destinations': _DESTINATIONS,
                    'vault_root': str(VAULT_ROOT)},
              template_search_paths=_SEARCH_PATHS),
        agent('judge-synthesis',
              template=str(PROMPTS / 'judge-synthesis.md.j2'),
              depends_on=['extract-synthesis'],
              output_schema=_schema_pipeline('judge-verdict'),
              vars={**_VARS, 'kind_name': 'synthesis',
                    'destinations': _DESTINATIONS,
                    'vault_root': str(VAULT_ROOT)},
              template_search_paths=_SEARCH_PATHS),
        tool('prune-replica',
             cmd=[str(CURATOR_SH), 'vault', 'replica', 'prune', '${workdir}'],
             depends_on=['judge-synthesis'],
             output_schema=_schema_pipeline('prune-replica')),
        tool('vault-report',
             cmd=[str(CURATOR_SH), 'vault', 'report', '${workdir}'],
             depends_on=['prune-replica'],
             output_schema=_schema_pipeline('vault-report')),
        human('vault-gate',
              template=str(PROMPTS / 'vault-gate.md.j2'),
              template_search_paths=_SEARCH_PATHS,
              depends_on=['vault-report'],
              output_schema=_schema_pipeline('vault-gate'),
              vars=_VARS),
        tool('strip-dead-links',
             cmd=[str(CURATOR_SH), 'vault', 'replica', 'strip-dead-links', '${workdir}'],
             depends_on=['vault-gate'],
             when='task."vault-gate".proceed == `true`',
             output_schema=_schema_pipeline('strip-dead-links')),
        tool('apply-replica',
             cmd=[str(CURATOR_SH), 'vault', 'replica', 'apply', '${workdir}'],
             depends_on=['strip-dead-links'],
             when='task."vault-gate".proceed == `true`',
             output_schema=_schema_pipeline('apply-replica')),
    ]
