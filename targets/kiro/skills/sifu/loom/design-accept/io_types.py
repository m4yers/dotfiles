# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class DesignAcceptInput:
    VERSION: ClassVar[int] = 1
    design: dict
    decision: str
    revise_reason: str

    @classmethod
    def from_dict(cls, d: dict) -> "DesignAcceptInput":
        return cls(
            design=d["design"],
            decision=d["decision"],
            revise_reason=d["revise_reason"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["design"] = self.design
        out["decision"] = self.decision
        out["revise_reason"] = self.revise_reason
        return out


@dataclass
class DesignAcceptOutput:
    VERSION: ClassVar[int] = 1
    design: dict
    decision: str
    revise_reason: str

    @classmethod
    def from_dict(cls, d: dict) -> "DesignAcceptOutput":
        return cls(
            design=d["design"],
            decision=d["decision"],
            revise_reason=d["revise_reason"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["design"] = self.design
        out["decision"] = self.decision
        out["revise_reason"] = self.revise_reason
        return out
