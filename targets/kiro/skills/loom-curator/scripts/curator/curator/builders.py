"""Generic schema-driven builder.

Two CLI commands replace all per-kind builders:

* ``curator builders init <output> --schema <kind>``
  Loads ``templates/<kind>/schema.yaml``, embeds the schema and the
  kind name as ``_schema`` and ``_schema_kind`` fields in the output
  file, and initializes any required top-level container shapes
  (arrays start empty, objects start as ``{}``).

* ``curator builders add <output> --set path.to.field=value [--set ...] ...``
  Applies one or more ``path=value`` assignments, then validates the
  resulting file against the embedded schema. Supports nested paths
  (``citations.0.title``) and creates intermediate objects/arrays
  as needed. Type coercion follows the schema (integer fields
  parse to int, array-of-string fields support ``--set
  field.0=v0 --set field.1=v1`` style).

Schema embedding makes every output file self-describing: any
downstream reader can re-validate without knowing the kind, and
the agent never sees the schema in its final output (the
``_schema*`` fields are stripped on read by curator's own readers).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Annotated, Any

import jsonschema
import typer
import yaml

from curator.utils import emit, fail


app = typer.Typer(
    help="Schema-driven output builders (init, add).",
    no_args_is_help=True,
)


# Schema location: <skill>/templates/<kind>/schema.yaml
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates"

_SCHEMA_FIELD = "_schema"


# ── helpers ──────────────────────────────────────────────────────


def _schema_path(kind: str) -> Path:
    # The "judge" schema is shared across every extractor's per-item
    # rubric verdict; it lives next to the base judge template under
    # _meta/ rather than in a per-kind extractors/<kind>/ dir.
    if kind == "judge":
        return _TEMPLATES_DIR / "extractors" / "_meta" / "judge-output-schema.yaml"
    return _TEMPLATES_DIR / "extractors" / kind / "schema.yaml"


def _load_schema_at(p: Path) -> dict:
    if not p.exists():
        fail(f"schema not found at {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _load_schema(kind: str) -> dict:
    return _load_schema_at(_schema_path(kind))


def _initial_data(schema: dict) -> dict:
    """Build the initial output shape from the schema's top-level
    properties. Arrays start as ``[]``, objects as ``{}``, scalars
    are left absent (the agent fills them in via add)."""
    data: dict = {}
    for name, sub in (schema.get("properties") or {}).items():
        t = sub.get("type")
        if t == "array":
            data[name] = []
        elif t == "object":
            data[name] = {}
    return data


def _atomic_save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True,
                        default_flow_style=False),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _load_output(path: Path) -> dict:
    if not path.exists():
        fail(f"output file does not exist: {path}; "
              f"call ``builders init`` first")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# ── path resolution ─────────────────────────────────────────────


_PATH_PART = re.compile(r"^(?:\d+|[^.\[]+)$")


def _split_path(path: str) -> list[str]:
    """Split dotted path. Numeric segments are treated as array
    indices when applied; the path itself stays as strings here."""
    if not path:
        fail(f"empty path")
    parts = path.split(".")
    for p in parts:
        if not _PATH_PART.match(p):
            fail(f"invalid path segment {p!r} in {path!r}")
    return parts


def _set_path(root: Any, path: str, value: Any) -> Any:
    """Apply ``value`` at ``path`` inside ``root``; returns root."""
    parts = _split_path(path)
    cursor = root
    # Walk to the parent of the final segment, creating intermediates.
    for i, part in enumerate(parts[:-1]):
        next_part = parts[i + 1]
        next_is_index = next_part.isdigit()

        if part.isdigit():
            idx = int(part)
            if not isinstance(cursor, list):
                fail(f"path {path!r}: expected list at segment "
                      f"{'.'.join(parts[:i])}, got {type(cursor).__name__}")
            while len(cursor) <= idx:
                cursor.append([] if next_is_index else {})
            cursor = cursor[idx]
        else:
            if not isinstance(cursor, dict):
                fail(f"path {path!r}: expected object at segment "
                      f"{'.'.join(parts[:i])}, got {type(cursor).__name__}")
            if part not in cursor or cursor[part] is None:
                cursor[part] = [] if next_is_index else {}
            cursor = cursor[part]

    last = parts[-1]
    if last.isdigit():
        idx = int(last)
        if not isinstance(cursor, list):
            fail(f"path {path!r}: expected list at parent, got "
                  f"{type(cursor).__name__}")
        while len(cursor) <= idx:
            cursor.append(None)
        cursor[idx] = value
    else:
        if not isinstance(cursor, dict):
            fail(f"path {path!r}: expected object at parent, got "
                  f"{type(cursor).__name__}")
        cursor[last] = value
    return root


# ── type coercion ───────────────────────────────────────────────


def _resolve_type_for_path(schema: dict, path: list[str]) -> dict | None:
    """Walk schema following ``path`` (with arrays handled via items).
    Returns the leaf schema fragment, or None if unresolvable."""
    cur = schema
    for part in path:
        if cur.get("type") == "array":
            # Numeric index — descend into items.
            cur = cur.get("items") or {}
            if part.isdigit():
                continue
            # Non-numeric path part inside array — try properties under items.
            cur = (cur.get("properties") or {}).get(part)
            if cur is None:
                return None
        elif cur.get("type") == "object" or "properties" in cur:
            cur = (cur.get("properties") or {}).get(part)
            if cur is None:
                return None
        else:
            return None
    return cur


def _coerce(value: str, leaf_schema: dict | None) -> Any:
    """Coerce a string value to the type specified by leaf_schema."""
    if value == "null":
        return None
    if leaf_schema is None:
        return value
    t = leaf_schema.get("type")
    # If the schema allows null and the value is the literal string
    # "null", treat as Python None. Same for empty string when
    # null is allowed.
    types = t if isinstance(t, list) else [t]
    if "null" in types and value in ("", "null", "None"):
        return None
    if "integer" in types:
        try:
            return int(value)
        except ValueError:
            fail(f"value {value!r} is not a valid integer")
    if "number" in types:
        try:
            return float(value)
        except ValueError:
            fail(f"value {value!r} is not a valid number")
    if "boolean" in types:
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
        fail(f"value {value!r} is not a valid boolean")
    return value


# ── CLI ─────────────────────────────────────────────────────────


@app.command("init")
def init(
    output: Annotated[str, typer.Argument(
        help="Absolute path of the output file to create.")],
    schema: Annotated[str, typer.Option("--schema",
        help="Kind name; resolves to templates/extractors/<kind>/schema.yaml.")],
) -> None:
    """Initialize an output file with a schema reference."""
    spath = _schema_path(schema)
    sch = _load_schema_at(spath)
    # Put _schema first so it appears at the top of the YAML.
    data: dict = {_SCHEMA_FIELD: str(spath)}
    data.update(_initial_data(sch))
    p = Path(output)
    _atomic_save(p, data)
    emit({"ok": True, "path": str(p), "schema": str(spath)})


@app.command("add")
def add(
    output: Annotated[str, typer.Argument()],
    set_pairs: Annotated[list[str], typer.Option("--set",
        help="path=value (repeatable). Path supports dots and "
             "numeric array indices: 'citations.0.title=...'")],
) -> None:
    """Apply one or more ``path=value`` assignments and validate."""
    p = Path(output)
    data = _load_output(p)
    schema_ref = data.get(_SCHEMA_FIELD)
    if not schema_ref:
        fail(f"output {p} has no embedded _schema reference; "
              f"call ``builders init`` first")
    schema = _load_schema_at(Path(schema_ref))

    def _data_view(d: dict) -> dict:
        return {k: v for k, v in d.items() if k != _SCHEMA_FIELD}

    applied: list[dict] = []
    for pair in set_pairs:
        if "=" not in pair:
            fail(f"--set requires path=value, got {pair!r}")
        path, _, raw_value = pair.partition("=")
        leaf = _resolve_type_for_path(schema, _split_path(path))
        value = _coerce(raw_value, leaf)
        _set_path(data, path, value)
        applied.append({"path": path, "type": leaf.get("type") if leaf else "?"})

    try:
        jsonschema.validate(instance=_data_view(data), schema=schema)
    except jsonschema.ValidationError as e:
        fail(f"schema violation at {list(e.absolute_path)}: {e.message}",
              applied=applied)

    _atomic_save(p, data)
    emit({"ok": True, "path": str(p), "applied": applied})
