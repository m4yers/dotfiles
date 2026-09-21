# generated from io.yaml v2 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class WorkspaceBriefInput:
    VERSION: ClassVar[int] = 2
    workspace_abs: str
    cache_dir: str
    cache_mode: str
    total_files: int
    total_bytes: int
    languages: list
    top_dirs: list
    entrypoints: list
    dependencies: list
    unresolved_imports: list
    build_system: str
    build_provenance: str
    fallback_build_cmd: str
    test_system: str
    fallback_test_cmd: str
    summarize_mode: str
    cached_summaries: list
    summaries_b1: list
    summaries_b2: list
    summaries_b3: list | None = None
    summaries_b4: list | None = None
    summaries_b5: list | None = None
    summaries_b6: list | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "WorkspaceBriefInput":
        return cls(
            workspace_abs=d["workspace_abs"],
            cache_dir=d["cache_dir"],
            cache_mode=d["cache_mode"],
            total_files=d["total_files"],
            total_bytes=d["total_bytes"],
            languages=d["languages"],
            top_dirs=d["top_dirs"],
            entrypoints=d["entrypoints"],
            dependencies=d["dependencies"],
            unresolved_imports=d["unresolved_imports"],
            build_system=d["build_system"],
            build_provenance=d["build_provenance"],
            fallback_build_cmd=d["fallback_build_cmd"],
            test_system=d["test_system"],
            fallback_test_cmd=d["fallback_test_cmd"],
            summarize_mode=d["summarize_mode"],
            cached_summaries=d["cached_summaries"],
            summaries_b1=d["summaries_b1"],
            summaries_b2=d["summaries_b2"],
            summaries_b3=d.get("summaries_b3"),
            summaries_b4=d.get("summaries_b4"),
            summaries_b5=d.get("summaries_b5"),
            summaries_b6=d.get("summaries_b6"),
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["workspace_abs"] = self.workspace_abs
        out["cache_dir"] = self.cache_dir
        out["cache_mode"] = self.cache_mode
        out["total_files"] = self.total_files
        out["total_bytes"] = self.total_bytes
        out["languages"] = self.languages
        out["top_dirs"] = self.top_dirs
        out["entrypoints"] = self.entrypoints
        out["dependencies"] = self.dependencies
        out["unresolved_imports"] = self.unresolved_imports
        out["build_system"] = self.build_system
        out["build_provenance"] = self.build_provenance
        out["fallback_build_cmd"] = self.fallback_build_cmd
        out["test_system"] = self.test_system
        out["fallback_test_cmd"] = self.fallback_test_cmd
        out["summarize_mode"] = self.summarize_mode
        out["cached_summaries"] = self.cached_summaries
        out["summaries_b1"] = self.summaries_b1
        out["summaries_b2"] = self.summaries_b2
        if self.summaries_b3 is not None:
            out["summaries_b3"] = self.summaries_b3
        if self.summaries_b4 is not None:
            out["summaries_b4"] = self.summaries_b4
        if self.summaries_b5 is not None:
            out["summaries_b5"] = self.summaries_b5
        if self.summaries_b6 is not None:
            out["summaries_b6"] = self.summaries_b6
        return out


@dataclass
class WorkspaceBriefOutput:
    VERSION: ClassVar[int] = 2
    brief: str
    file_summaries_total: int

    @classmethod
    def from_dict(cls, d: dict) -> "WorkspaceBriefOutput":
        return cls(
            brief=d["brief"],
            file_summaries_total=d["file_summaries_total"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["brief"] = self.brief
        out["file_summaries_total"] = self.file_summaries_total
        return out
