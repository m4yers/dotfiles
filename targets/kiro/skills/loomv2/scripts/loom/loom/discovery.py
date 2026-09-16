"""Task-folder resolution, kind detection, and graph.yaml loading.

Every public function carries a docstring stating the contract, args,
return shape, and raises list.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from loom.errors import (
    GraphYamlError,
    IOYamlError,
    KindMismatchError,
    TaskFolderError,
)


@dataclass
class IoYaml:
    """Parsed io.yaml. Fields track schemas/io.yaml one-to-one."""

    version: int
    input_schema: dict
    output_schema: dict


def resolve_task_folder(loom_root: Path, task_id: str) -> Path:
    """Return the folder that backs ``task_id``.

    The last segment of the canonical address is the LOCAL id, i.e. the
    on-disk folder name. Raises TaskFolderError on miss.
    """
    local_id = task_id.rsplit("/", 1)[-1]
    folder = Path(loom_root) / local_id
    if not folder.is_dir():
        raise TaskFolderError(f"task folder not found: {folder}")
    return folder


def detect_kind(folder: Path) -> str:
    """Return one of 'tool', 'agent', 'human' based on the folder body file.

    Raises KindMismatchError if zero or multiple body files are present.
    """
    body_files = {
        "tool": folder / "tool.py",
        "agent": folder / "prompt.md.j2",
        "human": folder / "message.md.j2",
    }
    present = [k for k, p in body_files.items() if p.exists()]
    if len(present) != 1:
        raise KindMismatchError(
            f"folder {folder} contains body files for kinds {present!r}; "
            "exactly one required"
        )
    return present[0]


_META_SCHEMA_IO: dict | None = None
_META_SCHEMA_GRAPH: dict | None = None


def _load_meta_schema(name: str) -> dict:
    """Load a bundled schemas/<name> once and cache it."""
    global _META_SCHEMA_IO, _META_SCHEMA_GRAPH
    cache = {"io.yaml": _META_SCHEMA_IO, "graph.yaml": _META_SCHEMA_GRAPH}[name]
    if cache is not None:
        return cache
    # schemas/ lives at the skill root; the module lives at
    # scripts/loom/loom/. Ascend three levels.
    root = Path(__file__).resolve().parents[3]
    parsed = yaml.safe_load((root / "schemas" / name).read_text())
    if name == "io.yaml":
        _META_SCHEMA_IO = parsed
    else:
        _META_SCHEMA_GRAPH = parsed
    return parsed


def load_io_yaml(folder: Path) -> IoYaml:
    """Load and meta-validate ``<folder>/io.yaml``.

    Before meta-validation, filesystem-relative ``$ref`` nodes in the
    ``input`` and ``output`` blocks are pre-inlined against the io.yaml
    file's own folder (nested refs re-anchor to their loaded file's
    folder). Absolute URIs (``http://``, ``file://``) and JSON Pointer
    fragments (``#/...``) pass through unchanged. Missing targets and
    cycles raise :class:`IOYamlError`.

    Raises IOYamlError with the offending field description quoted.
    """
    import jsonschema

    path = folder / "io.yaml"
    if not path.exists():
        raise IOYamlError(f"io.yaml missing at {path}")
    try:
        parsed = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise IOYamlError(f"io.yaml malformed at {path}: {exc}")
    if "input" in parsed:
        _substitute_reserved(parsed["input"], path)
        parsed["input"] = _resolve_local_refs(
            parsed["input"], folder, visited=frozenset()
        )
    if "output" in parsed:
        parsed["output"] = _resolve_local_refs(
            parsed["output"], folder, visited=frozenset()
        )
    meta = _load_meta_schema("io.yaml")
    try:
        jsonschema.validate(parsed, meta)
    except jsonschema.ValidationError as exc:
        # Quote the field description from the meta-schema.
        prop = exc.absolute_path[0] if exc.absolute_path else None
        hint = meta.get("properties", {}).get(prop, {}).get("description", "")
        raise IOYamlError(f"{path}: {exc.message}. {hint}")
    return IoYaml(
        version=parsed["version"],
        input_schema=parsed["input"],
        output_schema=parsed["output"],
    )


def _substitute_reserved(input_schema: Any, path: Path) -> None:
    """In-place substitute reserved-name declarations with meta-schemas.

    For every key in ``input.properties`` that names a reserved field
    (``__loom`` / ``__task``), the declared value MUST be the bare
    empty mapping ``{}`` — loom owns the shape and inlines the
    canonical meta-schema from ``schemas/<alias>-meta.yaml``. Any
    non-empty declaration (``$ref``, inline ``type``, extra keys)
    raises :class:`IOYamlError` pointing at ``references/io.md`` §5.

    Runs before ``_resolve_local_refs`` so a conflicting
    ``$ref`` is rejected without touching the filesystem.
    """
    if not isinstance(input_schema, dict):
        return
    properties = input_schema.get("properties")
    if not isinstance(properties, dict):
        return
    # Lazy import to avoid any engine→discovery cycle risk.
    from loom.engine.reserved import RESERVED_ALIASES, RESERVED_FIELDS

    for name in list(properties.keys()):
        if name not in RESERVED_FIELDS:
            continue
        decl = properties[name]
        if decl != {}:
            raise IOYamlError(
                f"{path}: reserved name {name!r} MUST be declared as the "
                f"bare empty mapping ``{{}}``; got {decl!r}. "
                f"See references/io.md §5."
            )
        from loom.engine.reserved import load_meta_schema

        properties[name] = load_meta_schema(RESERVED_ALIASES[name])


def _resolve_local_refs(
    schema: Any,
    base: Path,
    visited: frozenset[str],
) -> Any:
    """Recursively inline filesystem-relative ``$ref`` nodes.

    A dict whose ``$ref`` is a relative filesystem path is replaced by
    the parsed contents of the target YAML file (per draft 2020-12,
    sibling keys next to ``$ref`` are dropped). Nested refs inside a
    target re-anchor to that target's own folder. Absolute URIs
    (``http://``, ``file://``, etc.) and JSON Pointer fragments
    (``#/...``) pass through untouched — draft 2020-12 handles the
    pointer form natively via jsonschema.

    Raises :class:`IOYamlError` on missing targets, malformed YAML, or
    cycles. ``visited`` is the set of already-loaded target paths in
    the current recursion chain; two independent branches are not a
    cycle.
    """
    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if isinstance(ref, str) and not (ref.startswith("#") or "://" in ref):
            target = (base / ref).resolve()
            target_key = str(target)
            if target_key in visited:
                raise IOYamlError(
                    f"$ref cycle: {target} (references/io.md §3)"
                )
            if not target.exists():
                raise IOYamlError(
                    f"$ref target missing: {target} (references/io.md §3)"
                )
            try:
                loaded = yaml.safe_load(target.read_text())
            except yaml.YAMLError as exc:
                raise IOYamlError(
                    f"$ref target malformed at {target}: {exc}"
                )
            return _resolve_local_refs(
                loaded, target.parent, visited | {target_key}
            )
        return {k: _resolve_local_refs(v, base, visited) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_resolve_local_refs(v, base, visited) for v in schema]
    return schema


def resolve_graph_yaml(loom_root: Path) -> Path:
    """Return the expected path to ``<loom_root>/graph.yaml``."""
    return Path(loom_root) / "graph.yaml"


def load_graph_yaml(loom_root: Path) -> dict[str, Any]:
    """Load and meta-validate ``<loom_root>/graph.yaml``.

    Raises GraphYamlError on schema failure. Returns the parsed dict.
    """
    import jsonschema

    path = resolve_graph_yaml(loom_root)
    if not path.exists():
        raise GraphYamlError(f"graph.yaml missing at {path}")
    try:
        parsed = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise GraphYamlError(f"graph.yaml malformed at {path}: {exc}")
    meta = _load_meta_schema("graph.yaml")
    try:
        jsonschema.validate(parsed, meta)
    except jsonschema.ValidationError as exc:
        raise GraphYamlError(f"{path}: {exc.message}")
    return parsed
