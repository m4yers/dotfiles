# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class DesignReviewMergeInput:
    VERSION: ClassVar[int] = 1
    decision_swe: str
    revise_reason_swe: str
    role_swe: str
    decision_d1: str
    revise_reason_d1: str
    role_d1: str
    decision_d2: str
    revise_reason_d2: str
    role_d2: str

    @classmethod
    def from_dict(cls, d: dict) -> "DesignReviewMergeInput":
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
        return out


@dataclass
class DesignReviewMergeOutput:
    VERSION: ClassVar[int] = 1
    decision: str
    revise_reason: str

    @classmethod
    def from_dict(cls, d: dict) -> "DesignReviewMergeOutput":
        return cls(
            decision=d["decision"],
            revise_reason=d["revise_reason"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["decision"] = self.decision
        out["revise_reason"] = self.revise_reason
        return out
