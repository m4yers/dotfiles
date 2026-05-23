'''E2E: tool + 2 agent A-or-B with when: predicates.'''
import json
import pytest

import loom
from loom.plan import tool, agent, make_plan
from tests.helpers import write_schema, write_template


def test_a_or_b_predicates(tmp_path):
    '''Tool classifies, then exactly one of two agents runs (other skipped).'''
    s_classify = write_schema(tmp_path / 'classify.yaml', {
        'type': 'object',
        'properties': {'form': {'type': 'string'}},
        'required': ['form'],
    })
    s_extract = write_schema(tmp_path / 'extract.yaml', {
        'type': 'object',
        'properties': {'content': {'type': 'string'}},
        'required': ['content'],
    })
    tpl_paper = write_template(tmp_path / 'paper.j2',
                               'Extract paper: {{ upstream.classify.output.form }}')
    tpl_video = write_template(tmp_path / 'video.j2',
                               'Extract video: {{ upstream.classify.output.form }}')

    plan = make_plan(
        tool('classify',
             cmd=['python', '-c', 'import json; print(json.dumps({"form": "paper"}))'],
             output_schema=s_classify),
        agent('extract-paper',
              template=tpl_paper, output_schema=s_extract,
              depends_on=['classify'],
              when="task.classify.form == 'paper'"),
        agent('extract-video',
              template=tpl_video, output_schema=s_extract,
              depends_on=['classify'],
              when="task.classify.form == 'video'"),
    )

    wd = tmp_path / 'wd'
    rt = loom.init(workdir=wd, plan=plan)

    # First next(): runs classify inline, then yields the agent that passes predicate
    spec = rt.next()
    assert spec is not None

    # Only extract-paper should be yielded (paper predicate true)
    yielded_ids = [t['id'] for t in spec.tasks]
    assert 'extract-paper' in yielded_ids
    assert 'extract-video' not in yielded_ids

    # Verify extract-video was skipped
    p = rt.plan()
    assert p.get('extract-video').status == 'skipped'
    assert '_skip_reason' in p.get('extract-video').metadata

    # Complete the agent task
    rt.commit_running(['extract-paper'])
    rt.complete('extract-paper', output={'content': 'paper content'})

    assert rt.is_done()

    # Final state
    p = rt.plan()
    assert p.get('classify').status == 'done'
    assert p.get('extract-paper').status == 'done'
    assert p.get('extract-video').status == 'skipped'

    # Verify prompt was rendered
    td = rt.task_dir('extract-paper')
    assert (td / 'prompt.md').exists()
    prompt = (td / 'prompt.md').read_text()
    assert 'paper' in prompt
