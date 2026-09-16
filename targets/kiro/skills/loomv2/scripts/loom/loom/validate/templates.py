"""Static Jinja template reference validation.

For every task's ``prompt.md.j2`` / ``message.md.j2``, parse the Jinja
AST and enforce contract-locality:

  1. Every top-level undeclared identifier is a subset of ``{"input"}``
     (the only in-scope Jinja name — the validated ``input.yaml``).
  2. Every ``input.<attr>`` reference targets an attribute declared in
     the task's ``io.yaml/input.properties``.
  3. ``input.__loom.<attr>`` / ``input.__task.<attr>`` references must
     be a property of the corresponding meta-schema
     (``schemas/loom-meta.yaml`` / ``schemas/task-meta.yaml``).

Raises :class:`TemplateReferenceError` on the first breach with the
offending name, task id, and template path. Runs in
``_lifecycle._static_validate`` so ``$LOOM validate`` and
``$LOOM runtime init`` reject offending plans before any workdir
write.
"""
from __future__ import annotations

import jinja2
from jinja2 import meta as jinja_meta
from jinja2 import nodes

from loom.engine.models import LoomPlan, Task
from loom.engine.reserved import (
    RESERVED_ALIASES,
    RESERVED_FIELDS,
    load_meta_schema,
)
from loom.errors import TemplateReferenceError


def validate_templates(plan: LoomPlan) -> None:
    """Enforce Jinja-template contract-locality for every task."""
    from loom.discovery import load_io_yaml
    from loom.engine.runner import task_source_folder

    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    for t in plan.tasks:
        if not isinstance(t, Task):
            continue
        if t.kind == "tool":
            continue
        template_name = (
            "prompt.md.j2" if t.kind == "agent" else "message.md.j2"
        )
        source_folder = task_source_folder(plan.loom_root, t)
        template_path = source_folder / template_name
        if not template_path.exists():
            # io.yaml / kind validators flag missing body files separately.
            continue
        source = template_path.read_text()
        try:
            ast = env.parse(source)
        except jinja2.TemplateSyntaxError as exc:
            raise TemplateReferenceError(
                t.id, str(exc), str(template_path)
            ) from exc
        # (1) Top-level names must be ⊆ {"input"}.
        for name in jinja_meta.find_undeclared_variables(ast):
            if name != "input":
                raise TemplateReferenceError(
                    t.id, name, str(template_path)
                )
        io = load_io_yaml(source_folder)
        properties = io.input_schema.get("properties") or {}
        # (2) First-level input.<attr>.
        for node in ast.find_all(nodes.Getattr):
            inner = node.node
            if isinstance(inner, nodes.Name) and inner.name == "input":
                attr = node.attr
                if attr not in properties:
                    raise TemplateReferenceError(
                        t.id, f"input.{attr}", str(template_path)
                    )
        # (3) Second-level on reserved: input.__loom.<attr> / input.__task.<attr>.
        for node in ast.find_all(nodes.Getattr):
            inner = node.node
            if not isinstance(inner, nodes.Getattr):
                continue
            innermost = inner.node
            if not (
                isinstance(innermost, nodes.Name)
                and innermost.name == "input"
            ):
                continue
            first_attr = inner.attr
            if first_attr not in RESERVED_FIELDS:
                continue
            alias = RESERVED_ALIASES[first_attr]
            meta_schema = load_meta_schema(alias)
            meta_props = meta_schema.get("properties") or {}
            second_attr = node.attr
            if second_attr not in meta_props:
                raise TemplateReferenceError(
                    t.id,
                    f"input.{first_attr}.{second_attr}",
                    str(template_path),
                )
