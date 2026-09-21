"""Task-folder resolution, kind detection, and graph.yaml loading.

Every public function carries a docstring stating the contract, args,
return shape, and raises list.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from loom.errors import (
    AmbiguousToolEntryError,
    GraphYamlError,
    IOYamlError,
    KindMismatchError,
    TaskFolderError,
    TaskRefError,
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


# Kebab-case pattern shared with schemas/graph.yaml `ref` field.
_REF_KEBAB_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def resolve_ref_folder(loom_root: Path, ref: str) -> Path:
    """Return the folder named by ``ref`` under ``loom_root``.

    ``ref`` MUST be a bare kebab-cased folder name (``^[a-z][a-z0-9-]*$``)
    and MUST resolve to a real directory that is a DIRECT child of
    ``loom_root``. Any deviation — malformed ref, ref that escapes the
    loom root via ``..``, or missing folder — raises
    :class:`TaskRefError`.

    Kept separate from :func:`resolve_task_folder` because ``ref`` is a
    hand-authored graph.yaml surface with stricter validation than the
    id → folder mapping (which accepts the last segment of a canonical
    address).
    """
    if not isinstance(ref, str) or not _REF_KEBAB_RE.match(ref):
        raise TaskRefError(
            f"ref {ref!r} is not a bare kebab-cased folder name "
            f"(pattern: ^[a-z][a-z0-9-]*$)"
        )
    loom_root_resolved = Path(loom_root).resolve()
    folder = (Path(loom_root) / ref).resolve()
    if folder.parent != loom_root_resolved:
        raise TaskRefError(
            f"ref {ref!r} resolves to {folder} which is not a direct "
            f"child of loom root {loom_root_resolved}"
        )
    if not folder.is_dir():
        raise TaskRefError(
            f"ref {ref!r} points at missing folder {folder}"
        )
    return folder


def detect_kind(folder: Path) -> str:
    """Return one of 'tool', 'agent', 'human' based on the folder body file.

    A folder with either ``tool.py`` or ``tool.sh`` classifies as
    ``tool``. Carrying BOTH raises :class:`AmbiguousToolEntryError`;
    the two entry files are mutually exclusive so the engine never
    silently prefers one. The zero-body and cross-kind-body cases
    still raise :class:`KindMismatchError`.
    """
    tool_py = folder / "tool.py"
    tool_sh = folder / "tool.sh"
    if tool_py.exists() and tool_sh.exists():
        raise AmbiguousToolEntryError(
            f"folder {folder} contains both tool.py and tool.sh"
        )
    body_files = {
        "tool": tool_py.exists() or tool_sh.exists(),
        "agent": (folder / "prompt.md.j2").exists(),
        "human": (folder / "message.md.j2").exists(),
    }
    present = [k for k, v in body_files.items() if v]
    if len(present) != 1:
        raise KindMismatchError(
            f"folder {folder} contains body files for kinds {present!r}; "
            "exactly one required"
        )
    return present[0]


def resolve_tool_entry(folder: Path) -> Literal["python", "shell"]:
    """Return ``'python'`` or ``'shell'`` for the tool task in ``folder``.

    Sole owner of the "which entry file backs this tool task" decision.
    Consumed by :mod:`loom.engine.tool_dispatch` and
    :mod:`loom.validate.tool_entry`.

    Raises :class:`AmbiguousToolEntryError` if both entry files
    coexist, :class:`KindMismatchError` if neither does.
    """
    tool_py = folder / "tool.py"
    tool_sh = folder / "tool.sh"
    if tool_py.exists() and tool_sh.exists():
        raise AmbiguousToolEntryError(
            f"folder {folder} contains both tool.py and tool.sh"
        )
    if tool_sh.exists():
        return "shell"
    if tool_py.exists():
        return "python"
    raise KindMismatchError(
        f"folder {folder} has no tool.py or tool.sh entry"
    )


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


def resolve_graph_yaml(loom_root: Path, graph: Path | str | None = None) -> Path:
    """Return the graph file path for ``loom_root``.

    ``graph`` selects a variant: absolute paths are used verbatim,
    relative names resolve against ``loom_root``. ``None`` selects
    the default ``<loom_root>/graph.yaml``. Multi-graph scenarios
    (static scale variants sharing one loom root) are documented in
    ``references/guide-advanced.md``.
    """
    if graph is None:
        return Path(loom_root) / "graph.yaml"
    graph = Path(graph)
    return graph if graph.is_absolute() else Path(loom_root) / graph


def load_graph_yaml(loom_root: Path, graph: Path | str | None = None) -> dict[str, Any]:
    """Load and meta-validate the graph file (default ``graph.yaml``).

    Raises GraphYamlError on schema failure. Returns the parsed dict.
    """
    import jsonschema

    path = resolve_graph_yaml(loom_root, graph)
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
