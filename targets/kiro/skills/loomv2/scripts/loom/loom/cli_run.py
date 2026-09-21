"""CLI subcommand bodies: ``runtime init/next/complete`` plus ``runtime
fail/reset/status``.

Thin wrappers over the Python lifecycle + runtime. Kept out of
``__main__.py`` so that dispatch stays argument-parsing only.

The CLI is the primary client interface. Tool tasks run internally
during ``runtime next`` and never surface in the ``ready`` batch; the
caller only ever dispatches ``agent`` and ``human`` tasks. At every
dispatch, mapping-bearing tasks have their materialised ``input.yaml``
resolved against upstream outputs and strict-validated against
``io.yaml/input`` — a mismatch writes ``schema-error.yaml`` (phase
input) and aborts the run.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

from loom._lifecycle import init as _init, resume as _resume
from loom.engine.algorithm import failed_task_ids
from loom.engine.mapping import resolve_task_input
from loom.engine.models import Task
from loom.engine.reserved import RESERVED_FIELDS, build_reserved_values
from loom.engine.store import (
    atomic_write,
    begin_round,
    task_folder as _task_folder,
    write_output_yaml,
    write_schema_error_yaml,
)
from loom.engine.tool_dispatch import dispatch_tool
from loom.errors import InputSchemaError, RunAborted
from loom.render.jinja import render_task_body


def cmd_init(
    workdir: Path | None,
    loom_root: Path,
    *,
    assignments: list[str] | None = None,
) -> int:
    """Initialise a fresh workdir from ``<loom_root>/graph.yaml``.

    ``workdir`` is optional. When ``None``, the engine derives
    ``skill_name`` via :func:`loom.naming.derive_skill_name` and
    creates a fresh ``/tmp/<skill_name>/<uuid4.hex[:12]>/`` — the
    auto form. When explicit, the caller-supplied path is used
    verbatim. In BOTH shapes, :func:`loom._lifecycle.init` wipes any
    existing contents and recreates the workdir unconditionally.

    ``assignments`` is a list of ``key=value`` strings sharing
    grammar with ``output add --set``. When non-empty, after init
    succeeds this function resolves the plan's single entry task
    (in-degree 0 in the composed plan) and, provided the entry task
    has no ``input:`` mapping in graph.yaml, applies the assignments
    into an accumulator dict, strict-validates the assembled document
    against the entry task's ``io.yaml/input`` (required fields
    enforced), and writes ``tasks/<NN>-<entry>/input.yaml`` via the
    same atomic YAML emitter used elsewhere. Raises
    :class:`SeedNotAllowedError` if the entry task has an ``input:``
    mapping; raises a :class:`LoomPlanError` on bad grammar or a
    schema-validation failure.

    Auto-form cleanup: if ``workdir`` was ``None`` (auto form) and
    any exception surfaces after the auto path is created — plan
    validation, ``SeedNotAllowedError``, ``--set`` grammar or schema
    failure — the auto path is deleted before the exception
    propagates, so a failed auto init leaves nothing behind. The
    explicit-workdir branch does no post-failure cleanup: the caller
    owns the path.
    """
    import shutil
    import uuid

    import jsonschema

    from loom._lifecycle import resume as _resume_lifecycle
    from loom.builders import _APPEND, _coerce, _set_by_tokens, _tokenize_path
    from loom.discovery import load_io_yaml
    from loom.engine.models import Task
    from loom.engine.store import task_folder as _task_folder
    from loom.errors import LoomPlanError, SeedNotAllowedError
    from loom.naming import derive_skill_name

    auto = workdir is None
    if auto:
        skill_name = derive_skill_name(Path(loom_root))
        # 12 hex chars = 48 bits of entropy. Balances collision
        # resistance across concurrent auto workdirs against
        # filesystem-friendly path length (mirrors the sibling
        # instance-uid slice at engine/inline.py:70).
        workdir = Path("/tmp") / skill_name / uuid.uuid4().hex[:12]

    try:
        _init(workdir, loom_root=loom_root)
        print(str(workdir))
        if not assignments:
            return 0

        # Load the composed plan and resolve the entry task via the same
        # in-degree-0 predicate `validate_single_entry_exit` uses. Static
        # validation has already run inside `_init`, so exactly one entry
        # exists.
        runtime = _resume_lifecycle(workdir)
        plan = runtime.plan
        tasks = [t for t in plan.tasks if isinstance(t, Task)]
        incoming: dict[str, int] = {t.id: 0 for t in tasks}
        for t in tasks:
            for d in list(t.depends_on_all) + list(t.depends_on_any):
                if d in incoming:
                    incoming[t.id] += 1
        entry_ids = [i for i, c in incoming.items() if c == 0]
        entry_id = entry_ids[0]
        entry = next(t for t in tasks if t.id == entry_id)
        if entry.input_mapping is not None:
            raise SeedNotAllowedError(
                f"entry task {entry_id!r} has an `input:` mapping; "
                "`--set` cannot seed its input.yaml."
            )

        doc: dict[str, Any] = {}
        for a in assignments:
            path, _, raw_value = a.partition("=")
            try:
                _set_by_tokens(doc, _tokenize_path(path), _coerce(raw_value))
            except ValueError as exc:
                raise LoomPlanError(
                    f"--set path {path!r} is malformed: {exc}"
                ) from exc

        source = _source_folder(runtime, entry)
        io = load_io_yaml(source)
        try:
            jsonschema.validate(doc, io.input_schema)
        except jsonschema.ValidationError as exc:
            raise LoomPlanError(
                f"--set seed for entry task {entry_id!r} fails "
                f"io.yaml/input: {exc.message}"
            ) from exc

        folder = _task_folder(workdir, plan, entry_id)
        folder.mkdir(parents=True, exist_ok=True)
        write_output_yaml_like(folder / "input.yaml", doc)
        return 0
    except BaseException:
        # Auto-form guarantee: any failure after the auto path was
        # picked leaves nothing behind. Explicit-workdir callers own
        # their path and are not cleaned up.
        if auto and workdir.exists():
            shutil.rmtree(workdir, ignore_errors=True)
        raise


def cmd_next(workdir: Path) -> int:
    """Advance the plan: run tool tasks internally, surface agent/human.

    Emits a YAML document with ``done: true|false`` and, when not done,
    a ``ready:`` list of agent/human task descriptors. Non-zero exit
    with the failed address + ``error.yaml`` path on abort.
    """
    runtime = _resume(workdir)
    while True:
        try:
            action = runtime.next()
        except RunAborted:
            return _emit_abort(runtime, workdir)
        if action is None:
            _emit({"done": True, "ready": []})
            return 0
        tool_batch = [t for t in action.tasks if t["kind"] == "tool"]
        surface_batch = [t for t in action.tasks if t["kind"] != "tool"]
        if tool_batch:
            runtime.commit_running([t["id"] for t in tool_batch])
            for t in tool_batch:
                _run_tool(runtime, workdir, t["id"])
            if not surface_batch:
                continue  # tools may unblock more; re-check.
        runtime.commit_running([t["id"] for t in surface_batch])
        ready = [_ready_entry(runtime, workdir, t) for t in surface_batch]
        _emit({"done": False, "ready": ready})
        return 0


def cmd_complete(workdir: Path, task_id: str) -> int:
    """Mark ``task_id`` done. Validates output.yaml against io.yaml/output."""
    runtime = _resume(workdir)
    runtime.complete(task_id)
    print("ok")
    return 0


def cmd_fail(workdir: Path, task_id: str, message: str) -> int:
    """Mark ``task_id`` failed with ``message``; writes error.yaml.

    Callers use this to surface human/agent failures the CLI cannot
    detect on its own. The next ``runtime next`` aborts.
    """
    runtime = _resume(workdir)
    runtime.fail(task_id, message)
    print("ok")
    return 0


def cmd_reset(workdir: Path, task_id: str) -> int:
    """Reset ``task_id`` back to pending, clearing its generated artifacts.

    Region-aware for loop-body tasks; latch ``fuel`` is not restored.
    Caller-seeded input.yaml (entries without an ``input:`` mapping) is
    preserved.
    """
    runtime = _resume(workdir)
    runtime.reset(task_id)
    print("ok")
    return 0


def cmd_status(workdir: Path) -> int:
    """Print the runtime's ``status_summary()`` as YAML."""
    runtime = _resume(workdir)
    _emit(runtime.status_summary())
    return 0


def _emit(doc: dict[str, Any]) -> None:
    """Write a YAML document to stdout without key sorting."""
    sys.stdout.write(yaml.safe_dump(doc, sort_keys=False))


def _emit_abort(runtime, workdir: Path) -> int:
    """Print the first failed task and its error.yaml path to stderr."""
    from loom.engine.store import round_folder

    failed = failed_task_ids(runtime.plan)
    fid = failed[0] if failed else "?"
    if fid != "?":
        folder = round_folder(
            _task_folder(workdir, runtime.plan, fid),
            is_loop_body=_is_loop_body(runtime, fid),
        )
    else:
        folder = Path(workdir)
    err_path = folder / "error.yaml"
    sys.stderr.write(
        yaml.safe_dump(
            {"failed_task": fid, "error_path": str(err_path)},
            sort_keys=False,
        )
    )
    return 1


def _get_task(runtime, task_id: str) -> Task:
    for t in runtime.plan.tasks:
        if isinstance(t, Task) and t.id == task_id:
            return t
    raise KeyError(task_id)


def _source_folder(runtime, task: Task) -> Path:
    """Task's io.yaml/body source folder (loom-root side, not workdir)."""
    from loom.engine.runner import task_source_folder

    return task_source_folder(runtime.plan.loom_root, task)


def _is_loop_body(runtime, task_id: str) -> bool:
    from loom.engine.loops import region_members

    return task_id in region_members(runtime.plan)


def _dispatch_folder(runtime, workdir: Path, task_id: str) -> Path:
    """Folder the current activation reads input from and writes output to.

    Non-loop tasks use the flat task folder. Loop-body tasks get a
    fresh ``iter-NN/`` round dir per activation.
    """
    folder = _task_folder(workdir, runtime.plan, task_id)
    folder.mkdir(parents=True, exist_ok=True)
    if not _is_loop_body(runtime, task_id):
        return folder
    return begin_round(folder)


def _materialise_input(runtime, workdir: Path, task_id: str, folder: Path) -> None:
    """Resolve the task's input mapping and write input.yaml.

    For tasks without a mapping the caller-seeded input.yaml is left in
    place; declared reserved engine-provided fields (``__loom``,
    ``__task``) are filled in either way so ``input.yaml`` always
    carries them when the io.yaml declares them. On a strict-validation
    failure this writes ``schema-error.yaml`` (phase input), marks the
    task failed, and re-raises so ``cmd_next`` aborts.
    """
    from loom.discovery import load_io_yaml

    task = _get_task(runtime, task_id)
    input_path = folder / "input.yaml"
    source = _source_folder(runtime, task)
    io = load_io_yaml(source)
    reserved = build_reserved_values(task, workdir, folder, source)
    declared_reserved = {
        name: reserved[name]
        for name in RESERVED_FIELDS
        if name in (io.input_schema.get("properties") or {})
    }
    if task.input_mapping is None:
        # Preserve caller-seeded input.yaml; fill declared reserved
        # fields on top so `{{ input.__loom.workdir }}` etc. resolve.
        existing: dict[str, Any] = {}
        if input_path.exists():
            existing = yaml.safe_load(input_path.read_text()) or {}
        merged = {**existing, **declared_reserved}
        if not merged and not input_path.exists():
            input_path.write_text("{}\n")
        else:
            write_output_yaml_like(input_path, merged)
        return
    try:
        resolved = resolve_task_input(
            task, runtime.plan, workdir, folder, io.input_schema
        )
    except InputSchemaError as exc:
        folder.mkdir(parents=True, exist_ok=True)
        write_schema_error_yaml(folder, task_id, "input", exc.message)
        task.status = "failed"
        from loom.engine.store import write_error_yaml, write_plan_yaml

        write_error_yaml(folder, task_id, task.kind, exc)
        write_plan_yaml(workdir, runtime.plan)
        raise
    write_output_yaml_like(input_path, resolved)


def write_output_yaml_like(path: Path, doc: dict) -> None:
    """Atomic write of a dict to ``path`` as YAML (sort_keys=False)."""
    atomic_write(path, yaml.safe_dump(doc, sort_keys=False))


def _run_tool(runtime, workdir: Path, task_id: str) -> None:
    """Run one tool task under the CLI: dispatch, then complete."""
    task = _get_task(runtime, task_id)
    folder = _dispatch_folder(runtime, workdir, task_id)
    _materialise_input(runtime, workdir, task_id, folder)
    dispatch_tool(task, folder, source_folder=_source_folder(runtime, task))
    runtime.complete(task_id)


def _ready_entry(runtime, workdir: Path, t: dict[str, Any]) -> dict[str, Any]:
    """Materialise input.yaml + rendered body; return the ready descriptor."""
    task = _get_task(runtime, t["id"])
    folder = _dispatch_folder(runtime, workdir, t["id"])
    _materialise_input(runtime, workdir, t["id"], folder)
    input_path = folder / "input.yaml"
    input_data = yaml.safe_load(input_path.read_text()) or {}
    source = _source_folder(runtime, task)
    body_name = "prompt.md" if t["kind"] == "agent" else "message.md"
    body_path = folder / body_name
    body_path.write_text(render_task_body(task, source, input_data))
    entry: dict[str, Any] = {
        "id": t["id"],
        "kind": t["kind"],
        "task_workdir": str(folder),
        "input_path": str(input_path),
        "output_path": str(folder / "output.yaml"),
    }
    entry["prompt_path" if t["kind"] == "agent" else "message_path"] = str(body_path)
    return entry
