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


SKILL_ROOT = Path(__file__).resolve().parents[3]  # loom-curator/
TEMPLATES  = SKILL_ROOT / 'templates'
SCHEMAS    = SKILL_ROOT / 'schemas'
SCRIPTS    = SKILL_ROOT / 'scripts'
CURATOR_SH = SCRIPTS / 'curator.sh'
SECURITY_SCAN_SH = Path(__file__).resolve().parents[5] / 'secure-llm' / 'scripts' / 'security-scan.sh'
QUINTET    = SKILL_ROOT / 'scripts' / 'curator' / 'curator' / 'quintet.yaml'

_SEARCH_PATHS = [str(TEMPLATES), str(TEMPLATES / 'extractors' / '_meta'), str(QUINTET.parent.parent)]


def _load_destinations() -> dict:
    data = yaml.safe_load(QUINTET.read_text(encoding='utf-8'))
    return data.get('destinations', {})


_VARS = {
    'quintet_path':        str(QUINTET),
    'wiki_template_path':  str(TEMPLATES / 'vault' / 'wiki.j2'),
    'vault_templates_dir': str(TEMPLATES / 'vault'),
    'destinations':        _load_destinations(),
    'replica_root':        '${global:vault-replica}',
}


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


def _template(kind: str, judge: bool = False) -> str:
    return str(TEMPLATES / 'extractors' / kind / ('judge.j2' if judge else 'extractor.j2'))


def _pipeline_head(source_url: str) -> list:
    return [
        tool('fetch',
             cmd=[str(CURATOR_SH), 'source', 'fetch', source_url],
             output_schema=_schema_pipeline('fetch')),
        tool('convert',
             cmd=[str(CURATOR_SH), 'source', 'convert',
                  '${task:fetch:path}',
                  '--task-workdir', '${task_workdir}'],
             depends_on=['fetch'],
             output_schema=_schema_pipeline('convert')),
        tool('security_scan',
             cmd=[str(SECURITY_SCAN_SH),
                  '${task:convert:converted_path}'],
             depends_on=['convert'],
             output_schema=_schema_pipeline('security_scan')),
        agent('classify',
              template=_template('classify'),
              depends_on=['convert', 'security_scan'],
              output_schema=_schema_extractor('classify'),
              vars={**_VARS, 'kind_name': 'classify'},
              template_search_paths=_SEARCH_PATHS),
        agent('judge-classify',
              template=_template('classify', judge=True),
              depends_on=['classify'],
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
            'depends_on': ['classify', 'convert'],
            'output_schema': _schema_extractor(kind),
            'vars': {**_VARS, 'kind_name': kind},
            'template_search_paths': _SEARCH_PATHS,
        }
        if preds[kind] is not None:
            kw['when'] = preds[kind]
        out.append(agent(extract_id, **kw))
        out.append(agent(f'judge-{kind}',
                         template=_template(kind, judge=True),
                         depends_on=[extract_id],
                         output_schema=_schema_pipeline('judge-verdict'),
                         vars={**_VARS, 'kind_name': kind},
                         template_search_paths=_SEARCH_PATHS))
    return out


def _summary_extractor(parallel: list[str]) -> list:
    deps = ['classify', 'convert'] + [f'extract-{k}' for k in parallel]
    return [
        agent('extract-summary',
              template=_template('summary'),
              depends_on=deps,
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


def _pipeline_tail(parallel: list[str]) -> list:
    matchable = [k for k in ('keywords', 'people', 'models') if k in parallel]
    match_args = [str(CURATOR_SH), 'vault', 'match']
    for k in matchable:
        match_args += [f'--{k}', f'${{task_path:extract-{k}}}']

    all_judges = ([f'judge-{k}' for k in parallel]
                  + ['judge-summary', 'judge-classify'])

    return [
        tool('vault-match',
             cmd=match_args,
             depends_on=[f'judge-{k}' for k in matchable],
             output_schema=_schema_pipeline('vault-match')),
        tool('build-replica',
             cmd=[str(CURATOR_SH), 'vault', 'replica', 'build', '${workdir}'],
             depends_on=all_judges + ['vault-match'],
             output_schema=_schema_pipeline('build-replica')),
        agent('synthesis',
              template=str(TEMPLATES / 'extractors' / 'synthesis' / 'extractor.j2'),
              depends_on=['build-replica'],
              output_schema=_schema_pipeline('build-replica'),
              vars={**_VARS, 'kind_name': 'synthesis'},
              template_search_paths=_SEARCH_PATHS),
        agent('judge-synthesis',
              template=str(TEMPLATES / 'extractors' / 'synthesis' / 'judge.j2'),
              depends_on=['synthesis'],
              output_schema=_schema_pipeline('judge-verdict'),
              vars={**_VARS, 'kind_name': 'synthesis'},
              template_search_paths=_SEARCH_PATHS),
        tool('prune-replica',
             cmd=[str(CURATOR_SH), 'vault', 'replica', 'prune', '${workdir}'],
             depends_on=['judge-synthesis'],
             output_schema=_schema_pipeline('prune-replica')),
        tool('report',
             cmd=[str(CURATOR_SH), 'vault', 'report', '${workdir}'],
             depends_on=['prune-replica'],
             output_schema=_schema_pipeline('report')),
        human('gate',
              depends_on=['report'],
              output_schema=_schema_pipeline('gate')),
        tool('strip-dead-links',
             cmd=[str(CURATOR_SH), 'vault', 'replica', 'strip-dead-links', '${workdir}'],
             depends_on=['gate'],
             when='task."gate".proceed == `true`',
             output_schema=_schema_pipeline('strip-dead-links')),
        tool('apply-replica',
             cmd=[str(CURATOR_SH), 'vault', 'replica', 'apply', '${workdir}'],
             depends_on=['strip-dead-links'],
             when='task."gate".proceed == `true`',
             output_schema=_schema_pipeline('apply-replica')),
    ]
