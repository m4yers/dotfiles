# generated from io.yaml v3 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar
from loom.engine.reserved import LoomMeta, TaskMeta


@dataclass
class SummariseFilesInput:
    VERSION: ClassVar[int] = 3
    workspace_abs: str
    files: list
    blob_prefix: str
    cache_mode: str
    loom: LoomMeta
    task: TaskMeta

    @classmethod
    def from_dict(cls, d: dict) -> "SummariseFilesInput":
        return cls(
            workspace_abs=d["workspace_abs"],
            files=d["files"],
            blob_prefix=d["blob_prefix"],
            cache_mode=d["cache_mode"],
            loom=LoomMeta.from_dict(d["__loom"]),
            task=TaskMeta.from_dict(d["__task"]),
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["workspace_abs"] = self.workspace_abs
        out["files"] = self.files
        out["blob_prefix"] = self.blob_prefix
        out["cache_mode"] = self.cache_mode
        out["__loom"] = self.loom.to_dict()
        out["__task"] = self.task.to_dict()
        return out


@dataclass
class SummariseFilesOutput:
    VERSION: ClassVar[int] = 3
    summaries: list

    @classmethod
    def from_dict(cls, d: dict) -> "SummariseFilesOutput":
        return cls(
            summaries=d["summaries"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["summaries"] = self.summaries
        return out
