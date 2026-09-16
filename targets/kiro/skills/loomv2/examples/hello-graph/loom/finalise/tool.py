"""finalise — exit tool task. Composes the whole-graph output."""
from io_types import FinaliseInput, FinaliseOutput


def finalise(inp: FinaliseInput) -> FinaliseOutput:
    return FinaliseOutput(message=f"[{inp.decision}] {inp.summary}")
