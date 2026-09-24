"""Nested subgraph inlining: source_root must survive re-prefixing.

Regression: a grandchild task (subgraph within a subgraph) had its
source_root clobbered to the INTERMEDIATE child's root by the outer
expand pass, so folder resolution looked for the grandchild's task
folder under the wrong skill.
"""
import textwrap
from pathlib import Path

import pytest

from loom.engine.inline import expand_subgraphs
from loom.plan import from_graph_yaml


def _write_task(root: Path, tid: str, out_field: str = "val") -> None:
    d = root / tid
    d.mkdir(parents=True)
    (d / "io.yaml").write_text(textwrap.dedent(f"""\
        version: 1
        input:
          type: object
          additionalProperties: false
          properties: {{}}
        output:
          type: object
          additionalProperties: false
          required: [{out_field}]
          properties:
            {out_field}: {{type: string}}
    """))
    (d / "tool.py").write_text("def f():\n    pass\n")


def test_nested_subgraph_source_root_preserved(tmp_path: Path) -> None:
    # grandchild skill
    gc = tmp_path / "grandchild" / "loom"
    _write_task(gc, "gc-task")
    (gc / "graph.yaml").write_text(textwrap.dedent("""\
        tasks:
        - {id: gc-task, kind: tool, version: 1}
    """))
    # child skill embedding grandchild
    ch = tmp_path / "child" / "loom"
    _write_task(ch, "ch-exit")
    (ch / "graph.yaml").write_text(textwrap.dedent("""\
        tasks:
        - id: inner
          kind: subgraph
          version: 1
          root: ../../grandchild/loom
        - id: ch-exit
          kind: tool
          version: 1
          depends_on_all: [inner]
        latches:
        - task: ch-exit
          header: inner
          fuel: 3
          while_: ${task:ch-exit:val} == 'again'
    """))
    # parent embedding child
    pa = tmp_path / "parent" / "loom"
    _write_task(pa, "pa-exit")
    (pa / "graph.yaml").write_text(textwrap.dedent("""\
        tasks:
        - id: mid
          kind: subgraph
          version: 1
          root: ../../child/loom
        - id: pa-exit
          kind: tool
          version: 1
          depends_on_all: [mid]
    """))

    plan = expand_subgraphs(from_graph_yaml(pa))
    by_id = {t.id: t for t in plan.tasks}
    gc_task = by_id["mid/inner/gc-task"]
    assert gc_task.source_root == (gc).resolve(), gc_task.source_root
    ch_task = by_id["mid/ch-exit"]
    assert ch_task.source_root == (ch).resolve(), ch_task.source_root
    # latch carried by a subgraph task is re-anchored into the namespace
    assert ch_task.latch is not None
    assert ch_task.latch.header == "mid/inner"
    assert "${task:mid/ch-exit:val}" in ch_task.latch.while_
