'''Tests for plan builder factory functions: tool(), agent(), human(), make_plan().'''
import pytest

from loom.plan import tool, agent, human, make_plan
from loom.engine.models import LoomPlan, Task


class TestToolFactory:
    def test_basic(self):
        t = tool('x', cmd=['echo'], output_schema='/s.yaml')
        assert t.kind == 'tool'
        assert t.cmd == ['echo']
        assert t.output_schema == '/s.yaml'

    def test_rejects_template(self):
        with pytest.raises(TypeError):
            tool('x', cmd=['echo'], output_schema='/s.yaml', template='/t.j2')

    def test_requires_cmd(self):
        with pytest.raises((ValueError, TypeError)):
            tool('x', output_schema='/s.yaml')

    def test_requires_output_schema(self):
        with pytest.raises((ValueError, TypeError)):
            tool('x', cmd=['echo'])

    def test_empty_cmd_raises(self):
        with pytest.raises(ValueError, match='cmd'):
            tool('x', cmd=[], output_schema='/s.yaml')

    def test_with_depends_on(self):
        t = tool('x', cmd=['echo'], output_schema='/s.yaml', depends_on=['a'])
        assert t.depends_on == ['a']

    def test_with_when(self):
        t = tool('x', cmd=['echo'], output_schema='/s.yaml',
                 when='task.a.val > `0`')
        assert t.when == 'task.a.val > `0`'


class TestAgentFactory:
    def test_basic(self):
        t = agent('x', template='/t.j2', output_schema='/s.yaml')
        assert t.kind == 'agent'
        assert t.template == '/t.j2'
        assert t.output_schema == '/s.yaml'

    def test_requires_template(self):
        with pytest.raises((ValueError, TypeError)):
            agent('x', output_schema='/s.yaml')

    def test_requires_output_schema(self):
        with pytest.raises((ValueError, TypeError)):
            agent('x', template='/t.j2')

    def test_with_vars(self):
        t = agent('x', template='/t.j2', output_schema='/s.yaml',
                  vars={'k': 'v'})
        assert t.vars == {'k': 'v'}

    def test_with_agent_label(self):
        t = agent('x', template='/t.j2', output_schema='/s.yaml',
                  agent='my-agent')
        assert t.agent == 'my-agent'


class TestHumanFactory:
    def test_minimal(self):
        t = human('x')
        assert t.kind == 'human'
        assert t.output_schema is None
        assert t.template is None

    def test_with_template(self):
        t = human('x', template='/t.j2')
        assert t.template == '/t.j2'

    def test_with_output_schema(self):
        t = human('x', output_schema='/s.yaml')
        assert t.output_schema == '/s.yaml'

    def test_with_vars(self):
        t = human('x', vars={'k': 'v'})
        assert t.vars == {'k': 'v'}


class TestMakePlan:
    def test_returns_loom_plan(self):
        p = make_plan(
            tool('a', cmd=['echo'], output_schema='/s.yaml'),
            agent('b', template='/t.j2', output_schema='/s.yaml'),
        )
        assert isinstance(p, LoomPlan)
        assert p.ids() == {'a', 'b'}

    def test_empty_plan(self):
        p = make_plan()
        assert p.ids() == set()

    def test_preserves_order(self):
        p = make_plan(
            tool('c', cmd=['echo'], output_schema='/s.yaml'),
            tool('a', cmd=['echo'], output_schema='/s.yaml'),
            tool('b', cmd=['echo'], output_schema='/s.yaml'),
        )
        assert [t.id for t in p.tasks] == ['c', 'a', 'b']
