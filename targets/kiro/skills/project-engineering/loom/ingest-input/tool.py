"""Entry task for project-engineering: exact-parameter pass-through.

The subgraph contract is precisely the fields the pipeline consumes
— no opaque wrapper object. This skill does not know who produces
them: standalone runs seed them directly; a composing parent graph
wires them from whatever siblings produce compatible fields.
"""

from io_types import IngestInputInput, IngestInputOutput


def ingest_input(inp: IngestInputInput) -> IngestInputOutput:
    return IngestInputOutput(
        build_installed_skills=inp.build_installed_skills,
        build_system=inp.build_system,
        design=inp.design,
        design_note=inp.design_note,
        fallback_build_cmd=inp.fallback_build_cmd,
        fallback_test_cmd=inp.fallback_test_cmd,
        feature_slug=inp.feature_slug,
        reviewer_role_d1=inp.reviewer_role_d1,
        reviewer_role_d2=inp.reviewer_role_d2,
        reviewer_role_d3=inp.reviewer_role_d3,
        reviewer_role_d4=inp.reviewer_role_d4,
        reviewer_role_d5=inp.reviewer_role_d5,
        reviewer_role_d6=inp.reviewer_role_d6,
        test_installed_skills=inp.test_installed_skills,
        test_system=inp.test_system,
        workspace_abs=inp.workspace_abs,
    )
