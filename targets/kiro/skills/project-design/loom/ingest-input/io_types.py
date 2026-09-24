# generated from io.yaml v3 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class IngestInputInput:
    VERSION: ClassVar[int] = 3
    description: str
    workspace_abs: str
    build_system: str
    build_installed_skills: list
    fallback_build_cmd: str
    fallback_test_cmd: str
    domains: list
    summaries_store: str
    summaries_usage: str

    @classmethod
    def from_dict(cls, d: dict) -> "IngestInputInput":
        return cls(
            description=d["description"],
            workspace_abs=d["workspace_abs"],
            build_system=d["build_system"],
            build_installed_skills=d["build_installed_skills"],
            fallback_build_cmd=d["fallback_build_cmd"],
            fallback_test_cmd=d["fallback_test_cmd"],
            domains=d["domains"],
            summaries_store=d["summaries_store"],
            summaries_usage=d["summaries_usage"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["description"] = self.description
        out["workspace_abs"] = self.workspace_abs
        out["build_system"] = self.build_system
        out["build_installed_skills"] = self.build_installed_skills
        out["fallback_build_cmd"] = self.fallback_build_cmd
        out["fallback_test_cmd"] = self.fallback_test_cmd
        out["domains"] = self.domains
        out["summaries_store"] = self.summaries_store
        out["summaries_usage"] = self.summaries_usage
        return out


@dataclass
class IngestInputOutput:
    VERSION: ClassVar[int] = 3
    description: str
    workspace_abs: str
    build_system: str
    build_installed_skills: list
    fallback_build_cmd: str
    fallback_test_cmd: str
    domains: list
    summaries_store: str
    summaries_usage: str

    @classmethod
    def from_dict(cls, d: dict) -> "IngestInputOutput":
        return cls(
            description=d["description"],
            workspace_abs=d["workspace_abs"],
            build_system=d["build_system"],
            build_installed_skills=d["build_installed_skills"],
            fallback_build_cmd=d["fallback_build_cmd"],
            fallback_test_cmd=d["fallback_test_cmd"],
            domains=d["domains"],
            summaries_store=d["summaries_store"],
            summaries_usage=d["summaries_usage"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["description"] = self.description
        out["workspace_abs"] = self.workspace_abs
        out["build_system"] = self.build_system
        out["build_installed_skills"] = self.build_installed_skills
        out["fallback_build_cmd"] = self.fallback_build_cmd
        out["fallback_test_cmd"] = self.fallback_test_cmd
        out["domains"] = self.domains
        out["summaries_store"] = self.summaries_store
        out["summaries_usage"] = self.summaries_usage
        return out
