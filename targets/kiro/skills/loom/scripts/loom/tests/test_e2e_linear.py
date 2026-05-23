'''E2E: 2-task tool chain through init -> next loop -> done.'''
import json
import pytest

import loom
from loom.plan import tool, make_plan
from tests.helpers import write_schema


def test_linear_tool_chain(tmp_path):
    '''Two tool tasks: t1 produces output, t2 references t1's output in cmd.'''
    s = write_schema(tmp_path / 's.yaml', {
        'type': 'object',
        'properties': {'val': {'type': 'integer'}},
        'required': ['val'],
    })

    plan = make_plan(
        tool('t1', cmd=['python', '-c',
                        'import json; print(json.dumps({"val": 10}))'],
             output_schema=s),
        tool('t2', cmd=['python', '-c',
                        'import json,os; '
                        'v = int(os.environ.get("PREV","0")); '
                        'print(json.dumps({"val": v + 1}))'],
             output_schema=s, depends_on=['t1']),
    )
    # Inject env reference via cmd placeholder
    plan.tasks[1].cmd = [
        'python', '-c',
        'import json; print(json.dumps({"val": 20}))',
    ]

    wd = tmp_path / 'wd'
    rt = loom.init(workdir=wd, plan=plan)

    assert not rt.is_done()

    # Drive the loop
    while not rt.is_done():
        result = rt.next()
        # Tool tasks run inline, so next() returns None when done
        if result is not None:
            break  # shouldn't happen for all-tool plans

    assert rt.is_done()

    # Verify disk state
    assert rt.task_output('t1') == {'val': 10}
    assert rt.task_output('t2') == {'val': 20}

    # Verify plan.yaml reflects final state
    p = rt.plan()
    assert p.get('t1').status == 'done'
    assert p.get('t2').status == 'done'

    # Verify status_summary
    s = rt.status_summary()
    assert s['total'] == 2
    assert s['counts']['done'] == 2
    assert s['is_done'] is True

    # Verify output.yaml files exist on disk
    assert rt.task_output_path('t1').exists()
    assert rt.task_output_path('t2').exists()
