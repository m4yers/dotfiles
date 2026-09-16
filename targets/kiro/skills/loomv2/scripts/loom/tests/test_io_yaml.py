"""Meta-schema validation for io.yaml."""
from __future__ import annotations

import pytest
import yaml

from loom.discovery import load_io_yaml
from loom.errors import IOYamlError


def _write(folder, doc):
    (folder / "io.yaml").write_text(yaml.safe_dump(doc))


def test_positive(tmp_path):
    _write(tmp_path, {
        "version": 1,
        "input": {"type": "object"},
        "output": {"type": "object"},
    })
    io = load_io_yaml(tmp_path)
    assert io.version == 1


def test_missing_version(tmp_path):
    _write(tmp_path, {"input": {"type": "object"}, "output": {"type": "object"}})
    with pytest.raises(IOYamlError):
        load_io_yaml(tmp_path)


def test_non_integer_version(tmp_path):
    _write(tmp_path, {
        "version": "1",
        "input": {"type": "object"},
        "output": {"type": "object"},
    })
    with pytest.raises(IOYamlError):
        load_io_yaml(tmp_path)


def test_missing_input(tmp_path):
    _write(tmp_path, {"version": 1, "output": {"type": "object"}})
    with pytest.raises(IOYamlError):
        load_io_yaml(tmp_path)


def test_missing_output(tmp_path):
    _write(tmp_path, {"version": 1, "input": {"type": "object"}})
    with pytest.raises(IOYamlError):
        load_io_yaml(tmp_path)


def test_error_quotes_description(tmp_path):
    _write(tmp_path, {"input": {"type": "object"}, "output": {"type": "object"}})
    with pytest.raises(IOYamlError) as exc:
        load_io_yaml(tmp_path)
    assert "version" in str(exc.value).lower()


# ---- $ref resolution ---------------------------------------------------

def test_ref_relative_inline(tmp_path):
    """Sibling relative ``$ref`` inline-resolves at load."""
    (tmp_path / "greeting.yaml").write_text(yaml.safe_dump({
        "type": "object",
        "properties": {"greeting": {"type": "string"}},
        "required": ["greeting"],
    }))
    _write(tmp_path, {
        "version": 1,
        "input": {"$ref": "greeting.yaml"},
        "output": {"type": "object"},
    })
    io = load_io_yaml(tmp_path)
    assert "greeting" in io.input_schema["properties"]


def test_bare_reserved_substitution(tmp_path):
    """`__loom: {}` under input.properties is substituted with the
    canonical ``schemas/loom-meta.yaml``; the substituted schema
    exposes ``workdir`` as an inner property."""
    _write(tmp_path, {
        "version": 1,
        "input": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"__loom": {}},
            "required": ["__loom"],
        },
        "output": {"type": "object"},
    })
    io = load_io_yaml(tmp_path)
    loom_schema = io.input_schema["properties"]["__loom"]
    assert "workdir" in loom_schema["properties"]
    assert loom_schema.get("additionalProperties") is False


def test_reserved_conflict_ref_rejected(tmp_path):
    """`__loom: {$ref: ...}` is rejected before filesystem resolution."""
    _write(tmp_path, {
        "version": 1,
        "input": {
            "type": "object",
            "properties": {
                "__loom": {"$ref": "../../schemas/loom-meta.yaml"},
            },
        },
        "output": {"type": "object"},
    })
    with pytest.raises(IOYamlError) as exc:
        load_io_yaml(tmp_path)
    assert "__loom" in str(exc.value)
    assert "references/io.md" in str(exc.value)


def test_reserved_conflict_inline_rejected(tmp_path):
    """An inline ``type: object`` on a reserved name is rejected."""
    _write(tmp_path, {
        "version": 1,
        "input": {
            "type": "object",
            "properties": {
                "__task": {"type": "object", "properties": {"foo": {}}},
            },
        },
        "output": {"type": "object"},
    })
    with pytest.raises(IOYamlError) as exc:
        load_io_yaml(tmp_path)
    assert "__task" in str(exc.value)


def test_substituted_schema_validates_input(tmp_path):
    """The substituted ``__loom`` schema validates engine-filled
    values under jsonschema — a valid payload passes and a payload
    missing ``workdir`` fails."""
    import jsonschema

    _write(tmp_path, {
        "version": 1,
        "input": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"__loom": {}},
            "required": ["__loom"],
        },
        "output": {"type": "object"},
    })
    io = load_io_yaml(tmp_path)
    ok = {"__loom": {"workdir": "/tmp/loom-workdir", "runtime": "/x/loom.sh"}}
    jsonschema.validate(ok, io.input_schema)
    bad = {"__loom": {}}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, io.input_schema)


def test_ref_missing_target(tmp_path):
    _write(tmp_path, {
        "version": 1,
        "input": {
            "type": "object",
            "properties": {"x": {"$ref": "./missing.yaml"}},
        },
        "output": {"type": "object"},
    })
    with pytest.raises(IOYamlError) as exc:
        load_io_yaml(tmp_path)
    assert "missing.yaml" in str(exc.value)


def test_ref_cycle(tmp_path):
    """Two YAML files that $ref each other raise ``IOYamlError``
    naming ``cycle``."""
    (tmp_path / "a.yaml").write_text(yaml.safe_dump({"$ref": "b.yaml"}))
    (tmp_path / "b.yaml").write_text(yaml.safe_dump({"$ref": "a.yaml"}))
    _write(tmp_path, {
        "version": 1,
        "input": {
            "type": "object",
            "properties": {"x": {"$ref": "a.yaml"}},
        },
        "output": {"type": "object"},
    })
    with pytest.raises(IOYamlError) as exc:
        load_io_yaml(tmp_path)
    assert "cycle" in str(exc.value).lower()
