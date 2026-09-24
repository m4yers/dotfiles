# generated from io.yaml v4 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class IndexSymbolsInput:
    VERSION: ClassVar[int] = 4
    workspace_abs: str
    cache_prefix: str | None = None
    cache_mode: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "IndexSymbolsInput":
        return cls(
            workspace_abs=d["workspace_abs"],
            cache_prefix=d.get("cache_prefix"),
            cache_mode=d.get("cache_mode"),
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["workspace_abs"] = self.workspace_abs
        if self.cache_prefix is not None:
            out["cache_prefix"] = self.cache_prefix
        if self.cache_mode is not None:
            out["cache_mode"] = self.cache_mode
        return out


@dataclass
class IndexSymbolsOutput:
    VERSION: ClassVar[int] = 4
    index_path: str
    files_indexed: int
    symbols_total: int
    tags_tool: str

    @classmethod
    def from_dict(cls, d: dict) -> "IndexSymbolsOutput":
        return cls(
            index_path=d["index_path"],
            files_indexed=d["files_indexed"],
            symbols_total=d["symbols_total"],
            tags_tool=d["tags_tool"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["index_path"] = self.index_path
        out["files_indexed"] = self.files_indexed
        out["symbols_total"] = self.symbols_total
        out["tags_tool"] = self.tags_tool
        return out
