"""publish-output — exit task. Sums per-stage run counts and
re-emits the commit SHA for the host SKILL.md.
"""
from __future__ import annotations

from io_types import PublishOutputInput, PublishOutputOutput


def publish_output(inp: PublishOutputInput) -> PublishOutputOutput:
    return PublishOutputOutput(
        vault_path=inp.vault_path,
        scripts_run=(len(inp.ingestion_runs)
                     + len(inp.inference_runs)
                     + len(inp.presentation_runs)),
        commit_sha=inp.commit_sha,
    )
