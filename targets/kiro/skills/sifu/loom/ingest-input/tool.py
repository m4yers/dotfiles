"""ingest-input — entry task: validated `op` and `name` pass-through."""
from __future__ import annotations

from io_types import IngestInputInput, IngestInputOutput


def ingest_input(inp: IngestInputInput) -> IngestInputOutput:
    return IngestInputOutput(op=inp.op, name=inp.name)
