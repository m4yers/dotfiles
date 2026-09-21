# generated from io.yaml v3 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class DesignReviewMergeInput:
    VERSION: ClassVar[int] = 3
    decision_swe: str
    revise_reason_swe: str
    role_swe: str
    decision_d1: str
    decision_d2: str
    revise_reason_d1: str
    revise_reason_d2: str
    role_d1: str
    role_d2: str
    decision_d3: str | None = None
    decision_d4: str | None = None
    decision_d5: str | None = None
    decision_d6: str | None = None
    revise_reason_d3: str | None = None
    revise_reason_d4: str | None = None
    revise_reason_d5: str | None = None
    revise_reason_d6: str | None = None
    role_d3: str | None = None
    role_d4: str | None = None
    role_d5: str | None = None
    role_d6: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "DesignReviewMergeInput":
        return cls(
            decision_swe=d["decision_swe"],
            revise_reason_swe=d["revise_reason_swe"],
            role_swe=d["role_swe"],
            decision_d1=d["decision_d1"],
            decision_d2=d["decision_d2"],
            revise_reason_d1=d["revise_reason_d1"],
            revise_reason_d2=d["revise_reason_d2"],
            role_d1=d["role_d1"],
            role_d2=d["role_d2"],
            decision_d3=d.get("decision_d3"),
            decision_d4=d.get("decision_d4"),
            decision_d5=d.get("decision_d5"),
            decision_d6=d.get("decision_d6"),
            revise_reason_d3=d.get("revise_reason_d3"),
            revise_reason_d4=d.get("revise_reason_d4"),
            revise_reason_d5=d.get("revise_reason_d5"),
            revise_reason_d6=d.get("revise_reason_d6"),
            role_d3=d.get("role_d3"),
            role_d4=d.get("role_d4"),
            role_d5=d.get("role_d5"),
            role_d6=d.get("role_d6"),
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["decision_swe"] = self.decision_swe
        out["revise_reason_swe"] = self.revise_reason_swe
        out["role_swe"] = self.role_swe
        out["decision_d1"] = self.decision_d1
        out["decision_d2"] = self.decision_d2
        out["revise_reason_d1"] = self.revise_reason_d1
        out["revise_reason_d2"] = self.revise_reason_d2
        out["role_d1"] = self.role_d1
        out["role_d2"] = self.role_d2
        if self.decision_d3 is not None:
            out["decision_d3"] = self.decision_d3
        if self.decision_d4 is not None:
            out["decision_d4"] = self.decision_d4
        if self.decision_d5 is not None:
            out["decision_d5"] = self.decision_d5
        if self.decision_d6 is not None:
            out["decision_d6"] = self.decision_d6
        if self.revise_reason_d3 is not None:
            out["revise_reason_d3"] = self.revise_reason_d3
        if self.revise_reason_d4 is not None:
            out["revise_reason_d4"] = self.revise_reason_d4
        if self.revise_reason_d5 is not None:
            out["revise_reason_d5"] = self.revise_reason_d5
        if self.revise_reason_d6 is not None:
            out["revise_reason_d6"] = self.revise_reason_d6
        if self.role_d3 is not None:
            out["role_d3"] = self.role_d3
        if self.role_d4 is not None:
            out["role_d4"] = self.role_d4
        if self.role_d5 is not None:
            out["role_d5"] = self.role_d5
        if self.role_d6 is not None:
            out["role_d6"] = self.role_d6
        return out


@dataclass
class DesignReviewMergeOutput:
    VERSION: ClassVar[int] = 3
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
