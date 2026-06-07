'''loom error hierarchy.

Two families:
  - LoomPlanError(ValueError): plan-time errors raised by loom.init / loom.extend
    when the plan fails static validation (DAG, schemas, references, types).
  - Runtime errors (RuntimeError subclasses): raised during execution by
    LoomRuntime methods.

Workdir errors are ValueError subclasses raised by loom.init.
'''
from __future__ import annotations


# ---- plan-time validation errors ----

class LoomPlanError(ValueError):
    '''Base class for static-validation failures at loom.init / loom.extend.'''


class DAGError(LoomPlanError):
    '''Cycle, missing dependency, or duplicate task id.'''


class SchemaError(LoomPlanError):
    '''output_schema file missing, unparseable, or itself not valid JSON Schema.'''


class ReferenceError(LoomPlanError):
    '''A ${task:id:...} reference targets a non-existent task id, or a JMESPath
    field path doesn't resolve against the referenced task's output_schema.'''


class TypeMismatchError(LoomPlanError):
    '''A predicate's comparison literal is incompatible with the referenced
    field's declared type.'''


# ---- loop-admission errors ----

class LoopError(LoomPlanError):
    '''Base for loop-admission failures at loom.init / loom.extend.'''


class NoExitConditionError(LoopError):
    '''A `latch:` block declares neither `fuel` nor `while`, so the loop
    has no declared way out. This is the only exit-related check loom
    enforces; it is deliberately not a termination proof (a huge `fuel`
    still "terminates" but never ends in practice).'''
    def __init__(self, task_id: str):
        super().__init__(
            f'loop latch {task_id!r}: declare at least one of '
            f'`fuel` / `while`')
        self.task_id = task_id


class IrreducibleLoopError(LoopError):
    '''A back-edge `n -> h` whose target `h` does not dominate `n`, or a
    header with more than one back-edge. Only reducible (natural) loops
    are admitted.'''


class LoopEscapeError(LoopError):
    '''An edge crosses a loop region's boundary other than entering through
    the header or leaving through the latch (the hammock / single-entry
    single-exit property).'''


class LoopNestingError(LoopError):
    '''Two loop regions overlap without one being wholly nested inside the
    other's body.'''


# ---- workdir errors ----

class WorkdirExistsError(ValueError):
    '''loom.init was called with a workdir that already contains plan.yaml.
    Caller should use loom.resume() to re-attach.'''


class WorkdirNotEmptyError(ValueError):
    '''loom.init was called with a workdir that contains files but no plan.yaml.
    Loom does not clobber arbitrary directories.'''


# ---- runtime errors ----

class RunFailed(RuntimeError):
    '''A tool task subprocess exited non-zero.'''
    def __init__(self, task_id: str, message: str):
        super().__init__(f'task {task_id!r} failed: {message}')
        self.task_id = task_id
        self.message = message


class OutputSchemaError(RuntimeError):
    '''A task's written output.yaml does not validate against its output_schema.'''
    def __init__(self, task_id: str, message: str):
        super().__init__(f'task {task_id!r} output schema validation failed: {message}')
        self.task_id = task_id
        self.message = message


class RenderFailed(RuntimeError):
    '''Jinja rendering of a task's prompt template failed.'''
    def __init__(self, task_id: str, template_path: str, message: str):
        super().__init__(f'task {task_id!r} prompt render failed [{template_path}]: {message}')
        self.task_id = task_id
        self.template_path = template_path
        self.message = message


class RunAborted(RuntimeError):
    '''The plan has at least one task in ``failed`` status; the run
    cannot continue. Raised by ``LoomRuntime.next()`` when it
    detects pre-existing failures from prior dispatches.

    Failure is contagious at the run level: a single failed task
    halts further scheduling. In-flight tasks finish naturally
    (their results are persisted) but no new tasks are dispatched.
    Orchestrators surface this exception to the user as a
    run-level error.

    The first failed task id is stored on ``task_id`` for
    parity with other RuntimeErrors; the full list is on
    ``failed_task_ids``.
    '''
    def __init__(self, failed_task_ids: list[str]):
        ids = list(failed_task_ids)
        if not ids:
            raise ValueError(
                'RunAborted requires at least one failed task id')
        joined = ', '.join(repr(i) for i in ids)
        super().__init__(f'run aborted; failed tasks: {joined}')
        self.failed_task_ids = ids
        self.task_id = ids[0]
        self.message = f'failed tasks: {joined}'
