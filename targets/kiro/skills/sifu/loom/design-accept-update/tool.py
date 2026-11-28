"""design-accept-update — design-loop latch: carries the gate decision and the
plan out of the loop region (loomv2 routes all loop outflow
through the latch)."""
from __future__ import annotations

from io_types import DesignAcceptUpdateInput, DesignAcceptUpdateOutput


def design_accept_update(inp: DesignAcceptUpdateInput) -> DesignAcceptUpdateOutput:
    return DesignAcceptUpdateOutput.from_dict(inp.to_dict())
