"""Build the loom plan for a dojo run.

Three pipelines, each declared as a flat task list. The audit
core (lint → check-* → assemble → modify) is duplicated between
create and update by design — every check task is named
explicitly per pipeline so review-only or create-only checks
stay surface-visible.

Pipelines:

- `create` — gather → check-name/location/overlaps → design →
  design-review → materialize → audit-core → final-review →
  summary. Includes the create-only `check-design` task.
- `update` — find-skill → gather-update → modify-changes →
  audit-core → final-review → summary.
- `review` — find-skill (--name) → audit-core (no modify) →
  gate → finalize.

Maintenance contract: when a new check is added to one
pipeline, it MUST be added to the others as well unless the
check is intentionally pipeline-specific (like `check-design`,
which exists only in `create`).
"""
from __future__ import annotations

from pathlib import Path

from loom import LoomPlan, agent, human, make_plan, tool

from dojo.tasks import (
    check_overlaps, check_name, check_location,
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
           prompts_dir: Path = PROMPTS):
    return agent(
        id_,
        template=str(prompts_dir / template),
        output_schema=str(SCHEMAS / schema),
        depends_on_all=list(deps) if deps else None,
        when=when,
        vars=vars_ or {},
        template_search_paths=SEARCH_PATHS,
    )


def _human(id_: str, template: str, schema: str,
           deps: list[str] | None = None,
           vars_: dict | None = None,
           prompts_dir: Path = PROMPTS):
    return human(
        id_,
        template=str(prompts_dir / template),
        output_schema=str(SCHEMAS / schema),
        depends_on_all=list(deps) if deps else None,
        vars=vars_ or {},
        template_search_paths=SEARCH_PATHS,
    )


# ---------------------------------------------------------------------------
# Audit core — lint + check-* + assemble.
#
# The vars dict tells each check task where the skill being
# audited lives. Different pipelines source these vars from
# different upstream tasks:
#
#   create  → ${task:materialize:skill_dir} / ${task:gather:name} / ${task:gather:type}
#   update  → ${task:gather-update:path}    / ${task:gather-update:name} / ${task:gather-update:type}
#   review  → ${task:find-skill:path}       / ${task:find-skill:name}    / ${task:find-skill:type}
#
# Every check task depends_on lint so the lint output is
# available as `lint_false_positives` (the agent skips items
# the linter already flagged).
# ---------------------------------------------------------------------------

def _check_vars(skill_dir_ref: str, skill_name_ref: str,
                skill_type_ref: str) -> dict:
    return {
        "skill_dir":            skill_dir_ref,
        "skill_name":           skill_name_ref,
        "skill_type":           skill_type_ref,
        "lint_false_positives": "${task_path:lint}",
        "loom_sh":              str(LOOM_SH),
    }


def _check_task(task_id: str, template_name: str,
                base_vars: dict,
                lint_dep: str = "lint",
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
    """Lint + every check-* task. Caller appends assemble.

    `lint_dep_extras` are tasks the lint task itself depends on
    (e.g. `materialize` for create, `gather-update` for update,
    `find-skill` for review).
    """
    base_vars = _check_vars(
        skill_dir_ref, skill_name_ref, skill_type_ref)

    lint_task = tool(
        "lint",
        cmd=[str(DOJO_SH), "pipeline", "lint", skill_dir_ref],
        depends_on_all=lint_dep_extras,
        output_schema=str(SCHEMAS / "findings.yaml"),
    )

    checks = [
        _check_task("check-conventions",  "conventions.j2",
                    base_vars),
        _check_task("check-model-aware",  "model-aware.j2",
                    base_vars),
        _check_task("check-patterns",     "patterns.j2",
                    base_vars),
        _check_task("check-scripts",      "scripts.j2",
                    base_vars),
        _check_task("check-interface",    "interface.j2",
                    base_vars,
                    when="vars.skill_type == 'interface'"),
        _check_task("check-tool",         "tool.j2",
                    base_vars,
                    when="vars.skill_type == 'tool'"),
        _check_task("check-workflow",     "workflow.j2",
                    base_vars,
                    when="vars.skill_type == 'workflow'"),
        _check_task("check-reference",    "reference.j2",
                    base_vars,
                    when="vars.skill_type == 'reference'"),
    ]
    return [lint_task] + checks, base_vars


def _all_check_ids(extra: list[str] | None = None) -> list[str]:
    base = [
        "check-conventions", "check-model-aware",
        "check-patterns", "check-scripts",
        "check-interface", "check-tool",
        "check-workflow", "check-reference",
    ]
    return base + list(extra or [])


def _assemble_task(check_ids: list[str], locate_ref: str | None):
    """Assemble task. `locate_ref` is a path to a YAML file
    with the locate-shaped fields {skill_dir, name, category,
    type}. Pipelines that don't have a real `locate` task
    write a synthetic one as a tool task that emits the same
    shape from their upstream metadata.
    """
    cmd = [
        str(DOJO_SH), "pipeline", "assemble",
        "--workdir", "${workdir}",
        "--locate",  locate_ref,
        "--lint",    "${task_path:lint}",
    ]
    for cid in check_ids:
        cmd += ["--check", "${task_path:" + cid + "}"]

    return tool(
        "assemble",
        cmd=cmd,
        depends_on_all=["lint"] + check_ids,
        output_schema=str(SCHEMAS / "assemble.yaml"),
    )


# ---------------------------------------------------------------------------
# Synthetic locate emitters — assemble needs locate.yaml-shaped
# input. Create/update pipelines don't have a `locate` task so
# we construct one from upstream task data.
# ---------------------------------------------------------------------------

def _emit_locate_tool(task_id: str,
                      *,
                      name_ref: str,
                      type_ref: str,
                      depends_on: list[str],
                      skill_dir_ref: str | None = None,
                      location_ref: str | None = None):
    """Tool task that writes a locate.yaml-shaped file from
    upstream refs. Pass either `skill_dir_ref` (path) OR
    `location_ref` (namespace; combined with `name_ref` to
    derive the path).
    """
    if (skill_dir_ref is None) == (location_ref is None):
        raise ValueError(
            "exactly one of skill_dir_ref or location_ref required")

    cmd = [
        str(DOJO_SH), "pipeline", "synth-locate",
        "--name", name_ref,
        "--type", type_ref,
    ]
    if skill_dir_ref:
        cmd += ["--skill-dir", skill_dir_ref]
    else:
        cmd += ["--location", location_ref]

    return tool(
        task_id,
        cmd=cmd,
        depends_on_all=depends_on,
        output_schema=str(SCHEMAS / "locate.yaml"),
    )


# ---------------------------------------------------------------------------
# Pipeline builders
# ---------------------------------------------------------------------------

def build_create_plan(workdir: Path, name: str) -> LoomPlan:
    """Create pipeline: design-led skill authoring."""
    # skill_dir is computed by synth-locate from gather.location +
    # gather.name; downstream check tasks read the assembled
    # locate.yaml shape via task refs on synth-locate.
    skill_dir_ref = "${task:synth-locate:skill_dir}"
    name_ref      = "${task:gather:name}"
    type_ref      = "${task:gather:type}"
    location_ref  = "${task:gather:location}"

    base_vars = _check_vars(skill_dir_ref, name_ref, type_ref)

    audit_tasks, _ = _audit_tasks(
        skill_dir_ref, name_ref, type_ref,
        lint_dep_extras=["synth-locate"],
    )

    # check-design is exclusive to create — verifies each design
    # point survived materialization.
    design_check = _check_task(
        "check-design", "design.j2",
        {**base_vars,
         "design_path": "${task_path:design-review}"},
        lint_dep="lint",
    )

    check_ids = _all_check_ids(extra=["check-design"])

    return make_plan(
        # 1. Human gather — capture name, type, intent.
        _human("gather", "gather.md.j2", "gather.yaml"),

        # 2. Pre-design tool checks (parallel).
        check_name.task(workdir,     depends_on_all=["gather"]),
        check_location.task(workdir, depends_on_all=["gather"]),
        check_overlaps.task(workdir, depends_on_all=["gather"]),

        # 3. Design phase.
        _agent("design", "design.md.j2", "design.yaml",
               deps=["check-name", "check-location",
                     "check-overlaps"]),
        # 3b. Render design YAML as readable markdown for the
        # design-review gate. Tool task — no LLM. Output schema
        # exposes report_path that the gate template consumes.
        render_design.task(depends_on_all=["design"]),
        _human("design-review", "design_review.md.j2",
               "design.yaml", deps=["design", "render-design"]),

        # 4. Materialize — write SKILL.md + refs + scripts.
        _agent("materialize", "create.md.j2", "files.yaml",
               deps=["design-review"]),

        # 5. Synth-locate so assemble has uniform input. Skill
        # dir derives from gather.location + gather.name.
        _emit_locate_tool(
            "synth-locate",
            location_ref=location_ref,
            name_ref=name_ref,
            type_ref=type_ref,
            depends_on=["materialize"],
        ),

        # 6. Audit core (lint + checks + design check).
        *audit_tasks,
        design_check,

        # 7. Assemble report.
        _assemble_task(check_ids, "${task_path:synth-locate}"),

        # 8. Apply findings.
        _agent("modify", "modify.md.j2", "files.yaml",
               deps=["assemble"],
               vars_={"report_path": "${task:assemble:report_path}",
                      "skill_dir":   skill_dir_ref}),

        # 9. Final human gate.
        _human("final-review", "final_review.md.j2",
               "decision.yaml", deps=["modify"]),

        # 10. Summary.
        summary.task(workdir, depends_on_all=["final-review"]),
    )


def build_update_plan(workdir: Path, name: str) -> LoomPlan:
    """Update pipeline: pick a skill, apply user-described
    change, then audit-core."""
    skill_dir_ref = "${task:gather-update:path}"
    name_ref      = "${task:gather-update:name}"
    type_ref      = "${task:gather-update:type}"

    audit_tasks, _ = _audit_tasks(
        skill_dir_ref, name_ref, type_ref,
        lint_dep_extras=["synth-locate"],
    )

    check_ids = _all_check_ids()

    return make_plan(
        # 1. Discover landscape.
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

        # 4. Synth-locate for audit core.
        _emit_locate_tool(
            "synth-locate",
            skill_dir_ref=skill_dir_ref,
            name_ref=name_ref,
            type_ref=type_ref,
            depends_on=["modify-changes"],
        ),

        # 5. Audit core.
        *audit_tasks,

        # 6. Assemble.
        _assemble_task(check_ids, "${task_path:synth-locate}"),

        # 7. Modify based on findings.
        _agent("modify", "modify.md.j2", "files.yaml",
               deps=["assemble"],
               vars_={"report_path": "${task:assemble:report_path}",
                      "skill_dir":   skill_dir_ref}),

        # 8. Final human gate.
        _human("final-review", "final_review.md.j2",
               "decision.yaml", deps=["modify"]),

        # 9. Summary.
        summary.task(workdir, depends_on_all=["final-review"]),
    )


def build_review_plan(workdir: Path, name: str) -> LoomPlan:
    """Review pipeline: audit an existing skill, terminate at
    the interactive findings gate. No `modify` task — the gate
    dispatches accept/decline fixes one finding at a time."""
    skill_dir_ref = "${task:find-skill:path}"
    name_ref      = "${task:find-skill:name}"
    type_ref      = "${task:find-skill:type}"

    audit_tasks, _ = _audit_tasks(
        skill_dir_ref, name_ref, type_ref,
        lint_dep_extras=["find-skill"],
    )

    check_ids = _all_check_ids()

    # find-skill --name N produces shape {name, namespace, path,
    # type} which is the locate.yaml shape minus skill_dir/category;
    # synth-locate maps it.
    return make_plan(
        find_skill.task_named(workdir, name),

        _emit_locate_tool(
            "synth-locate",
            skill_dir_ref=skill_dir_ref,
            name_ref=name_ref,
            type_ref=type_ref,
            depends_on=["find-skill"],
        ),

        *audit_tasks,

        _assemble_task(check_ids, "${task_path:synth-locate}"),

        # Interactive gate — user accepts/declines findings via
        # report file edits; gate-decisions parses them.
        human(
            "gate",
            template=str(TEMPLATES / "report.md.j2"),
            template_search_paths=SEARCH_PATHS,
            depends_on_all=["assemble"],
            output_schema=str(SCHEMAS / "gate.yaml"),
            vars={"report_path": "${task:assemble:report_path}"},
        ),

        tool("finalize",
             cmd=[str(DOJO_SH), "pipeline", "finalize",
                  "--workdir", "${workdir}"],
             depends_on_all=["gate"],
             output_schema=str(SCHEMAS / "assemble.yaml")),
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
