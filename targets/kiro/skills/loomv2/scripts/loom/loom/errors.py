"""Loom exception hierarchy.

The class hierarchy IS the errors documentation. Every subclass carries:

  1. A docstring stating the CAUSE.
  2. A class-level ``remedy: str`` attribute stating the concrete FIX.

``LoomPlanError.__init__`` concatenates docstring + remedy into ``__str__``
so runtime output IS the remediation doc.
"""
from __future__ import annotations

from pathlib import Path


class LoomPlanError(Exception):
    """Base class for plan-time validation failures at loom.init / loom.extend."""

    remedy: str = "Fix the plan before retrying init/extend."

    def __init__(self, message: str = ""):
        self._message = message
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        cause = (self.__class__.__doc__ or "").strip().split("\n")[0]
        parts = [cause]
        if self._message:
            parts.append(self._message)
        if self.remedy:
            parts.append(f"Fix: {self.remedy}")
        return " | ".join(p for p in parts if p)


# ---- DAG errors ----

class DAGError(LoomPlanError):
    """Cycle, missing dependency, duplicate id, or empty dep list."""

    remedy = "Ensure task ids are unique, deps target existing ids, and the graph is acyclic."


class MultipleEntriesError(LoomPlanError):
    """Graph has more than one task with no incoming edges."""

    remedy = "Collapse roots to a single entry task or make secondary roots depend on the entry."


class MultipleExitsError(LoomPlanError):
    """Graph has more than one task with no outgoing edges."""

    remedy = "Add a fan-in task that depends_on_all leaves so the graph has one exit."


# ---- Folder / kind / io.yaml / graph.yaml ----

class TaskFolderError(LoomPlanError):
    """Task folder missing, malformed, or collides with an existing folder."""

    remedy = "Use `$LOOM task new` to scaffold task folders."


class IOYamlError(LoomPlanError):
    """`io.yaml` missing, malformed, or fails the io.yaml meta-schema."""

    remedy = "Validate against schemas/io.yaml; ensure version (int, >=1), input, output keys."


class GraphYamlError(LoomPlanError):
    """`graph.yaml` missing, malformed, or fails the graph.yaml meta-schema."""

    remedy = "Validate against schemas/graph.yaml; use `$LOOM graph new` for a starter."


class KindMismatchError(LoomPlanError):
    """Task folder body files do not match a single kind (tool/agent/human)."""

    remedy = "Exactly one of tool.py, prompt.md.j2, message.md.j2 per task folder."


# ---- Schema / references / types ----

class SchemaError(LoomPlanError):
    """An input or output JSON Schema fragment is invalid."""

    remedy = "Validate the schema fragment as JSON Schema draft 2020-12."


class ReferenceError(LoomPlanError):
    """A ${task:<addr>} reference targets a non-existent task or bad JMESPath."""

    remedy = "Check the canonical address and JMESPath against the target io.yaml/output."


class TypeMismatchError(LoomPlanError):
    """Type contract violated: either a comparator literal is
    incompatible with the declared field type, OR a producer/consumer
    ``input_mapping`` wiring fails the static subtype-projection check
    (see ``loom.validate.subtype``)."""

    remedy = (
        "For predicate-literal failures, match the literal type to the "
        "field type declared in io.yaml/output. For input_mapping "
        "failures, align the producer io.yaml/output projection with "
        "the consumer io.yaml/input field type (types, enum, const, "
        "numeric bounds, required-superset, or nullability); the "
        "message names the (producer, JMESPath, consumer field) triple."
    )


class TemplateReferenceError(LoomPlanError):
    """Template references a name or attribute not declared in the task's
    io.yaml/input."""

    remedy = (
        "Declare the name in the task's io.yaml/input.properties; the "
        "reserved objects `__loom` / `__task` are opt-in and documented "
        "in references/io.md."
    )

    def __init__(self, task_id: str, name: str, template_path: str):
        self.task_id = task_id
        self.name = name
        self.template_path = template_path
        super().__init__(
            f"task {task_id!r}: template {template_path} references "
            f"undeclared {name!r}"
        )


class ReservedShadowError(LoomPlanError):
    """`graph.yaml` `input:` mapping key shadows a reserved engine-provided
    input name (`__loom` or `__task`)."""

    remedy = (
        "Remove the reserved key from the graph.yaml input mapping; "
        "the engine fills reserved objects at dispatch. See "
        "references/io.md."
    )

    def __init__(
        self,
        task_id: str,
        *,
        field: str,
        doc: str = "references/io.md",
    ):
        self.task_id = task_id
        self.field = field
        self.doc = doc
        super().__init__(
            f"task {task_id!r}: input mapping key {field!r} shadows a "
            f"reserved engine-provided name (see {doc})"
        )


# ---- Loop admission ----

class NoExitConditionError(LoomPlanError):
    """Loop latch has neither `fuel` nor `while_`."""

    remedy = "Declare at least one of fuel (int) or while_ (predicate) on the latch."


class IrreducibleLoopError(LoomPlanError):
    """Back-edge target does not dominate the latch, or a header has multiple latches."""

    remedy = "Rewrite the loop so the header dominates the latch and each header has one latch."


class LoopEscapeError(LoomPlanError):
    """Edge crosses a loop region boundary other than into the header or out of the latch."""

    remedy = "Route all inflow through the header and all outflow through the latch."


class LoopNestingError(LoomPlanError):
    """Loop regions overlap or are nested illegally."""

    remedy = "Make loop bodies pairwise disjoint or wholly nested."


# ---- Subgraph / namespace / version pin ----

class SubgraphContractError(LoomPlanError):
    """Parent binding to a subgraph violates the child entry/exit contract."""

    remedy = "Match parent inputs to child entry io.yaml/input and consumers to child exit io.yaml/output."


class NamespaceCollisionError(LoomPlanError):
    """Sibling subgraph instance ids or task ids collide under one namespace."""

    remedy = "Pick a distinct instance id for each subgraph() call at the same nesting level."


class TaskVersionMismatchError(LoomPlanError):
    """Pinned io.yaml version in graph.yaml differs from current version on disk."""

    remedy = "Either re-pin the graph.yaml via `$LOOM graph new`, or revert the io.yaml bump."

    def __init__(
        self,
        canonical_address: str,
        pinned_version: int,
        current_version: int,
        graph_yaml: Path,
    ):
        self.canonical_address = canonical_address
        self.pinned_version = pinned_version
        self.current_version = current_version
        self.graph_yaml = graph_yaml
        message = (
            f"task {canonical_address!r}: pinned v{pinned_version} in "
            f"{graph_yaml}, current v{current_version} on disk"
        )
        super().__init__(message)


class ToolIOVersionMismatchError(LoomPlanError):
    """Generated <TaskName>Input/Output VERSION differs from current io.yaml on disk."""

    remedy = "Run `$LOOM task io-python <task-id>` to regenerate io_types.py."

    def __init__(
        self,
        task_id: str,
        class_version: int | None,
        io_version: int,
    ):
        self.task_id = task_id
        self.class_version = class_version
        self.io_version = io_version
        message = (
            f"task {task_id!r}: tool.py classes pinned v{class_version}, "
            f"io.yaml on disk v{io_version}"
        )
        super().__init__(message)


# ---- Workdir ----

class WorkdirExistsError(LoomPlanError):
    """`loom.init` called on a workdir that already contains plan.yaml."""

    remedy = "Use loom.resume() to re-attach or pick a fresh workdir."


class WorkdirNotEmptyError(LoomPlanError):
    """`loom.init` called on a workdir with unrecognised contents."""

    remedy = "Empty the workdir or point at a fresh path."


class SeedNotAllowedError(LoomPlanError):
    """`runtime init --set` used on an entry task that has an `input:`
    mapping declared in graph.yaml."""

    remedy = (
        "Either remove the `input:` mapping from the entry task in "
        "graph.yaml, or drop `--set` and let the mapping resolve at "
        "the first `runtime next`."
    )


# ---- Runtime ----

class RunFailed(RuntimeError):
    """Task body raised or a tool exited non-zero."""

    remedy = "Read error.yaml in the task folder for the underlying exception."

    def __init__(self, task_id: str, message: str):
        self.task_id = task_id
        self.message = message
        super().__init__(f"task {task_id!r} failed: {message}")


class RunAborted(RuntimeError):
    """The plan has at least one failed task; the run cannot continue."""

    remedy = "Inspect the failed task's error.yaml, fix, and start a fresh run."

    def __init__(self, failed_task_ids: list[str]):
        if not failed_task_ids:
            raise ValueError("RunAborted requires at least one failed task id")
        self.failed_task_ids = list(failed_task_ids)
        joined = ", ".join(repr(i) for i in self.failed_task_ids)
        super().__init__(f"run aborted; failed tasks: {joined}")


class OutputSchemaError(RuntimeError):
    """A task's output.yaml does not validate against io.yaml/output."""

    remedy = "Rewrite output.yaml to match the declared output schema."

    def __init__(self, task_id: str, message: str):
        self.task_id = task_id
        self.message = message
        super().__init__(f"task {task_id!r} output invalid: {message}")


class InputSchemaError(RuntimeError):
    """A task's input.yaml does not validate against io.yaml/input."""

    remedy = "Fix the producer of input.yaml or update io.yaml/input to accept the shape."

    def __init__(self, task_id: str, message: str):
        self.task_id = task_id
        self.message = message
        super().__init__(f"task {task_id!r} input invalid: {message}")


class PredicateEvalError(RuntimeError):
    """A `when` or `while_` predicate could not be evaluated (parse error,
    unresolvable ref, or JMESPath failure). Halts the run — only a clean
    boolean skips a task or stops a loop."""

    remedy = "Fix the predicate expression or ensure its refs resolve before dispatch."

    def __init__(self, expr: str, message: str):
        self.expr = expr
        self.message = message
        super().__init__(f"predicate {expr!r} failed to evaluate: {message}")


class RenderFailed(RuntimeError):
    """Jinja render of prompt.md.j2 / message.md.j2 failed."""

    remedy = "Fix the template or the input.yaml context it references."

    def __init__(self, task_id: str, template_path: str, message: str):
        self.task_id = task_id
        self.template_path = template_path
        self.message = message
        super().__init__(
            f"task {task_id!r} render failed [{template_path}]: {message}"
        )


class ToolTaskError(RuntimeError):
    """tool.py raised, returned wrong type, or the function is missing."""

    remedy = "Inspect error.yaml; the function name must equal snake_case(task id)."

    def __init__(self, task_id: str, message: str):
        self.task_id = task_id
        self.message = message
        super().__init__(f"tool task {task_id!r}: {message}")
