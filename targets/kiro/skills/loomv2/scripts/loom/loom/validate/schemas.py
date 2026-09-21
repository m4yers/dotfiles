"""Runtime schema cache keyed by folder path.

Wraps validate/io_yaml.py results with ``.input_schema``,
``.output_schema``, and ``.version`` fields for consumers. Callers
resolve a task's io.yaml/body source folder via
:func:`loom.engine.runner.task_source_folder` (which honours
subgraph-inlined ``source_root`` and ref-instanced ``folder``) and pass
the resolved folder here, so ref instances sharing one folder share
one cache entry.
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
    """Folder → CachedSchema cache."""

    def __init__(self):
        self._cache: dict[str, CachedSchema] = {}

    def get(self, folder: Path) -> CachedSchema:
        """Return the cached view for ``folder``; load on miss."""
        key = str(Path(folder).resolve())
        if key in self._cache:
            return self._cache[key]
        io: IoYaml = load_io_yaml(Path(folder))
        cached = CachedSchema(
            version=io.version,
            input_schema=io.input_schema,
            output_schema=io.output_schema,
        )
        self._cache[key] = cached
        return cached
