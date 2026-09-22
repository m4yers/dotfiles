"""Tool body for the ``overview-exit`` task (loomv2 native contract).

Pure fan-in aggregator: collects the cross-cutting context envelope
(workspace path, feature slug, description echo, build/test resolution
with installed skills and fallback commands, workspace brief, detected
domains, and cache identity) into a single ``envelope`` object.

The dataclass constructor of :class:`OverviewExitOutput` fails fast
when any required field is missing so the subgraph never reports
DONE with a partial envelope. No derived data is added — every field
is echoed verbatim from an upstream task via the input mapping.
"""

from __future__ import annotations

from io_types import OverviewExitInput, OverviewExitOutput


def overview_exit(inp: OverviewExitInput) -> OverviewExitOutput:
    envelope = {
        "workspace_abs": inp.workspace_abs,
        "feature_slug": inp.feature_slug,
        "description": inp.description,
        "build_system": inp.build_system,
        "build_installed_skills": inp.build_installed_skills,
        "fallback_build_cmd": inp.fallback_build_cmd,
        "test_system": inp.test_system,
        "test_installed_skills": inp.test_installed_skills,
        "fallback_test_cmd": inp.fallback_test_cmd,
        "workspace_brief": inp.workspace_brief,
        "domains": inp.domains,
        "cache_prefix": inp.cache_prefix,
        "blob_prefix": inp.blob_prefix,
        "cache_key": inp.cache_key,
        "git_head": inp.git_head,
        "dirty": inp.dirty,
        "cache_mode": inp.cache_mode,
    }
    return OverviewExitOutput(envelope=envelope)
