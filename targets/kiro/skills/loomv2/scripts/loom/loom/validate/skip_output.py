"""Static validation of ``skip_output`` declarations.

A task entry carrying ``skip_output`` promises the engine a default
output to write when its ``when`` predicate is false. Two static
rules keep the promise sound:

1. ``skip_output`` without ``when`` is inert (the default could never
   fire) — reject it as an authoring error.
2. The declared document must validate against the task's
   io.yaml/output schema NOW, so a run never fails at dispatch time
   on a default the author could have checked statically.
"""
from __future__ import annotations

import jsonschema

from loom.engine.models import LoomPlan, Task
from loom.errors import GraphYamlError


def validate_skip_output(plan: LoomPlan) -> None:
    from loom.discovery import load_io_yaml
    from loom.engine.runner import task_source_folder

    for t in plan.tasks:
        if not isinstance(t, Task) or t.skip_output is None:
            continue
        if not t.when:
            raise GraphYamlError(
                f"task {t.id!r} declares `skip_output` without `when` — "
                "the default output could never fire. Fix: add a `when:` "
                "predicate or drop `skip_output`."
            )
        io = load_io_yaml(task_source_folder(plan.loom_root, t))
        try:
            jsonschema.validate(t.skip_output, io.output_schema)
        except jsonschema.ValidationError as exc:
            raise GraphYamlError(
                f"task {t.id!r}: `skip_output` does not validate against "
                f"its io.yaml output schema: {exc.message} | Fix: align "
                "the declared default with the task's output contract."
            ) from exc
