# generated from io.yaml v9 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class PublishOutputInput:
    VERSION: ClassVar[int] = 9
    blob_prefix: str
    build_installed_skills: list
    build_provenance: str
    build_system: str
    cache_key: str
    cache_mode: str
    cache_prefix: str
    dependencies: list
    description: str
    dirty: bool
    domains: list
    entrypoints: list
    fallback_build_cmd: str
    fallback_test_cmd: str
    feature_slug: str
    git_head: str
    languages: list
    summarize_mode: str
    test_installed_skills: list
    test_system: str
    top_dirs: list
    total_bytes: int
    total_files: int
    unresolved_imports: list
    workspace_abs: str

    @classmethod
    def from_dict(cls, d: dict) -> "PublishOutputInput":
        return cls(
            blob_prefix=d["blob_prefix"],
            build_installed_skills=d["build_installed_skills"],
            build_provenance=d["build_provenance"],
            build_system=d["build_system"],
            cache_key=d["cache_key"],
            cache_mode=d["cache_mode"],
            cache_prefix=d["cache_prefix"],
            dependencies=d["dependencies"],
            description=d["description"],
            dirty=d["dirty"],
            domains=d["domains"],
            entrypoints=d["entrypoints"],
            fallback_build_cmd=d["fallback_build_cmd"],
            fallback_test_cmd=d["fallback_test_cmd"],
            feature_slug=d["feature_slug"],
            git_head=d["git_head"],
            languages=d["languages"],
            summarize_mode=d["summarize_mode"],
            test_installed_skills=d["test_installed_skills"],
            test_system=d["test_system"],
            top_dirs=d["top_dirs"],
            total_bytes=d["total_bytes"],
            total_files=d["total_files"],
            unresolved_imports=d["unresolved_imports"],
            workspace_abs=d["workspace_abs"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["blob_prefix"] = self.blob_prefix
        out["build_installed_skills"] = self.build_installed_skills
        out["build_provenance"] = self.build_provenance
        out["build_system"] = self.build_system
        out["cache_key"] = self.cache_key
        out["cache_mode"] = self.cache_mode
        out["cache_prefix"] = self.cache_prefix
        out["dependencies"] = self.dependencies
        out["description"] = self.description
        out["dirty"] = self.dirty
        out["domains"] = self.domains
        out["entrypoints"] = self.entrypoints
        out["fallback_build_cmd"] = self.fallback_build_cmd
        out["fallback_test_cmd"] = self.fallback_test_cmd
        out["feature_slug"] = self.feature_slug
        out["git_head"] = self.git_head
        out["languages"] = self.languages
        out["summarize_mode"] = self.summarize_mode
        out["test_installed_skills"] = self.test_installed_skills
        out["test_system"] = self.test_system
        out["top_dirs"] = self.top_dirs
        out["total_bytes"] = self.total_bytes
        out["total_files"] = self.total_files
        out["unresolved_imports"] = self.unresolved_imports
        out["workspace_abs"] = self.workspace_abs
        return out


@dataclass
class PublishOutputOutput:
    VERSION: ClassVar[int] = 9
    blob_prefix: str
    build_installed_skills: list
    build_provenance: str
    build_system: str
    cache_key: str
    cache_mode: str
    cache_prefix: str
    dependencies: list
    description: str
    dirty: bool
    domains: list
    entrypoints: list
    fallback_build_cmd: str
    fallback_test_cmd: str
    feature_slug: str
    git_head: str
    languages: list
    summaries_mode: str
    summaries_store: str
    summaries_total: int
    summaries_usage: str
    test_installed_skills: list
    test_system: str
    top_dirs: list
    total_bytes: int
    total_files: int
    unresolved_imports: list
    workspace_abs: str

    @classmethod
    def from_dict(cls, d: dict) -> "PublishOutputOutput":
        return cls(
            blob_prefix=d["blob_prefix"],
            build_installed_skills=d["build_installed_skills"],
            build_provenance=d["build_provenance"],
            build_system=d["build_system"],
            cache_key=d["cache_key"],
            cache_mode=d["cache_mode"],
            cache_prefix=d["cache_prefix"],
            dependencies=d["dependencies"],
            description=d["description"],
            dirty=d["dirty"],
            domains=d["domains"],
            entrypoints=d["entrypoints"],
            fallback_build_cmd=d["fallback_build_cmd"],
            fallback_test_cmd=d["fallback_test_cmd"],
            feature_slug=d["feature_slug"],
            git_head=d["git_head"],
            languages=d["languages"],
            summaries_mode=d["summaries_mode"],
            summaries_store=d["summaries_store"],
            summaries_total=d["summaries_total"],
            summaries_usage=d["summaries_usage"],
            test_installed_skills=d["test_installed_skills"],
            test_system=d["test_system"],
            top_dirs=d["top_dirs"],
            total_bytes=d["total_bytes"],
            total_files=d["total_files"],
            unresolved_imports=d["unresolved_imports"],
            workspace_abs=d["workspace_abs"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["blob_prefix"] = self.blob_prefix
        out["build_installed_skills"] = self.build_installed_skills
        out["build_provenance"] = self.build_provenance
        out["build_system"] = self.build_system
        out["cache_key"] = self.cache_key
        out["cache_mode"] = self.cache_mode
        out["cache_prefix"] = self.cache_prefix
        out["dependencies"] = self.dependencies
        out["description"] = self.description
        out["dirty"] = self.dirty
        out["domains"] = self.domains
        out["entrypoints"] = self.entrypoints
        out["fallback_build_cmd"] = self.fallback_build_cmd
        out["fallback_test_cmd"] = self.fallback_test_cmd
        out["feature_slug"] = self.feature_slug
        out["git_head"] = self.git_head
        out["languages"] = self.languages
        out["summaries_mode"] = self.summaries_mode
        out["summaries_store"] = self.summaries_store
        out["summaries_total"] = self.summaries_total
        out["summaries_usage"] = self.summaries_usage
        out["test_installed_skills"] = self.test_installed_skills
        out["test_system"] = self.test_system
        out["top_dirs"] = self.top_dirs
        out["total_bytes"] = self.total_bytes
        out["total_files"] = self.total_files
        out["unresolved_imports"] = self.unresolved_imports
        out["workspace_abs"] = self.workspace_abs
        return out
