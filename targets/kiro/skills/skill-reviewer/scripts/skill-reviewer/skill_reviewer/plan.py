"""Derive the loom plan for a skill review run.

Static DAG: locate → (lint || 8 check-* tasks) → assemble →
gate → finalize.

Type-specific check tasks (interface/tool/workflow/reference) are
all declared at plan time and gated by `when:` predicates so only
the matching one runs.
"""
from __future__ import annotations

from pathlib import Path

from loom import LoomPlan, agent, human, make_plan, tool

# Path layout:
#   <skill>/scripts/skill-reviewer/skill_reviewer/plan.py
#   parents[3] = skill root
SKILL_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS    = SKILL_ROOT / "scripts"
SCHEMAS    = SKILL_ROOT / "schemas"
TEMPLATES  = SKILL_ROOT / "templates"
REVIEWER_SH = SCRIPTS / "skill-reviewer.sh"

# Loom and secure-llm live in sibling skills.
LOOM_ROOT  = Path.home() / ".kiro" / "skills" / "home" / "loom"
LOOM_SH    = LOOM_ROOT / "scripts" / "loom.sh"
SECURE_LLM_TEMPLATES = (
    Path.home() / ".kiro" / "skills" / "home" / "secure-llm" / "templates"
)

# Resolved at plan time so `{% extends %}` works for per-check
# templates that inherit `_meta/check.j2`, plus secure-llm
# imports.
SEARCH_PATHS = [
    str(TEMPLATES),
    str(TEMPLATES / "checks"),
    str(TEMPLATES / "checks" / "_meta"),
    str(SECURE_LLM_TEMPLATES),
]


# Reference files owned by skill-builder. The check tasks
# fs_read these at runtime so skill-builder remains the single
# source of truth for authoring conventions.
_BUILDER_REFS_DIR = (
    Path.home() / ".kiro" / "skills" / "home"
    / "skill-builder" / "references"
)


def _builder_ref(name: str) -> str:
    """Absolute path to a skill-builder reference file."""
    return str(_BUILDER_REFS_DIR / name)


def _check_vars() -> dict:
    """Common vars for every check-* agent task."""
    return {
        "skill_dir":            "${task:locate:skill_dir}",
        "skill_name":           "${task:locate:name}",
        "skill_type":           "${task:locate:type}",
        "lint_false_positives": "${task_path:lint}",
        "loom_sh":              str(LOOM_SH),
    }


def _check_task(task_id: str, template_name: str,
                reference_path: str | None = None,
                when: str | None = None):
    """Build a check-* agent task."""
    vars_ = _check_vars()
    if reference_path is not None:
        vars_["reference_path"] = reference_path
    kw = dict(
        template=str(TEMPLATES / "checks" / template_name),
        depends_on=["locate", "lint"],
        output_schema=str(SCHEMAS / "findings.yaml"),
        vars=vars_,
        template_search_paths=SEARCH_PATHS,
    )
    if when is not None:
        kw["when"] = when
    return agent(task_id, **kw)


def derive_plan(name: str, category: str | None) -> LoomPlan:
    """Build the full loom plan for a skill review run."""
    locate_cmd = [
        str(REVIEWER_SH), "pipeline", "locate",
        "--name", name,
    ]
    if category:
        locate_cmd += ["--category", category]

    tasks = [
        # 1. Discover skill metadata.
        tool("locate",
             cmd=locate_cmd,
             output_schema=str(SCHEMAS / "locate.yaml")),

        # 2. Run automated lint (in parallel with check-* below).
        tool("lint",
             cmd=[str(REVIEWER_SH), "pipeline", "lint",
                  "${task:locate:skill_dir}"],
             depends_on=["locate"],
             output_schema=str(SCHEMAS / "findings.yaml")),

        # 3. Always-applied semantic checks.
        _check_task("check-conventions", "conventions.j2",
                    _builder_ref("conventions.md")),
        _check_task("check-model-aware", "model-aware.j2",
                    _builder_ref("model-aware-authoring.md")),
        _check_task("check-patterns", "patterns.j2",
                    _builder_ref("patterns.md")),

        # 4. Type-specific checks (3 of 4 auto-skipped).
        _check_task("check-interface", "interface.j2",
                    _builder_ref("interface-conventions.md"),
                    when="task.\"locate\".type == 'interface'"),
        _check_task("check-tool", "tool.j2",
                    _builder_ref("tool-conventions.md"),
                    when="task.\"locate\".type == 'tool'"),
        _check_task("check-workflow", "workflow.j2",
                    _builder_ref("workflow-conventions.md"),
                    when="task.\"locate\".type == 'workflow'"),
        _check_task("check-reference", "reference.j2",
                    _builder_ref("reference-conventions.md"),
                    when="task.\"locate\".type == 'reference'"),

        # 5. Cross-skill manual check (rules inlined in template).
        _check_task("check-manual", "manual.j2"),

        # 6. Assemble report.
        tool("assemble",
             cmd=[str(REVIEWER_SH), "pipeline", "assemble",
                  "--workdir", "${workdir}",
                  "--locate", "${task_path:locate}",
                  "--lint",   "${task_path:lint}",
                  "--check",  "${task_path:check-conventions}",
                  "--check",  "${task_path:check-model-aware}",
                  "--check",  "${task_path:check-patterns}",
                  "--check",  "${task_path:check-interface}",
                  "--check",  "${task_path:check-tool}",
                  "--check",  "${task_path:check-workflow}",
                  "--check",  "${task_path:check-reference}",
                  "--check",  "${task_path:check-manual}"],
             depends_on=[
                 "lint",
                 "check-conventions", "check-model-aware",
                 "check-patterns",
                 "check-interface", "check-tool",
                 "check-workflow", "check-reference",
                 "check-manual",
             ],
             output_schema=str(SCHEMAS / "assemble.yaml")),

        # 7. Human review gate.
        human("gate",
              template=str(TEMPLATES / "report.md.j2"),
              template_search_paths=SEARCH_PATHS,
              depends_on=["assemble"],
              output_schema=str(SCHEMAS / "gate.yaml"),
              vars={"report_path": "${task:assemble:report_path}"}),

        # 8. Finalize — surface terminal status.
        tool("finalize",
             cmd=[str(REVIEWER_SH), "pipeline", "finalize",
                  "--workdir", "${workdir}"],
             depends_on=["gate"],
             output_schema=str(SCHEMAS / "assemble.yaml")),
    ]

    return make_plan(*tasks)
