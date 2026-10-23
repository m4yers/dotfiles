# generated from io.yaml v2 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar
from loom.engine.reserved import LoomMeta, TaskMeta


@dataclass
class WriteResultInput:
    VERSION: ClassVar[int] = 2
    presentation_runs: list
    loom: LoomMeta
    task: TaskMeta

    @classmethod
    def from_dict(cls, d: dict) -> "WriteResultInput":
        return cls(
            presentation_runs=d["presentation_runs"],
            loom=LoomMeta.from_dict(d["__loom"]),
            task=TaskMeta.from_dict(d["__task"]),
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["presentation_runs"] = self.presentation_runs
        out["__loom"] = self.loom.to_dict()
        out["__task"] = self.task.to_dict()
        return out


@dataclass
class WriteResultOutput:
    VERSION: ClassVar[int] = 2
    header: str
    subsections: list

    @classmethod
    def from_dict(cls, d: dict) -> "WriteResultOutput":
        return cls(
            header=d["header"],
            subsections=d["subsections"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["header"] = self.header
        out["subsections"] = self.subsections
        return out
