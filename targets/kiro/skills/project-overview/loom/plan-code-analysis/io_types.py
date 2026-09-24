# generated from io.yaml v7 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class PlanCodeAnalysisInput:
    VERSION: ClassVar[int] = 7
    workspace_abs: str
    entrypoints: list
    cache_prefix: str
    blob_prefix: str
    cache_mode: str
    max_batches: str
    index_symbols_path: str
    candidates_path: str
    summary_budget: str

    @classmethod
    def from_dict(cls, d: dict) -> "PlanCodeAnalysisInput":
        return cls(
            workspace_abs=d["workspace_abs"],
            entrypoints=d["entrypoints"],
            cache_prefix=d["cache_prefix"],
            blob_prefix=d["blob_prefix"],
            cache_mode=d["cache_mode"],
            max_batches=d["max_batches"],
            index_symbols_path=d["index_symbols_path"],
            candidates_path=d["candidates_path"],
            summary_budget=d["summary_budget"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["workspace_abs"] = self.workspace_abs
        out["entrypoints"] = self.entrypoints
        out["cache_prefix"] = self.cache_prefix
        out["blob_prefix"] = self.blob_prefix
        out["cache_mode"] = self.cache_mode
        out["max_batches"] = self.max_batches
        out["index_symbols_path"] = self.index_symbols_path
        out["candidates_path"] = self.candidates_path
        out["summary_budget"] = self.summary_budget
        return out


@dataclass
class PlanCodeAnalysisOutput:
    VERSION: ClassVar[int] = 7
    summarize_mode: str
    cached_summaries: list
    batches: list

    @classmethod
    def from_dict(cls, d: dict) -> "PlanCodeAnalysisOutput":
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
