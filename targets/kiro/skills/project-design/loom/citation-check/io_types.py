# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class CitationCheckInput:
    VERSION: ClassVar[int] = 1
    design: str
    workspace_abs: str

    @classmethod
    def from_dict(cls, d: dict) -> "CitationCheckInput":
        return cls(
            design=d["design"],
            workspace_abs=d["workspace_abs"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["design"] = self.design
        out["workspace_abs"] = self.workspace_abs
        return out


@dataclass
class CitationCheckOutput:
    VERSION: ClassVar[int] = 1
    checked: int
    misses: list
    ok: bool
    report: str

    @classmethod
    def from_dict(cls, d: dict) -> "CitationCheckOutput":
        return cls(
            checked=d["checked"],
            misses=d["misses"],
            ok=d["ok"],
            report=d["report"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["checked"] = self.checked
        out["misses"] = self.misses
        out["ok"] = self.ok
        out["report"] = self.report
        return out
