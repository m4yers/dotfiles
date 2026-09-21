# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class DepAnalysisInput:
    VERSION: ClassVar[int] = 1
    workspace_abs: str
    cache_dir: str
    cache_mode: str

    @classmethod
    def from_dict(cls, d: dict) -> "DepAnalysisInput":
        return cls(
            workspace_abs=d["workspace_abs"],
            cache_dir=d["cache_dir"],
            cache_mode=d["cache_mode"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["workspace_abs"] = self.workspace_abs
        out["cache_dir"] = self.cache_dir
        out["cache_mode"] = self.cache_mode
        return out


@dataclass
class DepAnalysisOutput:
    VERSION: ClassVar[int] = 1
    dependencies: list
    unresolved_imports: list
    grep_tool: str
    cache_hit: bool

    @classmethod
    def from_dict(cls, d: dict) -> "DepAnalysisOutput":
        return cls(
            dependencies=d["dependencies"],
            unresolved_imports=d["unresolved_imports"],
            grep_tool=d["grep_tool"],
            cache_hit=d["cache_hit"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["dependencies"] = self.dependencies
        out["unresolved_imports"] = self.unresolved_imports
        out["grep_tool"] = self.grep_tool
        out["cache_hit"] = self.cache_hit
        return out
