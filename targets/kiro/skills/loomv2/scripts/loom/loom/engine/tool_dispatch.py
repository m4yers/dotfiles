"""Load ``io_types.py`` and ``tool.py``, invoke the tool function,
serialise the returned ``<TaskName>Output`` via ``to_dict()``, capture
exceptions to ``error.yaml`` and captured stderr to ``stderr.yaml``.

Function-name mapping: snake_case of the LOCAL task id (last segment of
the canonical address) so subgraph-embedded tools resolve without
namespace pollution. Class-name mapping: PascalCase + ``Input`` /
``Output`` suffix, from the same local id via
``loom.naming.pascal_case_task_name``.

Split-file contract: ``io_types.py`` is generator-owned (produced by
``$LOOM task io-python``); ``tool.py`` is user-owned and imports the
Input/Output dataclasses via ``from io_types import ...``. Dispatch
loads ``io_types.py`` first, registers the module in ``sys.modules``
under both a unique name AND ``io_types`` so the ``tool.py`` import
resolves, then restores ``sys.modules`` afterwards (preserving any
pre-existing ``io_types`` entry).

Version pinning invariant: ``<TaskName>Input.VERSION ==
<TaskName>Output.VERSION == <io.yaml on disk>.version``. A drift raises
:class:`ToolIOVersionMismatchError` whose remedy is
``$LOOM task io-python <id>``.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Any

import yaml

from loom.discovery import load_io_yaml
from loom.engine.models import Task
from loom.engine.store import write_error_yaml, write_output_yaml, write_stderr_yaml
from loom.errors import ToolIOVersionMismatchError, ToolTaskError
from loom.naming import pascal_case_task_name, snake_case_task_name


def dispatch_tool(task: Task, task_folder: Path, *, source_folder: Path | None = None) -> None:
    """Run the tool.py for ``task``.

    Reads input.yaml + writes output.yaml/error.yaml in ``task_folder``.
    Captured stderr from the tool body lands in ``stderr.yaml`` when
    non-empty or when the body fails. Loads ``io_types.py`` and
    ``tool.py`` from ``source_folder`` (defaults to ``task_folder``) so
    the CLI can point at the loom-root definition while reading and
    writing under the workdir.

    Raises:
      - :class:`ToolTaskError` if ``io_types.py`` is missing, if the
        Input/Output classes are missing, if the tool function is
        missing, if the body raises, or if the returned value is not an
        instance of ``<TaskName>Output``.
      - :class:`ToolIOVersionMismatchError` if the classes' ``VERSION``
        differs from the current io.yaml version.
    """
    src = source_folder if source_folder is not None else task_folder
    local_id = task.id.rsplit("/", 1)[-1]
    fn_name = snake_case_task_name(local_id)
    pascal = pascal_case_task_name(local_id)

    types_path = src / "io_types.py"
    if not types_path.exists():
        exc = ToolTaskError(
            task.id,
            f"missing io_types.py at {types_path}; "
            f"run `$LOOM task io-python {local_id}` to generate it",
        )
        write_error_yaml(task_folder, task.id, "tool", exc)
        raise exc

    types_module = _load_module(types_path, f"loom_io_types_{fn_name}")

    input_cls = getattr(types_module, f"{pascal}Input", None)
    output_cls = getattr(types_module, f"{pascal}Output", None)
    if input_cls is None or output_cls is None:
        exc = ToolTaskError(
            task.id,
            f"io_types.py missing {pascal}Input/{pascal}Output; "
            f"run `$LOOM task io-python {local_id}` to regenerate it",
        )
        write_error_yaml(task_folder, task.id, "tool", exc)
        raise exc

    io_version = load_io_yaml(src).version
    in_ver = getattr(input_cls, "VERSION", None)
    out_ver = getattr(output_cls, "VERSION", None)
    if in_ver != io_version or out_ver != io_version:
        exc = ToolIOVersionMismatchError(
            task_id=task.id,
            class_version=in_ver if in_ver == out_ver else None,
            io_version=io_version,
        )
        write_error_yaml(task_folder, task.id, "tool", exc)
        raise exc

    saved = sys.modules.get("io_types")
    had_saved = "io_types" in sys.modules
    sys.modules["io_types"] = types_module
    try:
        module = _load_module(src / "tool.py", f"loom_tool_{fn_name}")
    finally:
        if had_saved:
            sys.modules["io_types"] = saved
        else:
            sys.modules.pop("io_types", None)

    fn = getattr(module, fn_name, None)
    if fn is None:
        exc = ToolTaskError(task.id, f"tool.py has no function named {fn_name!r}")
        write_error_yaml(task_folder, task.id, "tool", exc)
        raise exc

    input_path = task_folder / "input.yaml"
    input_dict = yaml.safe_load(input_path.read_text()) if input_path.exists() else {}
    if not isinstance(input_dict, dict):
        input_dict = {}

    stderr_buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr_buf):
            inp = input_cls.from_dict(input_dict)
            result = fn(inp)
    except Exception as exc:  # noqa: BLE001 — intentional
        write_stderr_yaml(task_folder, task.id, "tool", stderr_buf.getvalue())
        write_error_yaml(task_folder, task.id, "tool", exc)
        raise ToolTaskError(task.id, str(exc)) from exc

    captured = stderr_buf.getvalue()
    if captured:
        write_stderr_yaml(task_folder, task.id, "tool", captured)

    if not isinstance(result, output_cls):
        exc = ToolTaskError(
            task.id,
            f"tool returned {type(result).__name__!s}, "
            f"expected {pascal}Output instance",
        )
        write_error_yaml(task_folder, task.id, "tool", exc)
        raise exc

    write_output_yaml(task_folder, result.to_dict())


def _load_module(path: Path, module_name: str) -> Any:
    """Load ``path`` as a fresh Python module under ``module_name``.

    Registers the module in ``sys.modules`` before execution so that
    ``@dataclass`` can resolve string annotations (``ClassVar[int]``
    under ``from __future__ import annotations``) via
    ``sys.modules[cls.__module__].__dict__``.
    """
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ToolTaskError(module_name, f"cannot load module at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module
