# generated from io.yaml v5 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class InventoryCodeInput:
    VERSION: ClassVar[int] = 5
    workspace_abs: str
    cache_prefix: str
    cache_mode: str

    @classmethod
    def from_dict(cls, d: dict) -> "InventoryCodeInput":
        return cls(
            workspace_abs=d["workspace_abs"],
            cache_prefix=d["cache_prefix"],
            cache_mode=d["cache_mode"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["workspace_abs"] = self.workspace_abs
        out["cache_prefix"] = self.cache_prefix
        out["cache_mode"] = self.cache_mode
        return out


@dataclass
class InventoryCodeOutput:
    VERSION: ClassVar[int] = 5
    total_files: int
    total_bytes: int
    languages: list
    top_dirs: list
    entrypoints: list
    cache_hit: bool
    candidates_path: str
    candidates_total: int

    @classmethod
    def from_dict(cls, d: dict) -> "InventoryCodeOutput":
        return cls(
            total_files=d["total_files"],
            total_bytes=d["total_bytes"],
            languages=d["languages"],
            top_dirs=d["top_dirs"],
            entrypoints=d["entrypoints"],
            cache_hit=d["cache_hit"],
            candidates_path=d["candidates_path"],
            candidates_total=d["candidates_total"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["total_files"] = self.total_files
        out["total_bytes"] = self.total_bytes
        out["languages"] = self.languages
        out["top_dirs"] = self.top_dirs
        out["entrypoints"] = self.entrypoints
        out["cache_hit"] = self.cache_hit
        out["candidates_path"] = self.candidates_path
        out["candidates_total"] = self.candidates_total
        return out
