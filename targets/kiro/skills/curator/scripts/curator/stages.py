"""Stage construction — curator-specific plan factories.

Two pure functions, no CLI:

* ``build_stage1_plan(wd, origin)``  →  Plan
  Stage 1 is content-agnostic: fetch → convert → load_context +
  classify. The classify task is the stage transition trigger.
  Curator's runtime detects it on `complete` and calls
  `run.extend(build_stage2_plan(...))`.

* ``build_stage2_plan(wd, quintet)``  →  Plan
  Reads the classifier's quintet, computes the extractor union
  from the quintet rule table, returns the Stage 2 task subgraph
  (extractors → compose → merge_issues → render_report → gate →
  materialize → apply_plan → verify_batch → commit).

Each agent task runs exactly once (no retries). The agent writes
its result to ``<task_workdir>/output.yaml`` directly; the paired
judge writes a verdict to ``<task_workdir>/verdict.yaml``. The
orchestrator reads verdict.yaml to surface DONE_WITH_CONCERNS
status to the user but always advances via ``curator.sh complete``.

Static path placeholders (``${workdir}``, ``${task_workdir}``) are
resolved at plan-build time and baked into ``cmd`` arrays as
absolute paths. Engine's runtime resolver only handles dynamic
``${task:<id>:<dotpath>}`` placeholders that depend on upstream
outputs.
"""
from __future__ import annotations

from pathlib import Path

from engine.models import Plan, Task

from curator import quintet as q_mod


# Resolved at plan-build time to the absolute curator.sh path.
CURATOR_SH = str(Path(__file__).resolve().parent.parent / "curator.sh")


# ── stage1 ───────────────────────────────────────────────────────


def build_stage1_plan(wd: Path | str, origin: str) -> Plan:
    """Build the stage1 plan as a Plan instance.

    No I/O — does not write plan.yaml. Caller (engine) writes it.
    """
    return Plan(tasks=[Task.from_dict(t) for t in _stage1_tasks(wd, origin)])


def _stage1_tasks(wd: Path | str, origin: str) -> list[dict]:
    """Stage 1 DAG — content-agnostic, always the same shape."""
    return [
        {
            "id":   "fetch",
            "kind": "tool",
            "cmd":  [CURATOR_SH, "source", "fetch", origin],
            "depends_on": [],
        },
        {
            "id":   "convert",
            "kind": "tool",
            "cmd":  [CURATOR_SH, "source", "convert",
                     "${task:fetch:path}",
                     "--task-workdir", "${task_workdir}"],
            "depends_on": ["fetch"],
        },
        {
            "id":   "security_scan",
            "kind": "tool",
            "cmd":  [CURATOR_SH, "security-scan",
                     "${task:convert:converted_path}"],
            "depends_on": ["convert"],
        },
        {
            "id":    "classify",
            "kind":  "agent",
            "agent": "curator-extractor",
            "template": "classify",
            "vars": {
                "source_text_path":   "${task:convert:converted_path}",
                "container_metadata": "${task:convert:metadata}",
            },
            "judge": {
                "agent":    "curator-judge",
                "template": "classify",
                "vars": {
                    "source_text_path": "${task:convert:converted_path}",
                },
            },
            "depends_on": ["convert", "security_scan"],
            # Declarative stage transition: when classify completes,
            # runtime imports build_stage2_plan and calls
            # ``build_stage2_plan(workdir, output["quintet"])``,
            # appending the result via ``run.extend``. Adding new
            # stages adds a metadata.transition; runtime stays stage-
            # blind.
            "metadata": {
                "transition": {
                    "factory":     "curator.stages:build_stage2_plan",
                    "input_field": "quintet",
                },
            },
        },
    ]


# ── stage2 ───────────────────────────────────────────────────────


def build_stage2_plan(wd: Path | str, quintet: dict) -> Plan:
    """Build the stage2 plan extension.

    Called by runtime as a transition factory:
    ``build_stage2_plan(workdir, output["quintet"])``. Accepts
    ``quintet`` positionally so the runtime contract stays simple.
    """
    q_mod.validate_quintet(quintet)
    extractor_kinds = q_mod.extractors_for(quintet)
    new_tasks = _stage2_tasks(wd, extractor_kinds)
    return Plan(tasks=[Task.from_dict(t) for t in new_tasks])


def _stage2_tasks(wd: Path | str, extractor_kinds: list[str]) -> list[dict]:
    """Stage 2 DAG: N extractors → compose → tail (apply chain)."""
    extract_task_ids = [f"extract-{kind}" for kind in extractor_kinds]
    workdir = str(wd)

    # Summary runs LAST among extractors so it can incorporate the
    # other extractors' outputs. Pull it out of the parallel batch.
    summary_id = "extract-summary"
    parallel_extractor_kinds = [k for k in extractor_kinds if k != "summary"]
    parallel_extract_ids = [f"extract-{k}" for k in parallel_extractor_kinds]

    parallel_extract_tasks = [
        {
            "id":    f"extract-{kind}",
            "kind":  "agent",
            "agent": "curator-extractor",
            "template": kind,
            "vars": {
                "source_text_path":  "${task:convert:converted_path}",
                "container_metadata": "${task:convert:metadata}",
                "source_vault_path": "${task:fetch:path}",
                "quintet":           "${task:classify:quintet}",
                "topic":             "${task:classify:topic}",
            },
            "judge": {
                "agent":    "curator-judge",
                "template": kind,
                "vars": {
                    "source_text_path":   "${task:convert:converted_path}",
                    "container_metadata": "${task:convert:metadata}",
                    "quintet":            "${task:classify:quintet}",
                    "topic":              "${task:classify:topic}",
                },
            },
            "depends_on": ["classify", "convert"],
        }
        for kind in parallel_extractor_kinds
    ]

    # Summary task — depends on all parallel extractors so it can
    # read their output.yaml files and synthesize a rich summary.
    summary_task: dict | None = None
    if "summary" in extractor_kinds:
        summary_task = {
            "id":    summary_id,
            "kind":  "agent",
            "agent": "curator-extractor",
            "template": "summary",
            "vars": {
                "source_text_path":   "${task:convert:converted_path}",
                "container_metadata": "${task:convert:metadata}",
                "quintet":            "${task:classify:quintet}",
                "topic":              "${task:classify:topic}",
                "upstream_outputs": {
                    k: f"${{task_path:extract-{k}}}"
                    for k in parallel_extractor_kinds
                },
                # Per-extractor judge verdicts. Lets summary down-weight
                # or skip kinds whose extractor was REJECTed by its judge.
                "upstream_verdicts": {
                    k: f"${{verdict_path:extract-{k}}}"
                    for k in parallel_extractor_kinds
                },
            },
            "judge": {
                "agent":    "curator-judge",
                "template": "summary",
                "vars": {
                    "source_text_path":   "${task:convert:converted_path}",
                    "container_metadata": "${task:convert:metadata}",
                    "quintet":            "${task:classify:quintet}",
                    "topic":              "${task:classify:topic}",
                },
            },
            "depends_on": parallel_extract_ids + ["classify", "convert"],
        }

    extract_tasks = parallel_extract_tasks + (
        [summary_task] if summary_task else [])

    # Vault matching — runs after parallel extractors; reads each
    # extractor output and finds existing vault pages by name.
    matchable_kinds = [k for k in parallel_extractor_kinds
                         if k in ("keywords", "people", "models")]
    vault_match_task: dict | None = None
    if matchable_kinds:
        match_args = [CURATOR_SH, "vault", "match"]
        for k in matchable_kinds:
            match_args += [f"--{k}", f"${{task_path:extract-{k}}}"]
        vault_match_task = {
            "id":   "vault_match",
            "kind": "tool",
            "cmd":  match_args,
            "depends_on": [f"extract-{k}" for k in matchable_kinds],
        }

    compose_task = {
        "id":    "compose",
        "kind":  "agent",
        "agent": "curator-composer",
        "template": "compose",
        "vars": {
            "source_text_path": "${task:convert:converted_path}",
            "quintet":          "${task:classify:quintet}",
            "topic":            "${task:classify:topic}",
            "workdir":          workdir,
            "extract_kinds":    extractor_kinds,
            "upstream_outputs": {
                k: f"${{task_path:extract-{k}}}"
                for k in extractor_kinds
            },
            # Judge verdicts for every upstream agent task. Composer uses
            # these to populate `failed_kinds` (verdict==REJECT) and to
            # inherit upstream issues into the composed `issues` array.
            "upstream_verdicts": {
                **{
                    k: f"${{verdict_path:extract-{k}}}"
                    for k in extractor_kinds
                },
                "classify": "${verdict_path:classify}",
            },
            "vault_match_path": "${task_path:vault_match}",
        },
        "judge": {
            "agent":    "curator-judge",
            "template": "compose",
            "vars": {
                "source_text_path": "${task:convert:converted_path}",
                "quintet":          "${task:classify:quintet}",
                "workdir":          workdir,
                "extract_kinds":    extractor_kinds,
                "upstream_outputs": {
                    k: f"${{task_path:extract-{k}}}"
                    for k in extractor_kinds
                },
                # Same verdict map for the judge so it can validate that
                # `failed_kinds` matches the actual REJECT set.
                "upstream_verdicts": {
                    **{
                        k: f"${{verdict_path:extract-{k}}}"
                        for k in extractor_kinds
                    },
                    "classify": "${verdict_path:classify}",
                },
                "vault_match_path": "${task_path:vault_match}",
            },
        },
        "depends_on": extract_task_ids + ["classify", "convert"]
                        + (["vault_match"] if vault_match_task else []),
    }

    tail_tasks = [
        {
            "id":   "render_report",
            "kind": "tool",
            "cmd":  [CURATOR_SH, "report", "render", workdir],
            "depends_on": ["compose"],
        },
        {
            "id":   "gate",
            "kind": "human",
            "metadata": {"report_from_task": "render_report"},
            "depends_on": ["render_report"],
        },
        {
            "id":   "materialize",
            "kind": "tool",
            "cmd":  [CURATOR_SH, "vault", "page", "materialize",
                     "${task:gate:approved_path}"],
            "depends_on": ["gate"],
        },
        {
            "id":   "apply_plan",
            "kind": "tool",
            "cmd":  [CURATOR_SH, "vault", "page", "apply-plan",
                     "${task:materialize:plan_path}"],
            "depends_on": ["materialize"],
        },
        {
            "id":   "verify_batch",
            "kind": "tool",
            "cmd":  [CURATOR_SH, "vault", "page", "verify-batch",
                     "${task:gate:approved_path}"],
            "depends_on": ["apply_plan"],
        },
        {
            "id":   "commit",
            "kind": "tool",
            "cmd":  [CURATOR_SH, "vault", "commit",
                     "ingest: ${task:fetch:basename}"],
            "depends_on": ["verify_batch"],
        },
    ]

    return (
        extract_tasks
        + ([vault_match_task] if vault_match_task else [])
        + [compose_task]
        + tail_tasks
    )
