"""JSON schema validation for sub-agent outputs and pipeline artifacts.

Deterministic oracle — runs before any downstream consumer reads the
files, so schema drift fails loudly instead of propagating.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

SCHEMA_DIR = Path(__file__).parent / "schemas"

# Which workdir files belong to which schema. The left column is the
# filename inside /tmp/curator/<date>/<slug>/, the right is the schema
# filename inside engine/schemas/.
EXTRACTOR_FILES = {
    "summary.json":  "summary.schema.json",
    "sources.json":  "sources.schema.json",
    "keywords.json": "items.schema.json",
    "people.json":   "items.schema.json",
    "models.json":   "items.schema.json",
}

PIPELINE_FILES = {
    "composed": "composed.schema.json",
    "approved": "approved.schema.json",
}


def validate_extractors(workdir: str) -> dict:
    """Validate all five extractor outputs in a workdir."""
    wd = Path(workdir)
    results = []
    ok = True
    for fname, schema_name in EXTRACTOR_FILES.items():
        path = wd / fname
        res = _validate_one(path, schema_name)
        results.append({"file": fname, **res})
        if not res["ok"]:
            ok = False
    return {"ok": ok, "results": results}


def validate_schema(kind: str, path: str) -> dict:
    """Validate a single pipeline artifact against its named schema."""
    schema_name = PIPELINE_FILES.get(kind)
    if not schema_name:
        raise ValueError(f"unknown schema kind: {kind}; expected one of {sorted(PIPELINE_FILES)}")
    return _validate_one(Path(path), schema_name)


def _validate_one(path: Path, schema_name: str) -> dict:
    if not path.exists():
        return {"ok": False, "error": f"file not found: {path}"}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"invalid JSON: {e}"}

    schema_path = SCHEMA_DIR / schema_name
    schema = json.loads(schema_path.read_text())
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        return {"ok": False, "error": f"schema violation: {e.message}", "path": list(e.absolute_path)}
    return {"ok": True}
