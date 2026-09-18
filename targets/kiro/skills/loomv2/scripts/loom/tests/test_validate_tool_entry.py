"""Static ``validate_tool_entry`` pass — ambiguity and shim-executable rules."""
from __future__ import annotations

import stat
from pathlib import Path

import pytest
import yaml

from loom.errors import AmbiguousToolEntryError, ToolShimNotExecutableError


_IO_YAML = yaml.safe_dump({
    "version": 1,
    "input": {
        "type": "object",
        "additionalProperties": False,
        "properties": {"greeting": {"type": "string"}},
        "required": ["greeting"],
    },
    "output": {
        "type": "object",
        "additionalProperties": False,
        "properties": {"banner": {"type": "string"}},
        "required": ["banner"],
    },
})


def _seed_shell_task(root: Path, *, executable: bool, shebang: bool) -> Path:
    """Seed a `<root>/banner` tool.sh task."""
    folder = root / "banner"
    folder.mkdir(parents=True)
    (folder / "io.yaml").write_text(_IO_YAML)
    tool_sh = folder / "tool.sh"
    body = "#!/usr/bin/env bash\nexit 0\n" if shebang else "exit 0\n"
    tool_sh.write_text(body)
    if executable:
        mode = tool_sh.stat().st_mode | stat.S_IXUSR
        tool_sh.chmod(mode)
    else:
        # Strip owner-execute bit; leave everything else intact.
        mode = tool_sh.stat().st_mode & ~stat.S_IXUSR
        tool_sh.chmod(mode)
    return folder


def _write_graph(root: Path, entries: list[dict]) -> None:
    (root / "graph.yaml").write_text(
        yaml.safe_dump({"tasks": entries}, sort_keys=False)
    )


def test_happy_shell_task_passes_validate_and_init(tmp_path):
    """A tool.sh task with chmod +x and #!/usr/bin/env bash passes
    both `$LOOM validate` and `$LOOM runtime init` cleanly."""
    from loom import init
    from loom.__main__ import main

    root = tmp_path / "loom"
    _seed_shell_task(root, executable=True, shebang=True)
    _write_graph(root, [{"id": "banner", "kind": "tool", "version": 1}])

    # $LOOM validate
    rc = main(["validate", str(root)])
    assert rc == 0

    # $LOOM runtime init — no workdir write on the failure path (there
    # is no failure here; this checks the happy path).
    workdir = tmp_path / "wd"
    runtime = init(workdir, loom_root=root)
    assert (workdir / "plan.yaml").exists()
    assert any(t.id == "banner" for t in runtime.plan.tasks)


def test_missing_executable_bit_raises_at_validate(tmp_path):
    from loom.__main__ import main

    root = tmp_path / "loom"
    _seed_shell_task(root, executable=False, shebang=True)
    _write_graph(root, [{"id": "banner", "kind": "tool", "version": 1}])

    rc = main(["validate", str(root)])
    assert rc == 1


def test_missing_executable_bit_raises_at_init(tmp_path):
    from loom import init

    root = tmp_path / "loom"
    _seed_shell_task(root, executable=False, shebang=True)
    _write_graph(root, [{"id": "banner", "kind": "tool", "version": 1}])

    workdir = tmp_path / "wd"
    with pytest.raises(ToolShimNotExecutableError):
        init(workdir, loom_root=root)
    # Nothing-written-on-init-failure invariant: no plan.yaml was
    # written (the workdir dir itself is created before validate).
    assert not (workdir / "plan.yaml").exists()


def test_missing_shebang_raises(tmp_path):
    from loom import init
    from loom.__main__ import main

    root = tmp_path / "loom"
    _seed_shell_task(root, executable=True, shebang=False)
    _write_graph(root, [{"id": "banner", "kind": "tool", "version": 1}])

    # $LOOM validate returns non-zero.
    rc = main(["validate", str(root)])
    assert rc == 1

    # Init path raises directly.
    workdir = tmp_path / "wd"
    with pytest.raises(ToolShimNotExecutableError):
        init(workdir, loom_root=root)
    assert not (workdir / "plan.yaml").exists()


def test_both_tool_py_and_tool_sh_raises_at_validate_and_init(tmp_path):
    """A folder carrying BOTH tool.py and tool.sh fails at both
    `$LOOM validate` AND `$LOOM runtime init`. Nothing is written on
    the init failure path."""
    from loom import init
    from loom.__main__ import main

    root = tmp_path / "loom"
    folder = _seed_shell_task(root, executable=True, shebang=True)
    (folder / "tool.py").write_text(
        "def banner(inp):\n    return None\n"
    )
    _write_graph(root, [{"id": "banner", "kind": "tool", "version": 1}])

    # Validate → non-zero exit.
    rc = main(["validate", str(root)])
    assert rc == 1

    # Init → AmbiguousToolEntryError; no plan.yaml written.
    workdir = tmp_path / "wd"
    with pytest.raises(AmbiguousToolEntryError):
        init(workdir, loom_root=root)
    assert not (workdir / "plan.yaml").exists()
