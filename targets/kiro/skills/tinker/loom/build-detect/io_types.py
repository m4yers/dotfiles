# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class BuildDetectInput:
    VERSION: ClassVar[int] = 1
    workspace_abs: str
    build_system_override: str
    cache_dir: str
    cache_mode: str

    @classmethod
    def from_dict(cls, d: dict) -> "BuildDetectInput":
        return cls(
            workspace_abs=d["workspace_abs"],
            build_system_override=d["build_system_override"],
            cache_dir=d["cache_dir"],
            cache_mode=d["cache_mode"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["workspace_abs"] = self.workspace_abs
        out["build_system_override"] = self.build_system_override
        out["cache_dir"] = self.cache_dir
        out["cache_mode"] = self.cache_mode
        return out


@dataclass
class BuildDetectOutput:
    VERSION: ClassVar[int] = 1
    build_system: str
    provenance: str
    installed_skills: list
    fallback_build_cmd: str
    cache_hit: bool

    @classmethod
    def from_dict(cls, d: dict) -> "BuildDetectOutput":
        return cls(
            build_system=d["build_system"],
            provenance=d["provenance"],
            installed_skills=d["installed_skills"],
            fallback_build_cmd=d["fallback_build_cmd"],
            cache_hit=d["cache_hit"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["build_system"] = self.build_system
        out["provenance"] = self.provenance
        out["installed_skills"] = self.installed_skills
        out["fallback_build_cmd"] = self.fallback_build_cmd
        out["cache_hit"] = self.cache_hit
        return out
