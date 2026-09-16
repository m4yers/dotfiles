"""Scaffolding backends for `$LOOM task new`, `$LOOM task io-python`, `$LOOM graph new`."""
from loom.scaffold.graph import new_graph
from loom.scaffold.task import io_python, new_task

__all__ = ["new_task", "io_python", "new_graph"]
