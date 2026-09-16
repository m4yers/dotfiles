"""Backing logic for `$LOOM task new` and `$LOOM task io-python`.

``new_task`` creates ``<loom_root>/<name>/`` — folder only, error if
it already exists. The authoring agent then writes ``io.yaml`` by hand
(schemas/io.yaml documents the shape) and, for a tool task, calls
``io_python`` to generate ``io_types.py`` and writes ``tool.py``.

``io_python`` reads ``<loom_root>/<name>/io.yaml`` and (re)writes
``<loom_root>/<name>/io_types.py`` — a fully generator-owned file
carrying ``<TaskName>Input`` / ``<TaskName>Output`` dataclasses with
``VERSION: ClassVar[int] = <io.yaml version>`` and ``from_dict`` /
``to_dict`` helpers. Regenerate at any time; the whole file is
overwritten. Meaningful only for tool tasks, but not gated on kind.

Reserved wire keys (``__loom``, ``__task``) are aliased to
``loom`` / ``task`` at codegen time — Python name-mangling
mangles ``__``-prefixed dataclass fields into
``_<Class>__<name>`` — and their fields are TYPED with the
engine-provided dataclasses ``LoomMeta`` / ``TaskMeta``. So an author
who declares ``__loom`` in io.yaml writes ``inp.loom.workdir`` in
tool.py, not ``inp.loom["workdir"]``.
"""
from __future__ import annotations

import re
from pathlib import Path

from loom.discovery import load_io_yaml
from loom.engine.reserved import RESERVED_ALIASES
from loom.errors import TaskFolderError
from loom.naming import pascal_case_task_name


NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")

_HEADER_FMT = (
    "# generated from io.yaml v{v} by $LOOM task io-python — do not edit"
)

_PY_TYPE = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list",
    "object": "dict",
}

_RESERVED_TYPES = {"__loom": "LoomMeta", "__task": "TaskMeta"}


def new_task(loom_root: Path, name: str) -> Path:
    """Create ``<loom_root>/<name>/``. Raise TaskFolderError on collision or bad name."""
    if not NAME_RE.match(name):
        raise TaskFolderError(f"task name must be kebab-case, got {name!r}")
    target = Path(loom_root) / name
    if target.exists():
        raise TaskFolderError(f"folder already exists: {target}")
    target.mkdir(parents=True)
    return target


def io_python(loom_root: Path, name: str) -> Path:
    """Regenerate ``<loom_root>/<name>/io_types.py`` from io.yaml.

    Overwrites the whole file. Prints ``wrote io_types.py (vN)``.
    Raises TaskFolderError if the task folder does not exist; io.yaml
    problems surface as IOYamlError via load_io_yaml.
    """
    target = Path(loom_root) / name
    if not target.is_dir():
        raise TaskFolderError(f"task folder not found: {target}")
    io = load_io_yaml(target)
    pascal = pascal_case_task_name(name)
    text = _render_io_types(pascal, io.version, io.input_schema, io.output_schema)
    (target / "io_types.py").write_text(text)
    print(f"wrote io_types.py (v{io.version})")
    return target / "io_types.py"


# ---- rendering ----

def _has_reserved(schema: dict) -> bool:
    """True iff any top-level property key is a reserved wire alias."""
    properties = schema.get("properties") or {}
    return any(k in RESERVED_ALIASES for k in properties)


def _field_ident(dict_key: str) -> str:
    """Alias reserved wire keys (``__loom``, ``__task``) to safe idents.

    ``__``-prefixed dataclass fields hit Python name-mangling (see
    ``dataclasses`` docs), so we expose them as ``loom`` / ``task`` at
    the Python level while keeping the wire keys unchanged in
    ``to_dict`` / ``from_dict``.
    """
    return RESERVED_ALIASES.get(dict_key, dict_key)


def _field_type(dict_key: str, sub_schema: dict) -> str:
    """Annotation for a property: reserved keys are typed with the
    engine's own dataclasses; everything else falls through to
    ``_py_type``."""
    if dict_key in _RESERVED_TYPES:
        return _RESERVED_TYPES[dict_key]
    return _py_type(sub_schema.get("type"))


def _field_from_dict_rhs(dict_key: str, *, required: bool) -> str:
    """RHS expression used in ``from_dict`` to hydrate one field."""
    if dict_key in _RESERVED_TYPES:
        cls = _RESERVED_TYPES[dict_key]
        if required:
            return f'{cls}.from_dict(d["{dict_key}"])'
        return (
            f'({cls}.from_dict(d["{dict_key}"]) '
            f'if "{dict_key}" in d else None)'
        )
    if required:
        return f'd["{dict_key}"]'
    return f'd.get("{dict_key}")'


def _field_to_dict_rhs(dict_key: str, ident: str) -> str:
    """RHS expression used in ``to_dict`` to serialise one field."""
    if dict_key in _RESERVED_TYPES:
        return f"self.{ident}.to_dict()"
    return f"self.{ident}"


def _render_io_types(
    pascal: str,
    version: int,
    input_schema: dict,
    output_schema: dict,
) -> str:
    """Render the full io_types.py contents."""
    has_reserved = _has_reserved(input_schema) or _has_reserved(output_schema)
    header_lines = [
        _HEADER_FMT.format(v=version),
        "from dataclasses import dataclass",
        "from typing import ClassVar",
    ]
    if has_reserved:
        # `loom` / `task` aliased from wire keys `__loom` / `__task`;
        # their field types are the hand-written engine dataclasses.
        header_lines.append(
            "from loom.engine.reserved import LoomMeta, TaskMeta"
        )
    return "\n".join([
        *header_lines,
        "",
        "",
        _render_dataclass(f"{pascal}Input", version, input_schema),
        "",
        "",
        _render_dataclass(f"{pascal}Output", version, output_schema),
        "",
    ])


def _render_dataclass(class_name: str, version: int, schema: dict) -> str:
    """Render one @dataclass with VERSION, fields, from_dict, to_dict."""
    properties = schema.get("properties") or {}
    required = list(schema.get("required") or [])
    required_set = set(required)
    # Required first (in declared order), then optional (properties order).
    fields_req = [(k, properties[k]) for k in required if k in properties]
    fields_opt = [(k, v) for k, v in properties.items() if k not in required_set]

    lines: list[str] = [
        "@dataclass",
        f"class {class_name}:",
        f"    VERSION: ClassVar[int] = {version}",
    ]
    for k, v in fields_req:
        ident = _field_ident(k)
        annot = _field_type(k, v)
        lines.append(f"    {ident}: {annot}")
    for k, v in fields_opt:
        ident = _field_ident(k)
        annot = _field_type(k, v)
        lines.append(f"    {ident}: {annot} | None = None")

    lines.append("")
    lines.append("    @classmethod")
    lines.append(f'    def from_dict(cls, d: dict) -> "{class_name}":')
    if not properties:
        lines.append("        return cls()")
    else:
        lines.append("        return cls(")
        for k, _ in fields_req:
            ident = _field_ident(k)
            rhs = _field_from_dict_rhs(k, required=True)
            lines.append(f'            {ident}={rhs},')
        for k, _ in fields_opt:
            ident = _field_ident(k)
            rhs = _field_from_dict_rhs(k, required=False)
            lines.append(f'            {ident}={rhs},')
        lines.append("        )")

    lines.append("")
    lines.append("    def to_dict(self) -> dict:")
    if not properties:
        lines.append("        return {}")
    else:
        lines.append("        out: dict = {}")
        for k, _ in fields_req:
            ident = _field_ident(k)
            rhs = _field_to_dict_rhs(k, ident)
            lines.append(f'        out["{k}"] = {rhs}')
        for k, _ in fields_opt:
            ident = _field_ident(k)
            rhs = _field_to_dict_rhs(k, ident)
            lines.append(f"        if self.{ident} is not None:")
            lines.append(f'            out["{k}"] = {rhs}')
        lines.append("        return out")

    return "\n".join(lines)


def _py_type(json_type) -> str:
    """Map a JSON Schema top-level ``type`` to a Python annotation."""
    return _PY_TYPE.get(json_type, "object")
