"""Runtime schema cache keyed by task id (accepts namespaced ids).

Wraps validate/io_yaml.py results with ``.input_schema``,
``.output_schema``, and ``.version`` fields for consumers.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loom.discovery import IoYaml, load_io_yaml


@dataclass
class CachedSchema:
    """Cached io.yaml view: version + input/output schemas."""

    version: int
    input_schema: dict
    output_schema: dict


class SchemaCache:
    """Task-id → CachedSchema cache."""

    def __init__(self):
        self._cache: dict[str, CachedSchema] = {}

    def get(self, loom_root: Path, task_id: str) -> CachedSchema:
        """Return the cached view; load on miss."""
        if task_id in self._cache:
            return self._cache[task_id]
        local = task_id.rsplit("/", 1)[-1]
        io: IoYaml = load_io_yaml(Path(loom_root) / local)
        cached = CachedSchema(
            version=io.version,
            input_schema=io.input_schema,
            output_schema=io.output_schema,
        )
        self._cache[task_id] = cached
        return cached
