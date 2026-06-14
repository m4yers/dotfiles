"""Build the loom plan for a dojo run.

Three pipelines, each declared as a flat task list. The audit
core (check-autochecks → check-* → checks-report → skill-modify) is
duplicated between create and update by design — every check
task is named explicitly per pipeline so review-only or
create-only checks stay surface-visible.

Pipelines:

- `create` — gather → check-name/location/overlaps → design →
  design-review (loop) → skill-materialize → find-skill →
  audit-core → skill-modify → final-review → summary. Includes
  the create-only `check-design` task. The `design-review` gate
  is a while-loop latch back to `design`: a `revise` verdict
  re-runs the design with the gate's feedback; `accept` exits.
- `update` — find-skill (landscape) → gather-update →
  modify-changes → audit-core → skill-modify → final-review →
  summary.
- `review` — find-skill (--name) → audit-core (no modify) →
  gate → finalize.

Locate shape: every pipeline feeds `checks-report` a
locate-shaped `{skill_dir, name, category, type}` source —
`find-skill --name` for create/review, `gather-update` for
update (its picked-skill fields). There is no separate
`synth-locate` adapter.

Maintenance contract: when a new check is added to one
pipeline, it MUST be added to the others as well unless the
check is intentionally pipeline-specific (like `check-design`,
which exists only in `create`).
"""
from __future__ import annotations

from pathlib import Path

from loom import LoomPlan, agent, human, latch, make_plan, tool

from dojo.tasks import (
    check_overlaps, check_name, check_location, check_naming,
    find_skill, render_design, summary,
)

# Path layout: <skill>/scripts/dojo/dojo/plan.py — parents[3] is
# the skill directory.
SKILL_ROOT = Path(__file__).resolve().parents[3]
PROMPTS    = SKILL_ROOT / "templates" / "prompts"
CHECKS     = SKILL_ROOT / "templates" / "checks"
TEMPLATES  = SKILL_ROOT / "templates"
SCHEMAS    = SKILL_ROOT / "schemas"
SCRIPTS    = SKILL_ROOT / "scripts"
DOJO_SH    = SCRIPTS / "dojo.sh"
REFERENCES = SKILL_ROOT / "references"

# Loom and secure-llm live in sibling skills.
LOOM_SH = (
    Path.home() / ".kiro" / "skills" / "home"
    / "loom" / "scripts" / "loom.sh"
)
SECURE_LLM_TEMPLATES = (
    Path.home() / ".kiro" / "skills" / "home"
    / "secure-llm" / "templates"
)

# Search paths for Jinja {% extends %} / {% include %} —
# resolved at plan time so per-check templates that inherit
# `_meta/check.j2` and design.md.j2 that includes
# `<type>-conventions.md` work without manual fs_read.
SEARCH_PATHS = [
    str(TEMPLATES),
    str(PROMPTS),
    str(CHECKS),
    str(CHECKS / "_meta"),
    str(REFERENCES),
    str(SECURE_LLM_TEMPLATES),
]


# ---------------------------------------------------------------------------
# Helpers — agent / human factories with consistent search paths
# ---------------------------------------------------------------------------

def _agent(id_: str, template: str, schema: str,
           deps: list[str] | None = None,
           when: str | None = None,
           vars_: dict | None = None,
           prompts_dir: Path = PROMPTS,
           latch_: dict | None = None):
    return agent(
        id_,
        template=str(prompts_dir / template),
        output_schema=str(SCHEMAS / schema),
        depends_on_all=list(deps) if deps else None,
        when=when,
        vars=vars_ or {},
        template_search_paths=SEARCH_PATHS,
        latch=latch_,
    )


def _human(id_: str, template: str, schema: str,
           deps: list[str] | None = None,
           vars_: dict | None = None,
           prompts_dir: Path = PROMPTS,
           latch_: dict | None = None):
    return human(
        id_,
        template=str(prompts_dir / template),
        output_schema=str(SCHEMAS / schema),
        depends_on_all=list(deps) if deps else None,
        vars=vars_ or {},
        template_search_paths=SEARCH_PATHS,
        latch=latch_,
    )


# ---------------------------------------------------------------------------
# Audit core — check-autochecks + check-* + checks-report.
#
# The vars dict tells each check task where the skill being
# audited lives. Different pipelines source these vars from
# different upstream tasks (all locate-shaped):
#
#   create  → ${task:find-skill:skill_dir|name|type}
#   update  → ${task:gather-update:skill_dir|name|type}
#   review  → ${task:find-skill:skill_dir|name|type}
#
# Every check task depends_on check-autochecks so the lint output is
# available as `lint_false_positives` (the agent skips items
# the linter already flagged).
# ---------------------------------------------------------------------------

def _check_vars(skill_dir_ref: str, skill_name_ref: str,
                skill_type_ref: str) -> dict:
    return {
        "skill_dir":            skill_dir_ref,
        "skill_name":           skill_name_ref,
        "skill_type":           skill_type_ref,
        "lint_false_positives": "${task_path:check-autochecks}",
        "loom_sh":              str(LOOM_SH),
    }


def _check_task(task_id: str, template_name: str,
                base_vars: dict,
                lint_dep: str = "check-autochecks",
                extra_deps: list[str] | None = None,
                when: str | None = None):
    """Build a check-* agent task with shared base vars."""
    deps = [lint_dep] + list(extra_deps or [])
    return agent(
        task_id,
        template=str(CHECKS / template_name),
        output_schema=str(SCHEMAS / "findings.yaml"),
        depends_on_all=deps,
        vars=base_vars,
        template_search_paths=SEARCH_PATHS,
        when=when,
    )


def _audit_tasks(skill_dir_ref: str, skill_name_ref: str,
                 skill_type_ref: str, lint_dep_extras: list[str]):
    """check-autochecks + every check-* task. Caller appends checks-report.

    `lint_dep_extras` are tasks the check-autochecks task itself
    depends on (e.g. `skill-materialize`/`find-skill` for create,
    `modify-changes` for update, `find-skill` for review).
    """
    base_vars = _check_vars(
        skill_dir_ref, skill_name_ref, skill_type_ref)

    lint_task = tool(
        "check-autochecks",
        cmd=[str(DOJO_SH), "pipeline", "autochecks", skill_dir_ref],
        depends_on_all=lint_dep_extras,
        output_schema=str(SCHEMAS / "findings.yaml"),
    )

    checks = [
        _check_task("check-authoring",    "authoring.j2",
                    base_vars),
        _check_task("check-model-awareness", "model-awareness.j2",
                    base_vars),
        _check_task("check-scripts",      "scripts.j2",
                    base_vars),
        _check_task("check-interface",    "interface.j2",
                    base_vars,
                    when=f"{skill_type_ref} == 'interface'"),
        _check_task("check-tool",         "tool.j2",
                    base_vars,
                    when=f"{skill_type_ref} == 'tool'"),
        _check_task("check-workflow",     "workflow.j2",
                    base_vars,
                    when=f"{skill_type_ref} == 'workflow'"),
        _check_task("check-reference",    "reference.j2",
                    base_vars,
                    when=f"{skill_type_ref} == 'reference'"),
    ]
    return [lint_task] + checks, base_vars


def _all_check_ids(extra: list[str] | None = None) -> list[str]:
    base = [
        "check-authoring",
        "check-model-awareness", "check-scripts",
        "check-interface", "check-tool",
        "check-workflow", "check-reference",
    ]
    return base + list(extra or [])


def _assemble_task(check_ids: list[str], locate_ref: str):
    """checks-report task. `locate_ref` is a path to a YAML file
    with the locate-shaped fields {skill_dir, name, category,
    type}. Every pipeline points this at a task that already
    emits that shape (find-skill or gather-update); there is no
    separate synth-locate adapter.
    """
    cmd = [
        str(DOJO_SH), "pipeline", "assemble",
        "--workdir", "${workdir}",
        "--locate",  locate_ref,
        "--autochecks",    "${task_path:check-autochecks}",
    ]
    for cid in check_ids:
        cmd += ["--check", "${task_path:" + cid + "}"]

    return tool(
        "checks-report",
        cmd=cmd,
        depends_on_all=["check-autochecks"],
        depends_on_any=check_ids,
        output_schema=str(SCHEMAS / "checks_report.yaml"),
    )


# ---------------------------------------------------------------------------
# Pipeline builders
# ---------------------------------------------------------------------------

def build_create_plan(workdir: Path, name: str) -> LoomPlan:
    """Create pipeline: design-led skill authoring.

    `find-skill --name` runs after `skill-materialize` (the
    skill now exists on disk) to produce the locate shape that
    `check-autochecks`, the checks, and `checks-report` consume.
    """
    skill_dir_ref = "${task:find-skill:skill_dir}"
    name_ref      = "${task:find-skill:name}"
    type_ref      = "${task:find-skill:type}"

    base_vars = _check_vars(skill_dir_ref, name_ref, type_ref)

    audit_tasks, _ = _audit_tasks(
        skill_dir_ref, name_ref, type_ref,
        lint_dep_extras=["find-skill"],
    )

    # check-design is exclusive to create — verifies each design
    # point survived materialization.
    design_check = _check_task(
        "check-design", "design.j2",
        {**base_vars,
         "design_path": "${task_path:design-review}"},
        lint_dep="check-autochecks",
    )

    check_ids = _all_check_ids(extra=["check-design"])

    return make_plan(
        # 1. Human gather — capture name, type, intent.
        _human("gather", "gather.md.j2", "gather.yaml"),

        # 2. Pre-design tool checks (parallel).
        check_name.task(workdir,     depends_on_all=["gather"]),
        check_location.task(workdir, depends_on_all=["gather"]),
        check_overlaps.task(workdir, depends_on_all=["gather"]),

        # 3. Design phase. On a design-review `revise` verdict the
        # latch re-runs this task; it reads the gate's feedback
        # from the bare (latest-completed) revise_reason ref.
        _agent("design", "design.md.j2", "design.yaml",
               deps=["check-name", "check-location",
                     "check-overlaps"],
               vars_={"revise_reason":
                      "${task:design-review:revise_reason}"}),
        # 3b. Render design YAML as readable markdown for the
        # design-review gate (tool task `design-render`).
        render_design.task(depends_on_all=["design"]),
        # 3c. Deterministic naming check `design-checks` — gates
        # design-review so bad names abort before the human
        # reviews and before materialization.
        check_naming.task(depends_on_all=["design"]),
        # 3d. Human gate with a while-loop latch back to `design`:
        # `revise` loops, `accept` exits.
        _human("design-review", "design_review.md.j2",
               "design.yaml",
               deps=["design", "design-render", "design-checks"],
               latch_=latch(
                   "design",
                   while_="${task:design-review:decision} == 'revise'")),

        # 4. Materialize — write SKILL.md + refs + scripts.
        _agent("skill-materialize", "skill_materialize.md.j2", "files.yaml",
               deps=["design-review"]),

        # 5. Locate the just-created skill on disk (canonical
        # locate shape for audit core).
        find_skill.task_named(
            workdir, name, depends_on_all=["skill-materialize"]),

        # 6. Audit core (check-autochecks + checks + design check).
        *audit_tasks,
        design_check,

        # 7. Assemble report.
        _assemble_task(check_ids, "${task_path:find-skill}"),

        # 8. Apply findings.
        _agent("skill-modify", "skill_modify.md.j2", "files.yaml",
               deps=["checks-report"],
               vars_={"report_path":
                      "${task:checks-report:report_path}",
                      "skill_dir":   skill_dir_ref}),

        # 9. Final human gate.
        _human("final-review", "final_review.md.j2",
               "decision.yaml", deps=["skill-modify"]),

        # 10. Summary.
        summary.task(workdir, depends_on_all=["final-review"]),
    )


def build_update_plan(workdir: Path, name: str) -> LoomPlan:
    """Update pipeline: pick a skill, apply user-described
    change, then audit-core.

    The locate shape comes from `gather-update`, whose picked
    skill carries `{skill_dir, name, category, type}` straight
    from the find-skill landscape — no separate locate task.
    """
    skill_dir_ref = "${task:gather-update:skill_dir}"
    name_ref      = "${task:gather-update:name}"
    type_ref      = "${task:gather-update:type}"

    audit_tasks, _ = _audit_tasks(
        skill_dir_ref, name_ref, type_ref,
        lint_dep_extras=["modify-changes"],
    )

    check_ids = _all_check_ids()

    return make_plan(
        # 1. Discover landscape (lister for the picker).
        find_skill.task(workdir),

        # 2. User picks a skill + describes change.
        _human("gather-update", "gather_update.md.j2",
               "gather_update.yaml",
               deps=["find-skill"]),

        # 3. Apply user-described change.
        _agent("modify-changes", "modify_changes.md.j2",
               "files.yaml",
               deps=["gather-update"],
               vars_={"skill_dir":   skill_dir_ref,
                      "description": "${task:gather-update:description}"}),

        # 4. Audit core.
        *audit_tasks,

        # 5. Assemble.
        _assemble_task(check_ids, "${task_path:gather-update}"),

        # 6. Modify based on findings.
        _agent("skill-modify", "skill_modify.md.j2", "files.yaml",
               deps=["checks-report"],
               vars_={"report_path":
                      "${task:checks-report:report_path}",
                      "skill_dir":   skill_dir_ref}),

        # 7. Final human gate.
        _human("final-review", "final_review.md.j2",
               "decision.yaml", deps=["skill-modify"]),

        # 8. Summary.
        summary.task(workdir, depends_on_all=["final-review"]),
    )


def build_review_plan(workdir: Path, name: str) -> LoomPlan:
    """Review pipeline: audit an existing skill, terminate at
    the interactive findings gate. No `skill-modify` task — the
    gate dispatches accept/decline fixes one finding at a time.

    `find-skill --name N` emits the locate shape
    `{skill_dir, name, category, type}` consumed directly by the
    audit core and `checks-report`.
    """
    skill_dir_ref = "${task:find-skill:skill_dir}"
    name_ref      = "${task:find-skill:name}"
    type_ref      = "${task:find-skill:type}"

    audit_tasks, _ = _audit_tasks(
        skill_dir_ref, name_ref, type_ref,
        lint_dep_extras=["find-skill"],
    )

    check_ids = _all_check_ids()

    return make_plan(
        find_skill.task_named(workdir, name),

        *audit_tasks,

        _assemble_task(check_ids, "${task_path:find-skill}"),

        # Fix loop: re-show the report, let the user pick fixes,
        # apply them, and loop while findings remain open. The
        # audit core above runs once; only this tail iterates.
        tool("show-report",
             cmd=[str(DOJO_SH), "pipeline", "show-report",
                  "--workdir", "${workdir}",
                  "--skill-dir", skill_dir_ref],
             depends_on_all=["checks-report"],
             output_schema=str(SCHEMAS / "show_report.yaml")),

        _human("skill-fix-review", "skill_fix_review.md.j2",
               "skill_fix_review.yaml",
               deps=["show-report"],
               vars_={"report_path":
                      "${task:show-report:report_path}"}),

        _agent("skill-fix-apply", "skill_fix_apply.md.j2",
               "skill_fix_apply.yaml",
               deps=["skill-fix-review"],
               vars_={"report_path":
                      "${task:show-report:report_path}",
                      "skill_dir": "${task:show-report:skill_dir}",
                      "dojo_sh":   str(DOJO_SH),
                      "loom_sh":   str(LOOM_SH)},
               latch_=latch(
                   "show-report",
                   while_="${task:skill-fix-apply:open_items} > `0`")),

        tool("finalize",
             cmd=[str(DOJO_SH), "pipeline", "finalize",
                  "--workdir", "${workdir}"],
             depends_on_all=["skill-fix-apply"],
             output_schema=str(SCHEMAS / "checks_report.yaml")),
    )


def derive_plan(op: str, workdir: Path, name: str) -> LoomPlan:
    """Dispatch to the right plan builder."""
    if op == "create":
        return build_create_plan(workdir, name)
    if op == "update":
        return build_update_plan(workdir, name)
    if op == "review":
        return build_review_plan(workdir, name)
    raise ValueError(
        f"unknown op: {op!r}; "
        f"expected 'create', 'update', or 'review'")
