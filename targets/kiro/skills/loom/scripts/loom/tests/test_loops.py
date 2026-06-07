'''Phase 1 loop tests: self-loop validation + execution.

Covers the `latch` block (fuel / while exit controls), per-iteration
output namespacing, fuel decrement, while-based exit, and downstream
gating (a consumer fires only after the loop finishes).
'''
import textwrap
from pathlib import Path

import pytest

import loom
from loom.plan import tool, agent, make_plan, latch
from loom.errors import NoExitConditionError, LoomPlanError, DAGError
from loom.engine import store
from tests.helpers import write_schema, write_template


# ---- helpers ----

def _int_schema(tmp_path: Path) -> Path:
    return write_schema(tmp_path / 'schemas' / 'int.yaml', {
        'type': 'object',
        'properties': {'val': {'type': 'integer'}},
        'required': ['val'],
    })


def _status_schema(tmp_path: Path) -> Path:
    return write_schema(tmp_path / 'schemas' / 'status.yaml', {
        'type': 'object',
        'properties': {'status': {'type': 'string'}},
        'required': ['status'],
    })


def _counter_script(tmp_path: Path) -> Path:
    '''A tool that increments a counter in WORKDIR and reports a status
    of "go" while n < 3, else "stop". Lets us drive while-based exit
    deterministically without cross-iteration references (Phase 2).'''
    p = tmp_path / 'count.py'
    p.write_text(textwrap.dedent('''
        import json, os
        wd = os.environ["WORKDIR"]
        cf = os.path.join(wd, "counter.txt")
        n = int(open(cf).read()) if os.path.exists(cf) else 0
        n += 1
        open(cf, "w").write(str(n))
        print(json.dumps({"status": "go" if n < 3 else "stop"}))
    ''').strip(), encoding='utf-8')
    return p


def _iter_dirs(rt, task_id):
    td = rt.task_dir(task_id)
    return store._iter_dirs(td)


# ---- the latch() builder ----

def test_latch_builder_shapes():
    assert latch('x', fuel=5) == {'header': 'x', 'fuel': 5}
    assert latch('x', while_="a == 'b'") == {'header': 'x', 'while': "a == 'b'"}
    assert latch('x', fuel=2, while_='p') == {
        'header': 'x', 'fuel': 2, 'while': 'p'}


# ---- validation ----

def test_loop_requires_exit_condition(tmp_path):
    s = _int_schema(tmp_path)
    plan = make_plan(
        tool('loop', cmd=['echo', '{"val":1}'], output_schema=s,
             latch={'header': 'loop'}),  # no fuel, no while
    )
    with pytest.raises(NoExitConditionError):
        loom.init(workdir=tmp_path / 'wd', plan=plan)


def test_loop_fuel_must_be_positive_int(tmp_path):
    s = _int_schema(tmp_path)
    for bad in (0, -1, 'five', True):
        plan = make_plan(
            tool('loop', cmd=['echo', '{"val":1}'], output_schema=s,
                 latch={'header': 'loop', 'fuel': bad}),
        )
        with pytest.raises(LoomPlanError):
            loom.init(workdir=tmp_path / f'wd-{bad}', plan=plan)


def test_loop_header_must_exist(tmp_path):
    s = _int_schema(tmp_path)
    plan = make_plan(
        tool('loop', cmd=['echo', '{"val":1}'], output_schema=s,
             latch={'header': 'ghost', 'fuel': 2}),
    )
    with pytest.raises(DAGError):
        loom.init(workdir=tmp_path / 'wd', plan=plan)


def test_multinode_loop_runs(tmp_path):
    '''L2 natural loop: fix -> review with back-edge review -> fix.

    Body is {fix, review}; fetch (before) and after (downstream) sit
    outside and run once.'''
    s = _int_schema(tmp_path)
    echo = lambda v: ['python', '-c',
                      f'import json; print(json.dumps({{"val": {v}}}))']
    plan = make_plan(
        tool('fetch', cmd=echo(0), output_schema=s),
        tool('fix', cmd=echo(1), output_schema=s, depends_on_all=['fetch']),
        tool('review', cmd=echo(2), output_schema=s,
             depends_on_all=['fix'], latch=latch('fix', fuel=2)),
        tool('after', cmd=echo(9), output_schema=s,
             depends_on_all=['review']),
    )
    rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
    assert rt.next() is None
    assert rt.is_done()

    # Body nodes iterate twice; outside nodes run once (flat).
    assert [d.name for d in _iter_dirs(rt, 'fix')] == ['iter-00', 'iter-01']
    assert [d.name for d in _iter_dirs(rt, 'review')] == ['iter-00', 'iter-01']
    assert not store._iter_dirs(rt.task_dir('fetch'))
    assert not store._iter_dirs(rt.task_dir('after'))
    p = rt.plan()
    assert p.get('after').status == 'done'
    assert p.get('review').latch['fuel'] == 0


def test_hammock_exit_escape_rejected(tmp_path):
    '''A node outside the region consuming a non-latch body node violates
    single-exit.'''
    s = _int_schema(tmp_path)
    e = ['echo', '{"val":1}']
    plan = make_plan(
        tool('fix', cmd=e, output_schema=s),
        tool('mid', cmd=e, output_schema=s, depends_on_all=['fix']),
        tool('review', cmd=e, output_schema=s, depends_on_all=['mid'],
             latch=latch('fix', fuel=3)),
        # leak depends on a body node (mid) that is not the latch.
        tool('leak', cmd=e, output_schema=s, depends_on_all=['mid']),
    )
    from loom.errors import LoopEscapeError
    with pytest.raises(LoopEscapeError):
        loom.init(workdir=tmp_path / 'wd', plan=plan)


def test_irreducible_multi_backedge_rejected(tmp_path):
    '''Two latches sharing a header is not a natural loop.'''
    s = _int_schema(tmp_path)
    e = ['echo', '{"val":1}']
    plan = make_plan(
        tool('fix', cmd=e, output_schema=s),
        tool('a', cmd=e, output_schema=s, depends_on_all=['fix'],
             latch=latch('fix', fuel=2)),
        tool('b', cmd=e, output_schema=s, depends_on_all=['fix'],
             latch=latch('fix', fuel=2)),
    )
    from loom.errors import IrreducibleLoopError
    with pytest.raises(IrreducibleLoopError):
        loom.init(workdir=tmp_path / 'wd', plan=plan)


def test_irreducible_header_not_dominator_rejected(tmp_path):
    '''Header that does not dominate the latch (two entry paths).'''
    s = _int_schema(tmp_path)
    e = ['echo', '{"val":1}']
    plan = make_plan(
        tool('r1', cmd=e, output_schema=s),
        tool('r2', cmd=e, output_schema=s),
        tool('loop', cmd=e, output_schema=s,
             depends_on_all=['r1', 'r2'], latch=latch('r1', fuel=2)),
    )
    from loom.errors import IrreducibleLoopError
    with pytest.raises(IrreducibleLoopError):
        loom.init(workdir=tmp_path / 'wd', plan=plan)


# ---- execution: fuel ----

def test_fuel_self_loop_runs_n_rounds(tmp_path):
    s = _int_schema(tmp_path)
    plan = make_plan(
        tool('loop', cmd=['python', '-c',
                          'import json; print(json.dumps({"val": 1}))'],
             output_schema=s, latch=latch('loop', fuel=3)),
    )
    rt = loom.init(workdir=tmp_path / 'wd', plan=plan)

    assert rt.next() is None          # tool self-loop runs all rounds inline
    assert rt.is_done()

    iters = _iter_dirs(rt, 'loop')
    assert [d.name for d in iters] == ['iter-00', 'iter-01', 'iter-02']
    for d in iters:
        assert (d / 'output.yaml').exists()

    # fuel decremented to 0; latch left done.
    p = rt.plan()
    assert p.get('loop').status == 'done'
    assert p.get('loop').latch['fuel'] == 0


def test_fuel_one_runs_exactly_once(tmp_path):
    s = _int_schema(tmp_path)
    plan = make_plan(
        tool('loop', cmd=['python', '-c',
                          'import json; print(json.dumps({"val": 1}))'],
             output_schema=s, latch=latch('loop', fuel=1)),
    )
    rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
    assert rt.next() is None
    assert [d.name for d in _iter_dirs(rt, 'loop')] == ['iter-00']


# ---- execution: while ----

def test_while_self_loop_exits_on_predicate(tmp_path):
    s = _status_schema(tmp_path)
    script = _counter_script(tmp_path)
    plan = make_plan(
        tool('loop', cmd=['python', str(script)], output_schema=s,
             latch=latch('loop', while_="${task:loop:status} == 'go'")),
    )
    rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
    assert rt.next() is None
    assert rt.is_done()
    # n=1 go, n=2 go, n=3 stop -> 3 rounds, last output status 'stop'.
    assert [d.name for d in _iter_dirs(rt, 'loop')] == [
        'iter-00', 'iter-01', 'iter-02']
    assert rt.task_output('loop') == {'status': 'stop'}


def test_fuel_caps_before_while_converges(tmp_path):
    '''fuel=2 stops the loop before the counter reaches its 'stop' state.'''
    s = _status_schema(tmp_path)
    script = _counter_script(tmp_path)
    plan = make_plan(
        tool('loop', cmd=['python', str(script)], output_schema=s,
             latch=latch('loop', fuel=2,
                         while_="${task:loop:status} == 'go'")),
    )
    rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
    assert rt.next() is None
    assert [d.name for d in _iter_dirs(rt, 'loop')] == ['iter-00', 'iter-01']
    # while was still 'go' at the cap; fuel forced the stop.
    assert rt.task_output('loop') == {'status': 'go'}
    assert rt.plan().get('loop').latch['fuel'] == 0


# ---- downstream gating + namespacing ----

def test_downstream_runs_once_after_loop(tmp_path):
    s = _int_schema(tmp_path)
    plan = make_plan(
        tool('loop', cmd=['python', '-c',
                          'import json; print(json.dumps({"val": 1}))'],
             output_schema=s, latch=latch('loop', fuel=3)),
        tool('after', cmd=['python', '-c',
                           'import json; print(json.dumps({"val": 9}))'],
             output_schema=s, depends_on_all=['loop']),
    )
    rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
    assert rt.next() is None
    assert rt.is_done()

    # loop iterated 3x; consumer ran exactly once (flat output, no iter dirs).
    assert len(_iter_dirs(rt, 'loop')) == 3
    after_td = rt.task_dir('after')
    assert (after_td / 'output.yaml').exists()
    assert not store._iter_dirs(after_td)
    assert rt.plan().get('after').status == 'done'


def test_latch_round_trips_through_plan_yaml(tmp_path):
    s = _int_schema(tmp_path)
    plan = make_plan(
        tool('loop', cmd=['echo', '{"val":1}'], output_schema=s,
             latch=latch('loop', fuel=4)),
    )
    wd = tmp_path / 'wd'
    loom.init(workdir=wd, plan=plan)
    # Reload from disk via resume; latch must survive serialization.
    rt2 = loom.resume(wd)
    assert rt2.plan().get('loop').latch == {'header': 'loop', 'fuel': 4}


def test_agent_self_loop_external_path(tmp_path):
    '''Agent latch driven via next() -> commit_running -> complete.'''
    s = _int_schema(tmp_path)
    tpl = write_template(tmp_path / 'refine.j2', 'refine round')
    plan = make_plan(
        agent('refine', template=tpl, output_schema=s,
              latch=latch('refine', fuel=2)),
    )
    rt = loom.init(workdir=tmp_path / 'wd', plan=plan)

    rounds = 0
    while True:
        spec = rt.next()
        if spec is None:
            break
        for t in spec.tasks:
            rt.commit_running([t['id']])
            rt.complete(t['id'], output={'val': rounds})
            rounds += 1
        assert rounds <= 5  # guard against runaway in a broken impl

    assert rounds == 2
    assert rt.is_done()
    iters = _iter_dirs(rt, 'refine')
    assert [d.name for d in iters] == ['iter-00', 'iter-01']
    for d in iters:
        assert (d / 'output.yaml').exists()
    assert (rt.task_dir('refine') / 'prompt.md').exists()


# ---- Phase 2: cross-iteration references ----

def _int_counter_script(tmp_path: Path, cap: int | None = None) -> Path:
    '''Tool that writes {"val": n} where n increments each round (capped
    at `cap` if given). Counter persists in WORKDIR across rounds.'''
    body = 'min(n, %d)' % cap if cap is not None else 'n'
    p = tmp_path / 'counter_int.py'
    p.write_text(textwrap.dedent(f'''
        import json, os
        wd = os.environ["WORKDIR"]
        cf = os.path.join(wd, "ci.txt")
        n = int(open(cf).read()) if os.path.exists(cf) else 0
        n += 1
        open(cf, "w").write(str(n))
        print(json.dumps({{"val": {body}}}))
    ''').strip(), encoding='utf-8')
    return p


def test_iteration_selector_references(tmp_path):
    s = _int_schema(tmp_path)
    script = _int_counter_script(tmp_path)
    plan = make_plan(
        tool('loop', cmd=['python', str(script)], output_schema=s,
             latch=latch('loop', fuel=3)),
    )
    rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
    assert rt.next() is None
    # iter-00 val=1, iter-01 val=2, iter-02 val=3.
    assert rt.resolve_value('${task:loop@0:val}') == 1
    assert rt.resolve_value('${task:loop@2:val}') == 3
    assert rt.resolve_value('${task:loop:val}') == 3        # latest completed
    assert rt.resolve_value('${task:loop@prev:val}') == 2   # completed[-2]
    assert rt.resolve_value('${task:loop@99:val}') is None  # out of range


def test_while_prev_convergence(tmp_path):
    '''Loop stops when this round's value equals the previous round's
    (a convergence test using @prev).'''
    s = _int_schema(tmp_path)
    script = _int_counter_script(tmp_path, cap=2)  # 1, 2, 2, 2, ...
    plan = make_plan(
        tool('loop', cmd=['python', str(script)], output_schema=s,
             latch=latch('loop',
                         while_="${task:loop:val} != ${task:loop@prev:val}")),
    )
    rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
    assert rt.next() is None
    assert rt.is_done()
    # round0 val1 (prev null -> differ), round1 val2 (prev 1 -> differ),
    # round2 val2 (prev 2 -> equal -> stop). 3 rounds.
    assert [d.name for d in _iter_dirs(rt, 'loop')] == [
        'iter-00', 'iter-01', 'iter-02']


# ---- Phase 4: visualisation ----

def test_visualise_shows_loop_annotation(tmp_path):
    s = _int_schema(tmp_path)
    plan = make_plan(
        tool('loop', cmd=['echo', '{"val":1}'], output_schema=s,
             latch=latch('loop', fuel=3)),
    )
    out = loom.visualise(plan)
    assert '↻ loop → loop' in out
    assert 'fuel 3' in out

    out_ascii = loom.visualise(plan, ascii_only=True)
    assert 'loop -> loop' in out_ascii
    assert 'fuel 3' in out_ascii


# ---- audit fixes: 1,2,4,5,6,8,9 ----

def test_exports_runaborted_and_looperror():  # #9
    assert hasattr(loom, 'RunAborted')
    assert hasattr(loom, 'LoopError')
    assert hasattr(loom, 'NoExitConditionError')


def test_nested_loops_rejected(tmp_path):  # #1
    s = _int_schema(tmp_path)
    e = ['echo', '{"val":1}']
    plan = make_plan(
        tool('fix', cmd=e, output_schema=s),
        tool('build', cmd=e, output_schema=s, depends_on_all=['fix'],
             latch=latch('build', fuel=2)),               # inner self-loop
        tool('review', cmd=e, output_schema=s, depends_on_all=['build'],
             latch=latch('fix', fuel=2)),                 # outer loop fix..review
    )
    from loom.errors import LoopNestingError
    with pytest.raises(LoopNestingError):
        loom.init(workdir=tmp_path / 'wd', plan=plan)


def test_latch_while_unknown_ref_rejected(tmp_path):  # #2
    s = _int_schema(tmp_path)
    plan = make_plan(
        tool('loop', cmd=['echo', '{"val":1}'], output_schema=s,
             latch=latch('loop', while_="${task:ghost:val} == `1`")),
    )
    from loom.errors import ReferenceError as LoomRefError
    with pytest.raises(LoomRefError):
        loom.init(workdir=tmp_path / 'wd', plan=plan)


def test_reference_into_body_rejected(tmp_path):  # #4
    '''An outside task consuming a non-latch body node via ${task_path:}
    violates single-exit and must be rejected by the boundary scan.'''
    s = _int_schema(tmp_path)
    e = ['echo', '{"val":1}']
    plan = make_plan(
        tool('fix', cmd=e, output_schema=s),
        tool('mid', cmd=e, output_schema=s, depends_on_all=['fix']),
        tool('review', cmd=e, output_schema=s, depends_on_all=['mid'],
             latch=latch('fix', fuel=3)),
        tool('leak', cmd=['cat', '${task_path:mid}'], output_schema=s),
    )
    from loom.errors import LoopEscapeError
    with pytest.raises(LoopEscapeError):
        loom.init(workdir=tmp_path / 'wd', plan=plan)


def test_selector_normalisation_and_validation(tmp_path):  # #5
    from loom.engine.algorithm import desugar_predicate
    # leading zeros normalise to canonical context keys
    assert desugar_predicate('${task:x@05:v} == `1`') == 'task_iter."x"."5".v == `1`'
    assert desugar_predicate('${task:x@prev:v}') == 'task_iter."x"."prev".v'

    s = _int_schema(tmp_path)
    from loom.errors import ReferenceError as LoomRefError
    # bogus selector
    bad = make_plan(
        tool('loop', cmd=['echo', '{"val":1}'], output_schema=s,
             latch=latch('loop', while_="${task:loop@xyz:val} == `1`")),
    )
    with pytest.raises(LoomRefError):
        loom.init(workdir=tmp_path / 'wd1', plan=bad)
    # selector targeting a non-loop task
    bad2 = make_plan(
        tool('flat', cmd=['echo', '{"val":1}'], output_schema=s),
        tool('user', cmd=['echo', '${task:flat@0:val}'], output_schema=s,
             depends_on_all=['flat']),
    )
    with pytest.raises(LoomRefError):
        loom.init(workdir=tmp_path / 'wd2', plan=bad2)


def test_reset_clears_iterations_and_region(tmp_path):  # #6
    s = _int_schema(tmp_path)
    plan = make_plan(
        tool('loop', cmd=['python', '-c',
                          'import json; print(json.dumps({"val": 1}))'],
             output_schema=s, latch=latch('loop', fuel=3)),
    )
    rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
    assert rt.next() is None
    assert len(_iter_dirs(rt, 'loop')) == 3
    rt.reset('loop')
    assert _iter_dirs(rt, 'loop') == []          # iter dirs cleared
    assert rt.plan().get('loop').status == 'pending'


def test_write_path_never_overwrites_completed_round(tmp_path):  # #8
    s = _int_schema(tmp_path)
    plan = make_plan(
        tool('loop', cmd=['echo', '{"val":1}'], output_schema=s,
             latch=latch('loop', fuel=3)),
    )
    wd = tmp_path / 'wd'
    rt = loom.init(workdir=wd, plan=plan)
    p = rt.plan()
    td = store.task_dir(wd, p, 'loop')
    (td / 'iter-00').mkdir(parents=True)
    (td / 'iter-00' / 'output.yaml').write_text('val: 1', encoding='utf-8')
    # iter-00 already has output and no fresh dir exists -> write to iter-01.
    wp = store.task_output_write_path(wd, p, 'loop')
    assert wp.parent.name == 'iter-01'
