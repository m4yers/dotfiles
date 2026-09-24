"""Entry task for project-design: exact-parameter pass-through.

The subgraph contract is precisely the fields the pipeline consumes
— no opaque wrapper object. This skill does not know who produces
them: standalone runs seed them directly; a composing parent graph
wires them from whatever sibling produces compatible fields.
"""

from io_types import IngestInputInput, IngestInputOutput


def ingest_input(inp: IngestInputInput) -> IngestInputOutput:
    return IngestInputOutput(
        description=inp.description,
        workspace_abs=inp.workspace_abs,
        build_system=inp.build_system,
        build_installed_skills=inp.build_installed_skills,
        fallback_build_cmd=inp.fallback_build_cmd,
        fallback_test_cmd=inp.fallback_test_cmd,
        domains=inp.domains,
        summaries_store=inp.summaries_store,
        summaries_usage=inp.summaries_usage,
    )
