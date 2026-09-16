"""Reserved engine-provided input contract for loomv2.

Two hand-written frozen dataclasses (``LoomMeta``, ``TaskMeta``) mirror
the draft-2020-12 schemas ``schemas/loom-meta.yaml`` and
``schemas/task-meta.yaml`` one-to-one. The classes ARE the typed
contract for reserved fields — no codegen — so extension is a two-file
commit: add the field here AND to the mirror schema.

The engine builds instances at every task dispatch via
``build_reserved_values(task, workdir, task_folder)``. The values are
returned under their wire keys (``__loom``, ``__task``); the scaffold
aliases those keys to ``loom`` / ``task`` at codegen time because
``__``-prefixed dataclass fields hit Python name-mangling.

See ``references/io.md`` §5 for the author-facing contract.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from loom.engine.models import Task


RESERVED_FIELDS = frozenset({"__loom", "__task"})
RESERVED_ALIASES = {"__loom": "loom", "__task": "task"}

# The loom.sh CLI shim of THIS loomv2 installation, derived from the
# package location: reserved.py sits at scripts/loom/loom/engine/, so
# parents[3] is scripts/. Filled into __loom.runtime so templates
# invoke the same runtime that dispatched them instead of hardcoding
# an install path.
_RUNTIME_SH = Path(__file__).resolve().parents[3] / "loom.sh"


@dataclass(frozen=True)
class LoomMeta:
    """Reserved ``__loom`` object mirror.

    SYNC MANDATE: keep in one-to-one correspondence with
    ``schemas/loom-meta.yaml``. Fields here and there change together
    in the same commit.
    """

    workdir: str
    runtime: str

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a wire dict (values are JSON/YAML-compatible)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LoomMeta":
        """Build an instance from a wire dict."""
        return cls(workdir=d["workdir"], runtime=d["runtime"])


@dataclass(frozen=True)
class TaskMeta:
    """Reserved ``__task`` object mirror.

    SYNC MANDATE: keep in one-to-one correspondence with
    ``schemas/task-meta.yaml``. Fields here and there change together
    in the same commit. Deliberately narrowed from the old ambient
    ``task`` dict, which was ``dataclasses.asdict(Task)`` over all
    Task fields.
    """

    id: str
    kind: str
    iter: int
    namespace: str
    workdir: str

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a wire dict (values are JSON/YAML-compatible)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TaskMeta":
        """Build an instance from a wire dict."""
        return cls(
            id=d["id"],
            kind=d["kind"],
            iter=d["iter"],
            namespace=d["namespace"],
            workdir=d["workdir"],
        )


def build_reserved_values(
    task: Task,
    workdir: Path,
    task_folder: Path,
) -> dict[str, dict[str, Any]]:
    """Return the reserved wire dict for ``task``'s dispatch.

    Keys are the reserved wire names (``__loom``, ``__task``); values
    are the ``to_dict()`` output of ``LoomMeta`` / ``TaskMeta`` so
    downstream code (mapping resolution, jsonschema, YAML writer)
    sees plain dicts.
    """
    loom = LoomMeta(workdir=str(workdir), runtime=str(_RUNTIME_SH))
    task_meta = TaskMeta(
        id=task.id,
        kind=task.kind,
        iter=task.iter,
        namespace=task.namespace,
        workdir=str(task_folder),
    )
    return {
        "__loom": loom.to_dict(),
        "__task": task_meta.to_dict(),
    }


def load_meta_schema(name: str) -> dict[str, Any]:
    """Load ``schemas/<name>-meta.yaml`` for the AST validator.

    ``name`` is one of the values in ``RESERVED_ALIASES`` (``loom``,
    ``task``).
    """
    import yaml

    # schemas/ lives at the skill root; this module lives at
    # scripts/loom/loom/engine/. Ascend four levels.
    root = Path(__file__).resolve().parents[4]
    path = root / "schemas" / f"{name}-meta.yaml"
    return yaml.safe_load(path.read_text())
