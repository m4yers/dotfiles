"""Regression: `$LOOM validate <skill-root> --graph loom/<variant>.yaml`.

The loom root MUST be derived from the resolved graph file's own
directory. Previously the graph file resolved under
``<positional>/loom/`` while ``ref:`` folders (and subgraph roots)
resolved under ``<positional>/``, so validating a skill root with a
relative ``--graph`` rejected valid graphs with TaskRefError.
"""
from __future__ import annotations

import textwrap

import yaml


def _seed_tool_task(folder, name):
    task = folder / name
    task.mkdir(parents=True)
    (task / "io.yaml").write_text(textwrap.dedent("""\
        version: 1
        input:
          type: object
          additionalProperties: false
          properties:
            word: {type: string}
          required: [word]
        output:
          type: object
          additionalProperties: false
          properties:
            echoed: {type: string}
          required: [echoed]
    """))
    fn = name.replace("-", "_")
    (task / "tool.py").write_text(textwrap.dedent(f"""\
        from io_types import {_camel(name)}Input, {_camel(name)}Output


        def {fn}(inp):
            return {_camel(name)}Output(echoed=inp.word)
    """))


def _camel(name: str) -> str:
    return "".join(p.capitalize() for p in name.split("-"))


def _write_graph(loom_root, filename, tasks):
    (loom_root / filename).write_text(yaml.safe_dump({"tasks": tasks}, sort_keys=False))


def _skill_with_variant_graph(tmp_path):
    """Skill root with tasks + a variant graph under <skill>/loom/."""
    skill = tmp_path / "myskill"
    loom_root = skill / "loom"
    _seed_tool_task(loom_root, "echo")
    _write_graph(loom_root, "graph-x.yaml", [
        {"id": "first", "kind": "tool", "version": 1, "ref": "echo",
         "input": {"word": "hi"}},
        {"id": "second", "kind": "tool", "version": 1, "ref": "echo",
         "depends_on_all": ["first"],
         "input": {"word": "${task:first:echoed}"}},
    ])
    return skill


def test_validate_skill_root_with_relative_graph_resolves_refs(tmp_path):
    from loom.__main__ import main

    skill = _skill_with_variant_graph(tmp_path)
    rc = main(["validate", str(skill), "--graph", "loom/graph-x.yaml"])
    assert rc == 0


def test_validate_absolute_graph_path(tmp_path):
    from loom.__main__ import main

    skill = _skill_with_variant_graph(tmp_path)
    rc = main(["validate", str(skill),
               "--graph", str(skill / "loom" / "graph-x.yaml")])
    assert rc == 0


def test_validate_loom_root_positional_with_bare_graph_name(tmp_path):
    from loom.__main__ import main

    skill = _skill_with_variant_graph(tmp_path)
    rc = main(["validate", str(skill / "loom"), "--graph", "graph-x.yaml"])
    assert rc == 0


def test_validate_skill_root_default_falls_back_to_loom_graph_yaml(tmp_path):
    """Docs: `validate <skill-root>` (no --graph) validates
    <skill-root>/loom/graph.yaml."""
    from loom.__main__ import main

    skill = tmp_path / "myskill"
    loom_root = skill / "loom"
    _seed_tool_task(loom_root, "echo")
    _write_graph(loom_root, "graph.yaml", [
        {"id": "echo", "kind": "tool", "version": 1,
         "input": {"word": "hi"}},
    ])
    rc = main(["validate", str(skill)])
    assert rc == 0


def test_from_graph_yaml_plan_loom_root_is_graph_dir(tmp_path):
    from loom.plan import from_graph_yaml

    skill = _skill_with_variant_graph(tmp_path)
    plan = from_graph_yaml(skill, "loom/graph-x.yaml")
    assert plan.loom_root == (skill / "loom")
    # ref folders resolved under the graph's own directory
    for t in plan.tasks:
        assert str(t.folder).startswith(str((skill / "loom").resolve())) or \
            t.folder.name == "echo"
