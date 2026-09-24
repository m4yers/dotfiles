# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class IngestInputInput:
    VERSION: ClassVar[int] = 1
    build_installed_skills: list
    build_system: str
    design: str
    design_note: str
    fallback_build_cmd: str
    fallback_test_cmd: str
    feature_slug: str
    reviewer_role_d1: str
    reviewer_role_d2: str
    reviewer_role_d3: str
    reviewer_role_d4: str
    reviewer_role_d5: str
    reviewer_role_d6: str
    test_installed_skills: list
    test_system: str
    workspace_abs: str

    @classmethod
    def from_dict(cls, d: dict) -> "IngestInputInput":
        return cls(
            build_installed_skills=d["build_installed_skills"],
            build_system=d["build_system"],
            design=d["design"],
            design_note=d["design_note"],
            fallback_build_cmd=d["fallback_build_cmd"],
            fallback_test_cmd=d["fallback_test_cmd"],
            feature_slug=d["feature_slug"],
            reviewer_role_d1=d["reviewer_role_d1"],
            reviewer_role_d2=d["reviewer_role_d2"],
            reviewer_role_d3=d["reviewer_role_d3"],
            reviewer_role_d4=d["reviewer_role_d4"],
            reviewer_role_d5=d["reviewer_role_d5"],
            reviewer_role_d6=d["reviewer_role_d6"],
            test_installed_skills=d["test_installed_skills"],
            test_system=d["test_system"],
            workspace_abs=d["workspace_abs"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["build_installed_skills"] = self.build_installed_skills
        out["build_system"] = self.build_system
        out["design"] = self.design
        out["design_note"] = self.design_note
        out["fallback_build_cmd"] = self.fallback_build_cmd
        out["fallback_test_cmd"] = self.fallback_test_cmd
        out["feature_slug"] = self.feature_slug
        out["reviewer_role_d1"] = self.reviewer_role_d1
        out["reviewer_role_d2"] = self.reviewer_role_d2
        out["reviewer_role_d3"] = self.reviewer_role_d3
        out["reviewer_role_d4"] = self.reviewer_role_d4
        out["reviewer_role_d5"] = self.reviewer_role_d5
        out["reviewer_role_d6"] = self.reviewer_role_d6
        out["test_installed_skills"] = self.test_installed_skills
        out["test_system"] = self.test_system
        out["workspace_abs"] = self.workspace_abs
        return out


@dataclass
class IngestInputOutput:
    VERSION: ClassVar[int] = 1
    build_installed_skills: list
    build_system: str
    design: str
    design_note: str
    fallback_build_cmd: str
    fallback_test_cmd: str
    feature_slug: str
    reviewer_role_d1: str
    reviewer_role_d2: str
    reviewer_role_d3: str
    reviewer_role_d4: str
    reviewer_role_d5: str
    reviewer_role_d6: str
    test_installed_skills: list
    test_system: str
    workspace_abs: str

    @classmethod
    def from_dict(cls, d: dict) -> "IngestInputOutput":
        return cls(
            build_installed_skills=d["build_installed_skills"],
            build_system=d["build_system"],
            design=d["design"],
            design_note=d["design_note"],
            fallback_build_cmd=d["fallback_build_cmd"],
            fallback_test_cmd=d["fallback_test_cmd"],
            feature_slug=d["feature_slug"],
            reviewer_role_d1=d["reviewer_role_d1"],
            reviewer_role_d2=d["reviewer_role_d2"],
            reviewer_role_d3=d["reviewer_role_d3"],
            reviewer_role_d4=d["reviewer_role_d4"],
            reviewer_role_d5=d["reviewer_role_d5"],
            reviewer_role_d6=d["reviewer_role_d6"],
            test_installed_skills=d["test_installed_skills"],
            test_system=d["test_system"],
            workspace_abs=d["workspace_abs"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["build_installed_skills"] = self.build_installed_skills
        out["build_system"] = self.build_system
        out["design"] = self.design
        out["design_note"] = self.design_note
        out["fallback_build_cmd"] = self.fallback_build_cmd
        out["fallback_test_cmd"] = self.fallback_test_cmd
        out["feature_slug"] = self.feature_slug
        out["reviewer_role_d1"] = self.reviewer_role_d1
        out["reviewer_role_d2"] = self.reviewer_role_d2
        out["reviewer_role_d3"] = self.reviewer_role_d3
        out["reviewer_role_d4"] = self.reviewer_role_d4
        out["reviewer_role_d5"] = self.reviewer_role_d5
        out["reviewer_role_d6"] = self.reviewer_role_d6
        out["test_installed_skills"] = self.test_installed_skills
        out["test_system"] = self.test_system
        out["workspace_abs"] = self.workspace_abs
        return out
