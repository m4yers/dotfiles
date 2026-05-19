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

# secure-llm is a sibling skill that hosts the heuristic security
# scanner and the ``security-frame.md.j2`` LLM preamble. We invoke
# its CLI wrapper as a tool task; ``SKILLS`` env var override the
# default location for non-standard layouts.
import os
_SKILLS_HOME = Path(os.environ.get(
    "SKILLS", str(Path.home() / ".kiro/skills")))
SECURITY_SCAN_SH = str(
    _SKILLS_HOME / "home/secure-llm/scripts/security-scan.sh")


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
            "cmd":  [SECURITY_SCAN_SH,
                     "${task:convert:converted_path}"],
            "depends_on": ["convert"],
        },
        {
            "id":    "classify",
            "kind":  "agent",
            "agent": "curator-extractor",
            "template": "classify",
            "judge": {
                "agent":    "curator-judge",
                "template": "classify",
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
            "judge": {
                "agent":    "curator-judge",
                "template": kind,
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
            "judge": {
                "agent":    "curator-judge",
                "template": "summary",
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
            "id":   "vault-match",
            "kind": "tool",
            "cmd":  match_args,
            "depends_on": [f"extract-{k}" for k in matchable_kinds],
        }

    # Per-kind paths the synthesis agent and build-replica iterate.
    # Built by the engine context (peers / upstream / destinations);
    # nothing to plumb at the plan layer.

    tail_tasks = [
        # Build the workdir replica — one atomic page per item.
        # Reads each extract-<kind>/output.yaml directly; vault-
        # match supplies alias hits. Synthesis pages are NOT built
        # here.
        {
            "id":   "build-replica",
            "kind": "tool",
            "cmd":  [CURATOR_SH, "vault", "replica", "build", workdir],
            "depends_on": extract_task_ids + ["classify"]
                            + (["vault-match"] if vault_match_task
                                                else []),
        },
        # Synthesis. Authors 1–2 wiki hub pages and writes them
        # DIRECTLY into the replica via ``fs_write``. Output.yaml
        # carries only the list of paths the agent wrote
        # (apply-replica picks them up by walking the replica
        # filesystem). The agent reads upstream task outputs
        # via the schema render context (peers / upstream /
        # destinations / templates) — no plan-time vars plumbing.
        {
            "id":    "synthesis",
            "kind":  "agent",
            "agent": "curator-composer",
            "template": "synthesis",
            "judge": {
                "agent":    "curator-judge",
                "template": "synthesis",
            },
            "depends_on": ["build-replica"],
        },
        # Render the gate operator's overview ``_REPORT.md`` into
        # the replica root. Pulls verbatim summary + per-kind item
        # counts + synthesis-page paths so the gate has one
        # scannable document to read before drilling into files.
        {
            "id":   "report",
            "kind": "tool",
            "cmd":  [CURATOR_SH, "vault", "report", workdir],
            "depends_on": ["synthesis"],
        },
        # Human gate — orchestrator drives editor with diffs for
        # modified files and plain views for new files. Output:
        # ``{proceed: true|false}``.
        {
            "id":   "gate",
            "kind": "human",
            "metadata": {"replica_dir": "vault-replica"},
            "depends_on": ["report"],
        },
        # Apply the (possibly user-edited) replica to the vault.
        # Files the user deleted between build and apply are
        # skipped with ``user_deleted`` reason. Synthesis pages
        # under ``21 SYNTHESIS/`` are validated + applied even
        # though the build-replica manifest doesn't list them.
        {
            "id":   "apply-replica",
            "kind": "tool",
            "cmd":  [CURATOR_SH, "vault", "replica", "apply", workdir],
            "depends_on": ["gate"],
        },
    ]

    return (
        extract_tasks
        + ([vault_match_task] if vault_match_task else [])
        + tail_tasks
    )
