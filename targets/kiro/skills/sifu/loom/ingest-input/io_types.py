# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class IngestInputInput:
    VERSION: ClassVar[int] = 1
    op: str
    name: str

    @classmethod
    def from_dict(cls, d: dict) -> "IngestInputInput":
        return cls(
            op=d["op"],
            name=d["name"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["op"] = self.op
        out["name"] = self.name
        return out


@dataclass
class IngestInputOutput:
    VERSION: ClassVar[int] = 1
    op: str
    name: str

    @classmethod
    def from_dict(cls, d: dict) -> "IngestInputOutput":
        return cls(
            op=d["op"],
            name=d["name"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["op"] = self.op
        out["name"] = self.name
        return out
