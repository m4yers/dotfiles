# generated from io.yaml v2 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class PublishOutputInput:
    VERSION: ClassVar[int] = 2
    design: str
    decisions: list
    open_risks: list
    research_report: str
    gate_note: str

    @classmethod
    def from_dict(cls, d: dict) -> "PublishOutputInput":
        return cls(
            design=d["design"],
            decisions=d["decisions"],
            open_risks=d["open_risks"],
            research_report=d["research_report"],
            gate_note=d["gate_note"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["design"] = self.design
        out["decisions"] = self.decisions
        out["open_risks"] = self.open_risks
        out["research_report"] = self.research_report
        out["gate_note"] = self.gate_note
        return out


@dataclass
class PublishOutputOutput:
    VERSION: ClassVar[int] = 2
    design: str
    decisions: list
    open_risks: list
    research_report: str
    gate_note: str

    @classmethod
    def from_dict(cls, d: dict) -> "PublishOutputOutput":
        return cls(
            design=d["design"],
            decisions=d["decisions"],
            open_risks=d["open_risks"],
            research_report=d["research_report"],
            gate_note=d["gate_note"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["design"] = self.design
        out["decisions"] = self.decisions
        out["open_risks"] = self.open_risks
        out["research_report"] = self.research_report
        out["gate_note"] = self.gate_note
        return out
