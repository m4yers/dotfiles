# generated from io.yaml v2 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class OverviewIngestInput:
    VERSION: ClassVar[int] = 2
    description: str
    workspace: str
    build_system_override: str
    test_system_override: str
    cache_mode: str

    @classmethod
    def from_dict(cls, d: dict) -> "OverviewIngestInput":
        return cls(
            description=d["description"],
            workspace=d["workspace"],
            build_system_override=d["build_system_override"],
            test_system_override=d["test_system_override"],
            cache_mode=d["cache_mode"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["description"] = self.description
        out["workspace"] = self.workspace
        out["build_system_override"] = self.build_system_override
        out["test_system_override"] = self.test_system_override
        out["cache_mode"] = self.cache_mode
        return out


@dataclass
class OverviewIngestOutput:
    VERSION: ClassVar[int] = 2
    feature_slug: str
    workspace_abs: str
    description: str
    build_system_override: str
    test_system_override: str
    captured_at: str
    cache_prefix: str
    blob_prefix: str
    cache_key: str
    git_head: str
    dirty: bool
    cache_mode: str

    @classmethod
    def from_dict(cls, d: dict) -> "OverviewIngestOutput":
        return cls(
            feature_slug=d["feature_slug"],
            workspace_abs=d["workspace_abs"],
            description=d["description"],
            build_system_override=d["build_system_override"],
            test_system_override=d["test_system_override"],
            captured_at=d["captured_at"],
            cache_prefix=d["cache_prefix"],
            blob_prefix=d["blob_prefix"],
            cache_key=d["cache_key"],
            git_head=d["git_head"],
            dirty=d["dirty"],
            cache_mode=d["cache_mode"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["feature_slug"] = self.feature_slug
        out["workspace_abs"] = self.workspace_abs
        out["description"] = self.description
        out["build_system_override"] = self.build_system_override
        out["test_system_override"] = self.test_system_override
        out["captured_at"] = self.captured_at
        out["cache_prefix"] = self.cache_prefix
        out["blob_prefix"] = self.blob_prefix
        out["cache_key"] = self.cache_key
        out["git_head"] = self.git_head
        out["dirty"] = self.dirty
        out["cache_mode"] = self.cache_mode
        return out
