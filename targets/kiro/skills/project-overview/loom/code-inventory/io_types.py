# generated from io.yaml v3 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class CodeInventoryInput:
    VERSION: ClassVar[int] = 3
    workspace_abs: str
    cache_prefix: str
    cache_mode: str

    @classmethod
    def from_dict(cls, d: dict) -> "CodeInventoryInput":
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
class CodeInventoryOutput:
    VERSION: ClassVar[int] = 3
    total_files: int
    total_bytes: int
    languages: list
    top_dirs: list
    entrypoints: list
    candidate_files: list
    cache_hit: bool

    @classmethod
    def from_dict(cls, d: dict) -> "CodeInventoryOutput":
        return cls(
            total_files=d["total_files"],
            total_bytes=d["total_bytes"],
            languages=d["languages"],
            top_dirs=d["top_dirs"],
            entrypoints=d["entrypoints"],
            candidate_files=d["candidate_files"],
            cache_hit=d["cache_hit"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["total_files"] = self.total_files
        out["total_bytes"] = self.total_bytes
        out["languages"] = self.languages
        out["top_dirs"] = self.top_dirs
        out["entrypoints"] = self.entrypoints
        out["candidate_files"] = self.candidate_files
        out["cache_hit"] = self.cache_hit
        return out
