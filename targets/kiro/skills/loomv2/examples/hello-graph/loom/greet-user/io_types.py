# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class GreetUserInput:
    VERSION: ClassVar[int] = 1
    name: str

    @classmethod
    def from_dict(cls, d: dict) -> "GreetUserInput":
        return cls(
            name=d["name"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["name"] = self.name
        return out


@dataclass
class GreetUserOutput:
    VERSION: ClassVar[int] = 1
    greeting: str

    @classmethod
    def from_dict(cls, d: dict) -> "GreetUserOutput":
        return cls(
            greeting=d["greeting"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["greeting"] = self.greeting
        return out
