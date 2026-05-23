'''E2E: init -> done -> extend -> done.'''
import json
import pytest

import loom
from loom.plan import tool, agent, make_plan
from tests.helpers import write_schema, write_template


def test_extend_after_completion(tmp_path):
    '''Init with one tool, complete it, extend with agent, complete that.'''
    s = write_schema(tmp_path / 's.yaml', {
        'type': 'object',
        'properties': {'val': {'type': 'integer'}},
        'required': ['val'],
    })
    tpl = write_template(tmp_path / 't.j2',
                         'upstream val={{ upstream.t1.output.val }}')

    # Phase 1: init with single tool
    plan1 = make_plan(
        tool('t1', cmd=['python', '-c', 'import json; print(json.dumps({"val": 7}))'],
             output_schema=s),
    )
    wd = tmp_path / 'wd'
    rt = loom.init(workdir=wd, plan=plan1)

    # Run tool to completion
    rt.next()
    assert rt.plan().get('t1').status == 'done'
    assert rt.task_output('t1') == {'val': 7}

    # Phase 2: extend with agent that depends on t1
    plan2 = make_plan(
        agent('a1', template=tpl, output_schema=s, depends_on=['t1']),
    )
    loom.extend(rt, plan2)

    # Plan now has both tasks
    p = rt.plan()
    assert p.ids() == {'t1', 'a1'}
    assert p.get('a1').depends_on == ['t1']

    # Not done yet (a1 is pending)
    assert not rt.is_done()

    # Drive agent
    spec = rt.next()
    assert spec is not None
    assert spec.tasks[0]['id'] == 'a1'

    # Verify prompt references t1's output
    td = rt.task_dir('a1')
    prompt = (td / 'prompt.md').read_text()
    assert '7' in prompt

    # Complete agent
    rt.commit_running(['a1'])
    rt.complete('a1', output={'val': 14})

    assert rt.is_done()

    # Final plan.yaml has all tasks with correct statuses
    p = rt.plan()
    assert p.get('t1').status == 'done'
    assert p.get('a1').status == 'done'
    assert rt.task_output('a1') == {'val': 14}
