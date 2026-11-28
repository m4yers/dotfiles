# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class DesignAcceptUpdateInput:
    VERSION: ClassVar[int] = 1
    plan: dict
    decision: str
    revise_reason: str

    @classmethod
    def from_dict(cls, d: dict) -> "DesignAcceptUpdateInput":
        return cls(
            plan=d["plan"],
            decision=d["decision"],
            revise_reason=d["revise_reason"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["plan"] = self.plan
        out["decision"] = self.decision
        out["revise_reason"] = self.revise_reason
        return out


@dataclass
class DesignAcceptUpdateOutput:
    VERSION: ClassVar[int] = 1
    plan: dict
    decision: str
    revise_reason: str

    @classmethod
    def from_dict(cls, d: dict) -> "DesignAcceptUpdateOutput":
        return cls(
            plan=d["plan"],
            decision=d["decision"],
            revise_reason=d["revise_reason"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["plan"] = self.plan
        out["decision"] = self.decision
        out["revise_reason"] = self.revise_reason
        return out
