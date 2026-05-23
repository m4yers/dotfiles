'''Schema file loading and caching with JSON-Schema meta-validation.'''
from __future__ import annotations

from pathlib import Path

import yaml
import jsonschema
from jsonschema.validators import validator_for

from loom.errors import SchemaError


class SchemaCache:
    '''Loads, parses, meta-validates, and caches JSON Schema YAML files.

    Identity contract: same absolute path -> same dict instance on every call.
    '''

    def __init__(self) -> None:
        self._cache: dict[Path, dict] = {}

    def load(self, path: str | Path) -> dict:
        p = Path(path).expanduser().resolve()
        cached = self._cache.get(p)
        if cached is not None:
            return cached
        if not p.exists():
            raise SchemaError(f'schema file not found: {p}')
        try:
            text = p.read_text(encoding='utf-8')
        except OSError as e:
            raise SchemaError(
                f'cannot read schema file {p}: {e}') from e
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise SchemaError(
                f'schema file {p} is not valid YAML: {e}') from e
        if not isinstance(doc, dict):
            raise SchemaError(
                f'schema file {p} must contain a YAML mapping at the top level')
        try:
            cls = validator_for(doc)
            cls.check_schema(doc)
        except jsonschema.exceptions.SchemaError as e:
            raise SchemaError(
                f'schema file {p} is not a valid JSON Schema: {e.message}') from e
        self._cache[p] = doc
        return doc

    def __contains__(self, path: str | Path) -> bool:
        return Path(path).expanduser().resolve() in self._cache
