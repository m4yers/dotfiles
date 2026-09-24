# generated from io.yaml v7 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar
from loom.engine.reserved import LoomMeta, TaskMeta


@dataclass
class ResearchPlanInput:
    VERSION: ClassVar[int] = 7
    description: str
    workspace_abs: str
    build_system: str
    installed_skills: list
    fallback_build_cmd: str
    fallback_test_cmd: str
    max_questions: str
    loom: LoomMeta
    summaries_store: str
    summaries_usage: str

    @classmethod
    def from_dict(cls, d: dict) -> "ResearchPlanInput":
        return cls(
            description=d["description"],
            workspace_abs=d["workspace_abs"],
            build_system=d["build_system"],
            installed_skills=d["installed_skills"],
            fallback_build_cmd=d["fallback_build_cmd"],
            fallback_test_cmd=d["fallback_test_cmd"],
            max_questions=d["max_questions"],
            loom=LoomMeta.from_dict(d["__loom"]),
            summaries_store=d["summaries_store"],
            summaries_usage=d["summaries_usage"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["description"] = self.description
        out["workspace_abs"] = self.workspace_abs
        out["build_system"] = self.build_system
        out["installed_skills"] = self.installed_skills
        out["fallback_build_cmd"] = self.fallback_build_cmd
        out["fallback_test_cmd"] = self.fallback_test_cmd
        out["max_questions"] = self.max_questions
        out["__loom"] = self.loom.to_dict()
        out["summaries_store"] = self.summaries_store
        out["summaries_usage"] = self.summaries_usage
        return out


@dataclass
class ResearchPlanOutput:
    VERSION: ClassVar[int] = 7
    questions: list
    num_questions: int

    @classmethod
    def from_dict(cls, d: dict) -> "ResearchPlanOutput":
        return cls(
            questions=d["questions"],
            num_questions=d["num_questions"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["questions"] = self.questions
        out["num_questions"] = self.num_questions
        return out
