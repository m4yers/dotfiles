# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class AggregateSummariesInput:
    VERSION: ClassVar[int] = 1
    a: str
    b: str

    @classmethod
    def from_dict(cls, d: dict) -> "AggregateSummariesInput":
        return cls(
            a=d["a"],
            b=d["b"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["a"] = self.a
        out["b"] = self.b
        return out


@dataclass
class AggregateSummariesOutput:
    VERSION: ClassVar[int] = 1
    combined: str

    @classmethod
    def from_dict(cls, d: dict) -> "AggregateSummariesOutput":
        return cls(
            combined=d["combined"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["combined"] = self.combined
        return out
