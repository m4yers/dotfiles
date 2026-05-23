'''Tests for DAG validation: cycles, dups, missing deps, kind-field consistency.'''
import pytest

from loom.engine.models import Task, LoomPlan
from loom.validate.dag import validate_dag, validate_kind_fields
from loom.errors import DAGError, LoomPlanError


class TestDuplicateIds:
    def test_duplicate_raises(self):
        plan = LoomPlan(tasks=[
            Task(id='x', kind='tool', cmd=['echo']),
            Task(id='x', kind='tool', cmd=['echo']),
        ])
        with pytest.raises(DAGError, match='duplicate'):
            validate_dag(plan)

    def test_unique_passes(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo']),
            Task(id='b', kind='tool', cmd=['echo']),
        ])
        validate_dag(plan)  # no exception


class TestMissingDeps:
    def test_missing_dep_raises(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], depends_on=['nonexistent']),
        ])
        with pytest.raises(DAGError, match='unknown id'):
            validate_dag(plan)

    def test_valid_dep_passes(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo']),
            Task(id='b', kind='tool', cmd=['echo'], depends_on=['a']),
        ])
        validate_dag(plan)


class TestCycleDetection:
    def test_simple_cycle(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], depends_on=['b']),
            Task(id='b', kind='tool', cmd=['echo'], depends_on=['a']),
        ])
        with pytest.raises(DAGError, match='cycle'):
            validate_dag(plan)

    def test_self_cycle(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], depends_on=['a']),
        ])
        with pytest.raises(DAGError, match='cycle'):
            validate_dag(plan)

    def test_three_node_cycle(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo'], depends_on=['c']),
            Task(id='b', kind='tool', cmd=['echo'], depends_on=['a']),
            Task(id='c', kind='tool', cmd=['echo'], depends_on=['b']),
        ])
        with pytest.raises(DAGError, match='cycle'):
            validate_dag(plan)

    def test_diamond_no_cycle(self):
        plan = LoomPlan(tasks=[
            Task(id='a', kind='tool', cmd=['echo']),
            Task(id='b', kind='tool', cmd=['echo'], depends_on=['a']),
            Task(id='c', kind='tool', cmd=['echo'], depends_on=['a']),
            Task(id='d', kind='tool', cmd=['echo'], depends_on=['b', 'c']),
        ])
        validate_dag(plan)


class TestKindFields:
    def test_tool_without_cmd(self):
        plan = LoomPlan(tasks=[Task(id='x', kind='tool', output_schema='/s.yaml')])
        with pytest.raises(LoomPlanError, match='cmd'):
            validate_kind_fields(plan)

    def test_tool_without_output_schema(self):
        plan = LoomPlan(tasks=[Task(id='x', kind='tool', cmd=['echo'])])
        with pytest.raises(LoomPlanError, match='output_schema'):
            validate_kind_fields(plan)

    def test_tool_with_template_rejected(self):
        plan = LoomPlan(tasks=[
            Task(id='x', kind='tool', cmd=['echo'], output_schema='/s.yaml',
                 template='/t.j2')])
        with pytest.raises(LoomPlanError, match='template'):
            validate_kind_fields(plan)

    def test_tool_with_vars_rejected(self):
        plan = LoomPlan(tasks=[
            Task(id='x', kind='tool', cmd=['echo'], output_schema='/s.yaml',
                 vars={'k': 'v'})])
        with pytest.raises(LoomPlanError, match='vars'):
            validate_kind_fields(plan)

    def test_agent_without_template(self):
        plan = LoomPlan(tasks=[
            Task(id='x', kind='agent', output_schema='/s.yaml')])
        with pytest.raises(LoomPlanError, match='template'):
            validate_kind_fields(plan)

    def test_agent_without_output_schema(self):
        plan = LoomPlan(tasks=[
            Task(id='x', kind='agent', template='/t.j2')])
        with pytest.raises(LoomPlanError, match='output_schema'):
            validate_kind_fields(plan)

    def test_human_without_output_schema_passes(self):
        plan = LoomPlan(tasks=[Task(id='x', kind='human')])
        validate_kind_fields(plan)  # no exception

    def test_human_with_cmd_rejected(self):
        plan = LoomPlan(tasks=[Task(id='x', kind='human', cmd=['echo'])])
        with pytest.raises(LoomPlanError, match='cmd'):
            validate_kind_fields(plan)

    def test_unknown_kind(self):
        plan = LoomPlan(tasks=[Task(id='x', kind='unknown')])
        with pytest.raises(LoomPlanError, match='unknown kind'):
            validate_kind_fields(plan)

    def test_valid_tool(self):
        plan = LoomPlan(tasks=[
            Task(id='x', kind='tool', cmd=['echo'], output_schema='/s.yaml')])
        validate_kind_fields(plan)

    def test_valid_agent(self):
        plan = LoomPlan(tasks=[
            Task(id='x', kind='agent', template='/t.j2', output_schema='/s.yaml')])
        validate_kind_fields(plan)
