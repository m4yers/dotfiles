# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class FinaliseInput:
    VERSION: ClassVar[int] = 1
    summary: str
    decision: str

    @classmethod
    def from_dict(cls, d: dict) -> "FinaliseInput":
        return cls(
            summary=d["summary"],
            decision=d["decision"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["summary"] = self.summary
        out["decision"] = self.decision
        return out


@dataclass
class FinaliseOutput:
    VERSION: ClassVar[int] = 1
    message: str

    @classmethod
    def from_dict(cls, d: dict) -> "FinaliseOutput":
        return cls(
            message=d["message"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["message"] = self.message
        return out
