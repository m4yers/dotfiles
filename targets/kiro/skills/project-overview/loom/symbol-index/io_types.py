# generated from io.yaml v3 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class SymbolIndexInput:
    VERSION: ClassVar[int] = 3
    workspace_abs: str

    @classmethod
    def from_dict(cls, d: dict) -> "SymbolIndexInput":
        return cls(
            workspace_abs=d["workspace_abs"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["workspace_abs"] = self.workspace_abs
        return out


@dataclass
class SymbolIndexOutput:
    VERSION: ClassVar[int] = 3
    index_path: str
    files_indexed: int
    symbols_total: int
    tags_tool: str

    @classmethod
    def from_dict(cls, d: dict) -> "SymbolIndexOutput":
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
