"""ingest-input — audit subgraph entry: locate shape plus the design
(create) or change plan (update) to verify; pass-through."""
from __future__ import annotations

from io_types import IngestInputInput, IngestInputOutput


def ingest_input(inp: IngestInputInput) -> IngestInputOutput:
    return IngestInputOutput.from_dict(inp.to_dict())
