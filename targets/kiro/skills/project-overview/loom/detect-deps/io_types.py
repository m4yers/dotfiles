# generated from io.yaml v2 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class DetectDepsInput:
    VERSION: ClassVar[int] = 2
    workspace_abs: str
    cache_prefix: str
    cache_mode: str

    @classmethod
    def from_dict(cls, d: dict) -> "DetectDepsInput":
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
class DetectDepsOutput:
    VERSION: ClassVar[int] = 2
    dependencies: list
    unresolved_imports: list
    grep_tool: str
    cache_hit: bool

    @classmethod
    def from_dict(cls, d: dict) -> "DetectDepsOutput":
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
