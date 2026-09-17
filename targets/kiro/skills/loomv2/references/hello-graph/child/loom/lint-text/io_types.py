# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class LintTextInput:
    VERSION: ClassVar[int] = 1
    greeting: str

    @classmethod
    def from_dict(cls, d: dict) -> "LintTextInput":
        return cls(
            greeting=d["greeting"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["greeting"] = self.greeting
        return out


@dataclass
class LintTextOutput:
    VERSION: ClassVar[int] = 1
    issues_found: int
    notes: str

    @classmethod
    def from_dict(cls, d: dict) -> "LintTextOutput":
        return cls(
            issues_found=d["issues_found"],
            notes=d["notes"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["issues_found"] = self.issues_found
        out["notes"] = self.notes
        return out
