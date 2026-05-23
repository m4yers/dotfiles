'''Tests for Jinja render + context bags.'''
import pytest
import yaml

from loom.engine.models import Task, LoomPlan
from loom.engine import store
from loom.render.jinja import render_task
from loom.errors import RenderFailed
from tests.helpers import write_template, write_output


class TestRenderBasic:
    def test_task_bag(self, tmp_path):
        tpl = write_template(tmp_path / 't.j2', 'id={{ task.id }} kind={{ task.kind }}')
        plan = LoomPlan(tasks=[
            Task(id='x', kind='agent', template=str(tpl), output_schema='/s.yaml'),
        ])
        store.ensure_task_dir(tmp_path, plan, 'x')
        result = render_task(plan.get('x'), tmp_path, plan)
        assert 'id=x' in result
        assert 'kind=agent' in result

    def test_run_bag(self, tmp_path):
        tpl = write_template(tmp_path / 't.j2', 'wd={{ run.workdir }}')
        plan = LoomPlan(tasks=[
            Task(id='x', kind='agent', template=str(tpl), output_schema='/s.yaml'),
        ])
        store.ensure_task_dir(tmp_path, plan, 'x')
        result = render_task(plan.get('x'), tmp_path, plan)
        assert str(tmp_path) in result

    def test_vars_bag(self, tmp_path):
        tpl = write_template(tmp_path / 't.j2', 'hint={{ vars.hint }}')
        plan = LoomPlan(tasks=[
            Task(id='x', kind='agent', template=str(tpl),
                 output_schema='/s.yaml', vars={'hint': 'focus'}),
        ])
        store.ensure_task_dir(tmp_path, plan, 'x')
        result = render_task(plan.get('x'), tmp_path, plan)
        assert 'hint=focus' in result

    def test_global_bag(self, tmp_path):
        tpl = write_template(tmp_path / 't.j2', 'g={{ global.path }}')
        plan = LoomPlan(tasks=[
            Task(id='x', kind='agent', template=str(tpl), output_schema='/s.yaml'),
        ])
        store.ensure_task_dir(tmp_path, plan, 'x')
        store.ensure_workdir_dirs(tmp_path)
        result = render_task(plan.get('x'), tmp_path, plan)
        assert str(tmp_path / 'global') in result


class TestUpstreamBag:
    def test_upstream_output_accessible(self, tmp_path):
        tpl = write_template(tmp_path / 't.j2',
                             'val={{ upstream.dep.output.val }}')
        plan = LoomPlan(tasks=[
            Task(id='dep', kind='tool', cmd=['echo'], output_schema='/s.yaml',
                 status='done'),
            Task(id='x', kind='agent', template=str(tpl),
                 output_schema='/s.yaml', depends_on=['dep']),
        ])
        td = store.ensure_task_dir(tmp_path, plan, 'dep')
        write_output(td / 'output.yaml', {'val': 99})
        store.ensure_task_dir(tmp_path, plan, 'x')
        result = render_task(plan.get('x'), tmp_path, plan)
        assert 'val=99' in result

    def test_transitive_dep(self, tmp_path):
        tpl = write_template(tmp_path / 't.j2',
                             'a={{ upstream.a.output.x }}')
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], output_schema='/s.yaml',
                 status='done'),
            Task(id='b', kind='tool', cmd=['echo'], output_schema='/s.yaml',
                 depends_on=['a'], status='done'),
            Task(id='c', kind='agent', template=str(tpl),
                 output_schema='/s.yaml', depends_on=['b']),
        ])
        td_a = store.ensure_task_dir(tmp_path, plan, 'a')
        write_output(td_a / 'output.yaml', {'x': 'hello'})
        store.ensure_task_dir(tmp_path, plan, 'b')
        store.ensure_task_dir(tmp_path, plan, 'c')
        result = render_task(plan.get('c'), tmp_path, plan)
        assert 'a=hello' in result


class TestRenderErrors:
    def test_missing_template_raises(self, tmp_path):
        plan = LoomPlan(tasks=[
            Task(id='x', kind='agent', template='/nonexistent.j2',
                 output_schema='/s.yaml'),
        ])
        with pytest.raises(RenderFailed, match='not found'):
            render_task(plan.get('x'), tmp_path, plan)

    def test_invalid_syntax_raises(self, tmp_path):
        tpl = write_template(tmp_path / 't.j2', '{{ undefined_var }}')
        plan = LoomPlan(tasks=[
            Task(id='x', kind='agent', template=str(tpl), output_schema='/s.yaml'),
        ])
        store.ensure_task_dir(tmp_path, plan, 'x')
        with pytest.raises(RenderFailed):
            render_task(plan.get('x'), tmp_path, plan)

    def test_no_template_field_raises(self, tmp_path):
        plan = LoomPlan(tasks=[
            Task(id='x', kind='agent', output_schema='/s.yaml'),
        ])
        with pytest.raises(RenderFailed, match='no template'):
            render_task(plan.get('x'), tmp_path, plan)

    def test_render_failed_has_attributes(self, tmp_path):
        plan = LoomPlan(tasks=[
            Task(id='x', kind='agent', template='/missing.j2',
                 output_schema='/s.yaml'),
        ])
        with pytest.raises(RenderFailed) as exc_info:
            render_task(plan.get('x'), tmp_path, plan)
        assert exc_info.value.task_id == 'x'
        assert exc_info.value.template_path == '/missing.j2'


class TestTemplateSearchPaths:
    def test_extends_resolves_via_search_paths(self, tmp_path):
        # Base template in a separate root
        root = tmp_path / 'templates'
        base = root / '_meta' / 'base.j2'
        base.parent.mkdir(parents=True)
        base.write_text('BASE:{% block body %}default{% endblock %}', encoding='utf-8')

        # Child template in a subdirectory
        child = root / 'kind' / 'extractor.j2'
        child.parent.mkdir(parents=True)
        child.write_text(
            "{% extends '_meta/base.j2' %}{% block body %}custom={{ task.id }}{% endblock %}",
            encoding='utf-8')

        plan = LoomPlan(tasks=[
            Task(id='x', kind='agent', template=str(child),
                 output_schema='/s.yaml',
                 template_search_paths=[str(root)]),
        ])
        store.ensure_task_dir(tmp_path, plan, 'x')
        result = render_task(plan.get('x'), tmp_path, plan)
        assert 'BASE:custom=x' in result

    def test_extends_fails_without_search_paths(self, tmp_path):
        root = tmp_path / 'templates'
        base = root / '_meta' / 'base.j2'
        base.parent.mkdir(parents=True)
        base.write_text('BASE:{% block body %}default{% endblock %}', encoding='utf-8')

        child = root / 'kind' / 'extractor.j2'
        child.parent.mkdir(parents=True)
        child.write_text(
            "{% extends '_meta/base.j2' %}{% block body %}custom{% endblock %}",
            encoding='utf-8')

        plan = LoomPlan(tasks=[
            Task(id='x', kind='agent', template=str(child),
                 output_schema='/s.yaml'),
        ])
        store.ensure_task_dir(tmp_path, plan, 'x')
        with pytest.raises(RenderFailed):
            render_task(plan.get('x'), tmp_path, plan)
