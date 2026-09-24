"""Atomic filesystem IO for plan.yaml, input.yaml, output.yaml, error.yaml.

Writes go through temp+rename. Loop iterations nest under
``tasks/<NN-id>/iter-NN/``. Subgraph parents receive a summary
``error.yaml`` when a child leaf fails.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from loom.engine.models import LoomPlan, LoopBlock, SubgraphSpec, Task


def atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically via temp+rename.

    Public helper: shared by store.py, cli_run.py, scaffold/graph.py, and
    plan.py so all workdir-side writes go through the same tmp+rename
    dance. Creates parent directories as needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    tmp.replace(path)


def _numbered_name(index: int, task_id: str) -> str:
    """Two-digit prefix folder name; index is 1-based plan order.

    The ``:02d`` zero-pad makes folder listings sort lexicographically
    to plan order, but implicitly caps task count at 99 (and loop
    rounds at 99, since ``iter_folder`` / ``begin_round`` use the
    same width). Widen the pad here and in those two helpers if a
    real plan ever approaches the cap.
    """
    flat = task_id.replace("/", "__")
    return f"{index:02d}-{flat}"


def task_folder(workdir: Path, plan: LoomPlan, task_id: str) -> Path:
    """Return the per-task subdirectory under ``<workdir>/tasks/``."""
    for idx, t in enumerate(plan.tasks, start=1):
        if isinstance(t, Task) and t.id == task_id:
            return Path(workdir) / "tasks" / _numbered_name(idx, task_id)
    raise KeyError(task_id)


def iter_folder(workdir: Path, plan: LoomPlan, task_id: str, iteration: int) -> Path:
    """Loop iteration sub-folder ``iter-NN/`` under the task folder."""
    return task_folder(workdir, plan, task_id) / f"iter-{iteration:02d}"


def _iter_dirs(folder: Path) -> list[Path]:
    """Sorted list of existing ``iter-NN`` subdirs of a task folder."""
    if not folder.exists():
        return []
    out = []
    for d in folder.iterdir():
        if d.is_dir() and d.name.startswith("iter-") and d.name[len("iter-"):].isdigit():
            out.append(d)
    return sorted(out, key=lambda p: int(p.name[len("iter-"):]))


def completed_iter_indices(folder: Path) -> list[int]:
    """Sorted indices of iter dirs that contain an output.yaml."""
    return sorted(
        int(d.name[len("iter-"):])
        for d in _iter_dirs(folder)
        if (d / "output.yaml").exists()
    )


def next_round_index(folder: Path) -> int:
    """Index :func:`begin_round` would assign to the next activation.

    One past the highest existing iter dir; 0 when none exist. Pure
    read — creates nothing.
    """
    existing = _iter_dirs(folder)
    return (int(existing[-1].name[len("iter-"):]) + 1) if existing else 0


def begin_round(folder: Path) -> Path:
    """Create and return the iter dir for a fresh loop round.

    Called once per round when a loop-body task is activated. The new
    index is one past the highest existing iter dir, so each activation
    gets its own round directory.
    """
    folder.mkdir(parents=True, exist_ok=True)
    existing = _iter_dirs(folder)
    nxt = (int(existing[-1].name[len("iter-"):]) + 1) if existing else 0
    d = folder / f"iter-{nxt:02d}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def round_folder(folder: Path, *, is_loop_body: bool) -> Path:
    """WRITE-side folder for the current round.

    For a non-loop task this is the task folder itself. For a loop-body
    task it is the latest ``iter-NN/`` dir — round identity comes from
    the directory existing, not from whether output.yaml has been
    written, so the path is stable within a round across ``next`` and
    ``complete``. Round advancement is exclusively ``begin_round``'s
    job; before the first call this falls back to ``iter-00``.
    """
    if not is_loop_body:
        return folder
    existing = _iter_dirs(folder)
    return existing[-1] if existing else folder / "iter-00"


def output_read_path(folder: Path, *, is_loop_body: bool) -> Path:
    """READ path: the output.yaml a consumer should read.

    For a non-loop task the flat ``<folder>/output.yaml``. For a
    loop-body task the latest *completed* round's output (highest
    ``iter-NN/`` containing an output.yaml).
    """
    if not is_loop_body:
        return folder / "output.yaml"
    completed = [d for d in _iter_dirs(folder) if (d / "output.yaml").exists()]
    if completed:
        return completed[-1] / "output.yaml"
    return folder / "iter-00" / "output.yaml"


def _plan_to_dict(plan: LoomPlan) -> dict[str, Any]:
    """Serialise a LoomPlan to the plan.yaml shape."""
    tasks: list[dict] = []
    for t in plan.tasks:
        if isinstance(t, SubgraphSpec):
            # Post-inlining plans should not carry SubgraphSpec entries.
            # Keep this branch to surface bugs in inline.py.
            raise RuntimeError(
                f"plan still contains SubgraphSpec {t.id!r}; "
                "expand_subgraphs must run before writing plan.yaml"
            )
        entry: dict[str, Any] = {
            "id": t.id,
            "kind": t.kind,
            "folder": str(t.folder) if t.folder else "",
            "status": t.status,
            "iter": t.iter,
        }
        if t.depends_on_all:
            entry["depends_on_all"] = list(t.depends_on_all)
        if t.depends_on_any:
            entry["depends_on_any"] = list(t.depends_on_any)
        if t.when:
            entry["when"] = t.when
        if t.skip_output is not None:
            entry["skip_output"] = t.skip_output
        if t.model is not None:
            entry["model"] = t.model
        if t.latch:
            entry["latch"] = {
                "header": t.latch.header,
                **({"fuel": t.latch.fuel} if t.latch.fuel is not None else {}),
                **({"while_": t.latch.while_} if t.latch.while_ is not None else {}),
            }
        if t.namespace:
            entry["namespace"] = t.namespace
        if t.inlined_from_subgraph:
            entry["inlined_from_subgraph"] = True
        if t.instance_uid:
            entry["instance_uid"] = t.instance_uid
        if t.source_root:
            entry["source_root"] = str(t.source_root)
        if t.pinned_version is not None:
            entry["pinned_version"] = t.pinned_version
        if t.input_mapping is not None:
            entry["input_mapping"] = dict(t.input_mapping)
        tasks.append(entry)
    return {"loom_root": str(plan.loom_root), "tasks": tasks}


def _dict_to_plan(doc: dict[str, Any]) -> LoomPlan:
    """Deserialise plan.yaml into a LoomPlan."""
    tasks: list[Task | SubgraphSpec] = []
    for entry in doc.get("tasks", []):
        latch_dict = entry.get("latch")
        latch = None
        if latch_dict:
            latch = LoopBlock(
                header=latch_dict["header"],
                fuel=latch_dict.get("fuel"),
                while_=latch_dict.get("while_"),
            )
        tasks.append(Task(
            id=entry["id"],
            kind=entry["kind"],
            depends_on_all=entry.get("depends_on_all", []),
            depends_on_any=entry.get("depends_on_any", []),
            when=entry.get("when"),
            skip_output=entry.get("skip_output"),
            model=entry.get("model"),
            latch=latch,
            input_mapping=entry.get("input_mapping"),
            folder=Path(entry["folder"]) if entry.get("folder") else None,
            status=entry.get("status", "pending"),
            iter=entry.get("iter", 0),
            namespace=entry.get("namespace", ""),
            inlined_from_subgraph=entry.get("inlined_from_subgraph", False),
            instance_uid=entry.get("instance_uid"),
            source_root=Path(entry["source_root"]) if entry.get("source_root") else None,
            pinned_version=entry.get("pinned_version"),
        ))
    return LoomPlan(loom_root=Path(doc["loom_root"]), tasks=tasks)


def write_plan_yaml(workdir: Path, plan: LoomPlan) -> None:
    """Atomically write ``<workdir>/plan.yaml``."""
    doc = _plan_to_dict(plan)
    atomic_write(Path(workdir) / "plan.yaml", yaml.safe_dump(doc, sort_keys=False))


def read_plan_yaml(workdir: Path) -> LoomPlan:
    """Load ``<workdir>/plan.yaml`` back into a LoomPlan."""
    doc = yaml.safe_load((Path(workdir) / "plan.yaml").read_text())
    return _dict_to_plan(doc or {})


def write_output_yaml(folder: Path, output: dict[str, Any]) -> None:
    """Write ``folder/output.yaml`` atomically."""
    atomic_write(folder / "output.yaml", yaml.safe_dump(output, sort_keys=False))


def read_output_yaml(folder: Path) -> dict[str, Any]:
    """Read ``folder/output.yaml``. Returns {} if missing."""
    path = folder / "output.yaml"
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def write_error_yaml(
    folder: Path,
    task_id: str,
    kind: str,
    exc: BaseException,
) -> None:
    """Write a leaf error.yaml for a failing task."""
    import traceback as tb

    doc = {
        "task_id": task_id,
        "kind": kind,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(tb.format_exception(exc)),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write(folder / "error.yaml", yaml.safe_dump(doc, sort_keys=False))


def write_subgraph_summary_error(
    subgraph_folder: Path,
    subgraph_id: str,
    failed_task_address: str,
    inner_error_path: Path,
) -> None:
    """Write the aggregate error.yaml at a subgraph parent folder."""
    doc = {
        "task_id": subgraph_id,
        "failed_task": failed_task_address,
        "inner_error_path": str(inner_error_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write(subgraph_folder / "error.yaml", yaml.safe_dump(doc, sort_keys=False))


def write_skip_reason_yaml(
    folder: Path,
    task_id: str,
    reason_kind: str,
    predicate: str | None = None,
) -> None:
    """Write ``folder/skip-reason.yaml`` for a task the runner just skipped.

    ``reason_kind`` is one of ``when-false`` (task's own predicate was
    a clean false) or ``cascade-skip`` (an upstream dep was skipped).
    ``predicate`` is the source ``when`` expression; omitted for
    cascade-skip.
    """
    doc: dict[str, Any] = {
        "task_id": task_id,
        "reason_kind": reason_kind,
    }
    if predicate is not None:
        doc["predicate"] = predicate
    doc["timestamp"] = datetime.now(timezone.utc).isoformat()
    atomic_write(folder / "skip-reason.yaml", yaml.safe_dump(doc, sort_keys=False))


def write_schema_error_yaml(
    folder: Path,
    task_id: str,
    phase: str,
    message: str,
    path: str = "",
) -> None:
    """Write ``folder/schema-error.yaml`` for an input/output validation failure.

    ``phase`` is ``input`` or ``output``. ``path`` is a JSON Pointer
    into the failing document identifying the offending field.
    """
    doc = {
        "phase": phase,
        "task_id": task_id,
        "message": message,
        "path": path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write(folder / "schema-error.yaml", yaml.safe_dump(doc, sort_keys=False))


def write_stderr_yaml(
    folder: Path,
    task_id: str,
    kind: str,
    text: str,
) -> None:
    """Write ``folder/stderr.yaml`` capturing a task body's stderr output.

    Emitted when the body writes non-empty stderr OR when the body
    fails (even if the captured text is empty).
    """
    doc = {
        "task_id": task_id,
        "kind": kind,
        "text": text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write(folder / "stderr.yaml", yaml.safe_dump(doc, sort_keys=False))


_GENERATED_ARTIFACTS = (
    "output.yaml",
    "error.yaml",
    "skip-reason.yaml",
    "schema-error.yaml",
    "stderr.yaml",
    "prompt.md",
    "message.md",
)


def clear_generated_artifacts(folder: Path, *, preserve_input: bool) -> None:
    """Delete engine-generated artifacts for a reset.

    Removes ``output.yaml``, diagnostic YAMLs, rendered bodies, and
    every ``iter-NN/`` round dir. Removes the materialised
    ``input.yaml`` unless ``preserve_input`` is True (entry-task
    pattern: caller-seeded input must survive reset).
    """
    import shutil

    if not folder.exists():
        return
    for name in _GENERATED_ARTIFACTS:
        f = folder / name
        if f.exists():
            f.unlink()
    if not preserve_input:
        inp = folder / "input.yaml"
        if inp.exists():
            inp.unlink()
    for d in _iter_dirs(folder):
        shutil.rmtree(d, ignore_errors=True)
