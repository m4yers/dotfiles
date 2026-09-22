# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class PoolDrawInput:
    VERSION: ClassVar[int] = 1
    tasks: list
    prev: dict | None

    @classmethod
    def from_dict(cls, d: dict) -> "PoolDrawInput":
        return cls(
            tasks=d["tasks"],
            prev=d["prev"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["tasks"] = self.tasks
        out["prev"] = self.prev
        return out


@dataclass
class PoolDrawOutput:
    VERSION: ClassVar[int] = 1
    cursor: int
    total: int
    current_task: dict

    @classmethod
    def from_dict(cls, d: dict) -> "PoolDrawOutput":
        return cls(
            cursor=d["cursor"],
            total=d["total"],
            current_task=d["current_task"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["cursor"] = self.cursor
        out["total"] = self.total
        out["current_task"] = self.current_task
        return out
