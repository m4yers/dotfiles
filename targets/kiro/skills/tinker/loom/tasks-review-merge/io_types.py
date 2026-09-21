# generated from io.yaml v2 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class TasksReviewMergeInput:
    VERSION: ClassVar[int] = 2
    decision_swe: str
    revise_reason_swe: str
    role_swe: str
    decision_d1: str
    revise_reason_d1: str
    role_d1: str
    decision_d2: str
    revise_reason_d2: str
    role_d2: str
    num_tasks: int

    @classmethod
    def from_dict(cls, d: dict) -> "TasksReviewMergeInput":
        return cls(
            decision_swe=d["decision_swe"],
            revise_reason_swe=d["revise_reason_swe"],
            role_swe=d["role_swe"],
            decision_d1=d["decision_d1"],
            revise_reason_d1=d["revise_reason_d1"],
            role_d1=d["role_d1"],
            decision_d2=d["decision_d2"],
            revise_reason_d2=d["revise_reason_d2"],
            role_d2=d["role_d2"],
            num_tasks=d["num_tasks"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["decision_swe"] = self.decision_swe
        out["revise_reason_swe"] = self.revise_reason_swe
        out["role_swe"] = self.role_swe
        out["decision_d1"] = self.decision_d1
        out["revise_reason_d1"] = self.revise_reason_d1
        out["role_d1"] = self.role_d1
        out["decision_d2"] = self.decision_d2
        out["revise_reason_d2"] = self.revise_reason_d2
        out["role_d2"] = self.role_d2
        out["num_tasks"] = self.num_tasks
        return out


@dataclass
class TasksReviewMergeOutput:
    VERSION: ClassVar[int] = 2
    decision: str
    revise_reason: str
    num_tasks: int

    @classmethod
    def from_dict(cls, d: dict) -> "TasksReviewMergeOutput":
        return cls(
            decision=d["decision"],
            revise_reason=d["revise_reason"],
            num_tasks=d["num_tasks"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["decision"] = self.decision
        out["revise_reason"] = self.revise_reason
        out["num_tasks"] = self.num_tasks
        return out
