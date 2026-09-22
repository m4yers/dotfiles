# generated from io.yaml v2 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class TestDetectInput:
    VERSION: ClassVar[int] = 2
    workspace_abs: str
    build_system: str
    build_installed_skills: list
    test_system_override: str
    cache_prefix: str
    cache_mode: str

    @classmethod
    def from_dict(cls, d: dict) -> "TestDetectInput":
        return cls(
            workspace_abs=d["workspace_abs"],
            build_system=d["build_system"],
            build_installed_skills=d["build_installed_skills"],
            test_system_override=d["test_system_override"],
            cache_prefix=d["cache_prefix"],
            cache_mode=d["cache_mode"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["workspace_abs"] = self.workspace_abs
        out["build_system"] = self.build_system
        out["build_installed_skills"] = self.build_installed_skills
        out["test_system_override"] = self.test_system_override
        out["cache_prefix"] = self.cache_prefix
        out["cache_mode"] = self.cache_mode
        return out


@dataclass
class TestDetectOutput:
    VERSION: ClassVar[int] = 2
    test_system: str
    provenance: str
    installed_skills: list
    fallback_test_cmd: str
    cache_hit: bool

    @classmethod
    def from_dict(cls, d: dict) -> "TestDetectOutput":
        return cls(
            test_system=d["test_system"],
            provenance=d["provenance"],
            installed_skills=d["installed_skills"],
            fallback_test_cmd=d["fallback_test_cmd"],
            cache_hit=d["cache_hit"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["test_system"] = self.test_system
        out["provenance"] = self.provenance
        out["installed_skills"] = self.installed_skills
        out["fallback_test_cmd"] = self.fallback_test_cmd
        out["cache_hit"] = self.cache_hit
        return out
