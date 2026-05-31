'''Tests for LoomRuntime methods: commit/complete/fail/reset/queries.'''
import pytest
import yaml

import loom
from loom.engine.runner import LoomRuntime
from loom.engine.models import LoomPlan, Task
from loom.engine import store
from loom.errors import OutputSchemaError, RunFailed, RenderFailed
from loom.plan import tool, agent, human, make_plan
from tests.helpers import write_schema, write_template, write_output


@pytest.fixture
def runtime_with_agent(tmp_path):
    '''Set up a runtime with one done tool + one ready agent task.'''
    s = write_schema(tmp_path / 's.yaml', {
        'type': 'object',
        'properties': {'val': {'type': 'integer'}},
        'required': ['val'],
    })
    tpl = write_template(tmp_path / 't.j2', 'prompt for {{ task.id }}')
    plan = make_plan(
        tool('t1', cmd=['python', '-c', 'import json; print(json.dumps({"val":1}))'],
             output_schema=s),
        agent('a1', template=tpl, output_schema=s, depends_on=['t1']),
    )
    rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
    # Run next() to execute tool inline and yield agent
    spec = rt.next()
    assert spec is not None
    assert len(spec.tasks) == 1
    assert spec.tasks[0]['id'] == 'a1'
    return rt


class TestCommitRunning:
    def test_flips_ready_to_running(self, runtime_with_agent):
        rt = runtime_with_agent
        rt.commit_running(['a1'])
        p = rt.plan()
        assert p.get('a1').status == 'running'

    def test_non_ready_raises(self, runtime_with_agent):
        rt = runtime_with_agent
        rt.commit_running(['a1'])
        with pytest.raises(ValueError, match='not in ready'):
            rt.commit_running(['a1'])  # already running


class TestComplete:
    def test_valid_output_transitions_to_done(self, runtime_with_agent):
        rt = runtime_with_agent
        rt.commit_running(['a1'])
        rt.complete('a1', output={'val': 99})
        p = rt.plan()
        assert p.get('a1').status == 'done'

    def test_missing_output_raises(self, runtime_with_agent):
        rt = runtime_with_agent
        rt.commit_running(['a1'])
        with pytest.raises(FileNotFoundError):
            rt.complete('a1')  # no output written

    def test_schema_mismatch_fails_task(self, runtime_with_agent):
        rt = runtime_with_agent
        rt.commit_running(['a1'])
        with pytest.raises(OutputSchemaError):
            rt.complete('a1', output={'wrong_key': 'not_int'})
        p = rt.plan()
        assert p.get('a1').status == 'failed'


class TestFail:
    def test_marks_failed(self, runtime_with_agent):
        rt = runtime_with_agent
        rt.commit_running(['a1'])
        rt.fail('a1', 'timeout')
        p = rt.plan()
        assert p.get('a1').status == 'failed'

    def test_writes_stderr(self, runtime_with_agent):
        rt = runtime_with_agent
        rt.commit_running(['a1'])
        rt.fail('a1', 'some error')
        td = rt.task_dir('a1')
        assert (td / 'stderr.log').exists()
        assert 'some error' in (td / 'stderr.log').read_text()


class TestRunAborted:
    '''A task in ``failed`` status causes the next call to
    ``runtime.next()`` to raise ``RunAborted``. Failure halts
    the whole run; downstream tasks are NOT cascade-failed
    individually (they remain in their pre-existing state).'''

    def test_failed_task_raises_run_aborted(self, runtime_with_agent):
        from loom.errors import RunAborted
        rt = runtime_with_agent
        rt.commit_running(['a1'])
        rt.fail('a1', 'timeout')
        with pytest.raises(RunAborted) as exc_info:
            rt.next()
        assert exc_info.value.failed_task_ids == ['a1']
        assert exc_info.value.task_id == 'a1'
        assert "'a1'" in str(exc_info.value)

    def test_run_aborted_exposes_all_failed_ids(self, tmp_path):
        '''Multiple failures in one run are all surfaced.'''
        from loom.errors import RunAborted
        s = write_schema(tmp_path / 's.yaml',
                         {'type': 'object',
                          'properties': {'v': {'type': 'integer'}},
                          'required': ['v']})
        tpl = write_template(tmp_path / 't.j2', 'p')
        plan = make_plan(
            agent('a', template=tpl, output_schema=s),
            agent('b', template=tpl, output_schema=s),
        )
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        spec = rt.next()
        ids = [t['id'] for t in spec.tasks]
        assert sorted(ids) == ['a', 'b']
        rt.commit_running(ids)
        rt.fail('a', 'oops a')
        rt.fail('b', 'oops b')
        with pytest.raises(RunAborted) as exc_info:
            rt.next()
        assert sorted(exc_info.value.failed_task_ids) == ['a', 'b']

    def test_in_flight_completion_still_works(self, tmp_path):
        '''Q1=(a) semantics: a task that completes after another
        fails is still recorded; the run-aborted flag fires only
        when next() is called.'''
        from loom.errors import RunAborted
        s = write_schema(tmp_path / 's.yaml',
                         {'type': 'object',
                          'properties': {'v': {'type': 'integer'}},
                          'required': ['v']})
        tpl = write_template(tmp_path / 't.j2', 'p')
        plan = make_plan(
            agent('a', template=tpl, output_schema=s),
            agent('b', template=tpl, output_schema=s),
        )
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        spec = rt.next()
        rt.commit_running([t['id'] for t in spec.tasks])
        # A fails first, B finishes after.
        rt.fail('a', 'fail-a')
        rt.complete('b', output={'v': 7})
        # b's terminal state is preserved.
        assert rt.plan().get('b').status == 'done'
        # next() now reports the run aborted.
        with pytest.raises(RunAborted):
            rt.next()


class TestReset:
    def test_resets_to_pending(self, runtime_with_agent):
        rt = runtime_with_agent
        rt.commit_running(['a1'])
        rt.fail('a1', 'err')
        rt.reset('a1')
        p = rt.plan()
        assert p.get('a1').status == 'pending'

    def test_clears_artifacts(self, runtime_with_agent):
        rt = runtime_with_agent
        rt.commit_running(['a1'])
        rt.complete('a1', output={'val': 1})
        rt.reset('a1')
        td = rt.task_dir('a1')
        assert not (td / 'output.yaml').exists()


class TestQueries:
    def test_is_done_false_initially(self, runtime_with_agent):
        assert not runtime_with_agent.is_done()

    def test_is_done_true_after_complete(self, runtime_with_agent):
        rt = runtime_with_agent
        rt.commit_running(['a1'])
        rt.complete('a1', output={'val': 1})
        assert rt.is_done()

    def test_task_output(self, runtime_with_agent):
        rt = runtime_with_agent
        rt.commit_running(['a1'])
        rt.complete('a1', output={'val': 77})
        assert rt.task_output('a1') == {'val': 77}

    def test_task_output_none_when_missing(self, runtime_with_agent):
        assert runtime_with_agent.task_output('a1') is None

    def test_global_dir(self, runtime_with_agent):
        rt = runtime_with_agent
        assert rt.global_dir().name == 'global'
        assert rt.global_dir().is_dir()

    def test_global_path(self, runtime_with_agent):
        rt = runtime_with_agent
        p = rt.global_path('docs', 'readme.md')
        assert str(p).endswith('global/docs/readme.md')

    def test_status_summary(self, runtime_with_agent):
        rt = runtime_with_agent
        s = rt.status_summary()
        assert s['total'] == 2
        assert s['is_done'] is False

    def test_resolve_value(self, runtime_with_agent):
        rt = runtime_with_agent
        result = rt.resolve_value('${workdir}')
        assert str(rt.workdir) in result


class TestNextRenderFailure:
    def test_render_failure_marks_failed(self, tmp_path):
        s = write_schema(tmp_path / 's.yaml', {'type': 'object'})
        # Template with undefined var triggers StrictUndefined error
        tpl = write_template(tmp_path / 't.j2', '{{ nonexistent_var }}')
        plan = make_plan(
            agent('a1', template=tpl, output_schema=s),
        )
        rt = loom.init(workdir=tmp_path / 'wd', plan=plan)
        with pytest.raises(RenderFailed):
            rt.next()
        p = rt.plan()
        assert p.get('a1').status == 'failed'
