r"""Builds the loom DAG for the think workflow.

DAG shape:

    rubric           answer-1  answer-2  answer-3
       \________________|_________/         |
        |               |                   |
        compare-1v2     compare-1v3   compare-2v3
                  \______|______/
                         |
                        rank

Three independence rules the DAG enforces:

1. The `rubric` task and the three `answer-*` tasks have no
   dependency edges between them. The answer agents
   structurally cannot see the rubric and cannot tailor
   their responses to its weights.
2. Each `compare-*` task waits on `rubric` and exactly two
   answer tasks — the pair it judges.
3. `rank` waits on all three compares; it is a tool task,
   not an agent, so the aggregation is deterministic.

Schemas live under `<skill>/schemas/`, prompt templates
under `<skill>/templates/prompts/`, both referenced
absolutely so loom can locate them regardless of the
caller's CWD.
"""
from __future__ import annotations

from pathlib import Path

from loom import LoomPlan, agent, make_plan, tool

# Path layout: <skill>/scripts/think/think/plan.py — parents[3]
# is the skill directory.
SKILL_ROOT = Path(__file__).resolve().parents[3]
PROMPTS    = SKILL_ROOT / "templates" / "prompts"
SCHEMAS    = SKILL_ROOT / "schemas"
SCRIPTS    = SKILL_ROOT / "scripts"
THINK_SH   = SCRIPTS / "think.sh"


# Pair-wise comparisons. One entry per pair the rank tool will
# aggregate. Three pairs == complete tournament for N=3, which
# is what Copeland aggregation requires (no judging gaps).
_COMPARE_PAIRS = [
    ("compare-1v2", "answer-1", "answer-2"),
    ("compare-1v3", "answer-1", "answer-3"),
    ("compare-2v3", "answer-2", "answer-3"),
]


def build_plan(workdir: Path, question: str, context: str) -> LoomPlan:
    """Construct the think LoomPlan.

    `question` and `context` are the user inputs. They are
    passed as task `vars` so the prompt templates can
    reference them via the `vars` bag.
    """
    common_vars = {"question": question, "context": context}

    # Rubric — keystone agent. Reads question + context; emits
    # 3-8 weighted dimensions tailored to THIS question.
    rubric = agent(
        "rubric",
        template=str(PROMPTS / "rubric.md.j2"),
        output_schema=str(SCHEMAS / "rubric.yaml"),
        vars=common_vars,
    )

    # Answer agents — three independent siblings of `rubric`.
    # No dep edge: structurally cannot see rubric.
    answers = [
        agent(
            f"answer-{i}",
            template=str(PROMPTS / "answer.md.j2"),
            output_schema=str(SCHEMAS / "answer.yaml"),
            vars={"question": question, "answer_id": f"answer-{i}"},
        )
        for i in (1, 2, 3)
    ]

    # Compares — each depends on rubric + the two answers it
    # judges. `pair_name` and the answer paths are passed as
    # vars so the prompt template can reference them without
    # re-deriving from the dep list.
    compares = [
        agent(
            cid,
            template=str(PROMPTS / "compare.md.j2"),
            output_schema=str(SCHEMAS / "compare.yaml"),
            depends_on_all=["rubric", a, b],
            vars={
                "pair_name":      cid,
                "a":              a,
                "b":              b,
                "rubric_path":    "${task_path:rubric}",
                "answer_a_path":  "${task_path:" + a + "}",
                "answer_b_path":  "${task_path:" + b + "}",
            },
        )
        for cid, a, b in _COMPARE_PAIRS
    ]

    # Rank — deterministic tool task. Aggregates the three
    # compares into a Copeland-weighted ranking. See rank.py
    # for the formula and tie-credit constant.
    rank = tool(
        "rank",
        cmd=[str(THINK_SH), "pipeline", "rank", "${workdir}"],
        depends_on_all=[cid for cid, _, _ in _COMPARE_PAIRS],
        output_schema=str(SCHEMAS / "rank.yaml"),
    )

    return make_plan(rubric, *answers, *compares, rank)
