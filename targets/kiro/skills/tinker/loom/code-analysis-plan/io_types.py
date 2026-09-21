# generated from io.yaml v2 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class CodeAnalysisPlanInput:
    VERSION: ClassVar[int] = 2
    workspace_abs: str
    total_files: int
    files: list
    entrypoints: list
    cache_dir: str
    cache_mode: str
    symbol_index_path: str

    @classmethod
    def from_dict(cls, d: dict) -> "CodeAnalysisPlanInput":
        return cls(
            workspace_abs=d["workspace_abs"],
            total_files=d["total_files"],
            files=d["files"],
            entrypoints=d["entrypoints"],
            cache_dir=d["cache_dir"],
            cache_mode=d["cache_mode"],
            symbol_index_path=d["symbol_index_path"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["workspace_abs"] = self.workspace_abs
        out["total_files"] = self.total_files
        out["files"] = self.files
        out["entrypoints"] = self.entrypoints
        out["cache_dir"] = self.cache_dir
        out["cache_mode"] = self.cache_mode
        out["symbol_index_path"] = self.symbol_index_path
        return out


@dataclass
class CodeAnalysisPlanOutput:
    VERSION: ClassVar[int] = 2
    summarize_mode: str
    cached_summaries: list
    batches: list

    @classmethod
    def from_dict(cls, d: dict) -> "CodeAnalysisPlanOutput":
        return cls(
            summarize_mode=d["summarize_mode"],
            cached_summaries=d["cached_summaries"],
            batches=d["batches"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["summarize_mode"] = self.summarize_mode
        out["cached_summaries"] = self.cached_summaries
        out["batches"] = self.batches
        return out
