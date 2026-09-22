# generated from io.yaml v3 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class OverviewExitInput:
    VERSION: ClassVar[int] = 3
    workspace_abs: str
    feature_slug: str
    description: str
    build_system: str
    build_installed_skills: list
    fallback_build_cmd: str
    test_system: str
    test_installed_skills: list
    fallback_test_cmd: str
    workspace_brief: str
    domains: list
    cache_prefix: str
    blob_prefix: str
    cache_key: str
    git_head: str
    dirty: bool
    cache_mode: str

    @classmethod
    def from_dict(cls, d: dict) -> "OverviewExitInput":
        return cls(
            workspace_abs=d["workspace_abs"],
            feature_slug=d["feature_slug"],
            description=d["description"],
            build_system=d["build_system"],
            build_installed_skills=d["build_installed_skills"],
            fallback_build_cmd=d["fallback_build_cmd"],
            test_system=d["test_system"],
            test_installed_skills=d["test_installed_skills"],
            fallback_test_cmd=d["fallback_test_cmd"],
            workspace_brief=d["workspace_brief"],
            domains=d["domains"],
            cache_prefix=d["cache_prefix"],
            blob_prefix=d["blob_prefix"],
            cache_key=d["cache_key"],
            git_head=d["git_head"],
            dirty=d["dirty"],
            cache_mode=d["cache_mode"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["workspace_abs"] = self.workspace_abs
        out["feature_slug"] = self.feature_slug
        out["description"] = self.description
        out["build_system"] = self.build_system
        out["build_installed_skills"] = self.build_installed_skills
        out["fallback_build_cmd"] = self.fallback_build_cmd
        out["test_system"] = self.test_system
        out["test_installed_skills"] = self.test_installed_skills
        out["fallback_test_cmd"] = self.fallback_test_cmd
        out["workspace_brief"] = self.workspace_brief
        out["domains"] = self.domains
        out["cache_prefix"] = self.cache_prefix
        out["blob_prefix"] = self.blob_prefix
        out["cache_key"] = self.cache_key
        out["git_head"] = self.git_head
        out["dirty"] = self.dirty
        out["cache_mode"] = self.cache_mode
        return out


@dataclass
class OverviewExitOutput:
    VERSION: ClassVar[int] = 3
    envelope: dict

    @classmethod
    def from_dict(cls, d: dict) -> "OverviewExitOutput":
        return cls(
            envelope=d["envelope"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["envelope"] = self.envelope
        return out
