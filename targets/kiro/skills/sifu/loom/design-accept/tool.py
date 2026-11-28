"""design-accept — design-loop latch: carries the gate decision and the
design out of the loop region (loomv2 routes all loop outflow
through the latch)."""
from __future__ import annotations

from io_types import DesignAcceptInput, DesignAcceptOutput


def design_accept(inp: DesignAcceptInput) -> DesignAcceptOutput:
    return DesignAcceptOutput.from_dict(inp.to_dict())
