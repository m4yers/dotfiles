# generated from io.yaml v3 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class ReviewDiffsMergeInput:
    VERSION: ClassVar[int] = 3
    verdict_swe: str
    findings_swe: list
    summary_swe: str
    role_swe: str
    verdict_d1: str
    verdict_d2: str
    findings_d1: list
    findings_d2: list
    summary_d1: str
    summary_d2: str
    role_d1: str
    role_d2: str
    verdict_d3: str | None = None
    verdict_d4: str | None = None
    verdict_d5: str | None = None
    verdict_d6: str | None = None
    findings_d3: list | None = None
    findings_d4: list | None = None
    findings_d5: list | None = None
    findings_d6: list | None = None
    summary_d3: str | None = None
    summary_d4: str | None = None
    summary_d5: str | None = None
    summary_d6: str | None = None
    role_d3: str | None = None
    role_d4: str | None = None
    role_d5: str | None = None
    role_d6: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "ReviewDiffsMergeInput":
        return cls(
            verdict_swe=d["verdict_swe"],
            findings_swe=d["findings_swe"],
            summary_swe=d["summary_swe"],
            role_swe=d["role_swe"],
            verdict_d1=d["verdict_d1"],
            verdict_d2=d["verdict_d2"],
            findings_d1=d["findings_d1"],
            findings_d2=d["findings_d2"],
            summary_d1=d["summary_d1"],
            summary_d2=d["summary_d2"],
            role_d1=d["role_d1"],
            role_d2=d["role_d2"],
            verdict_d3=d.get("verdict_d3"),
            verdict_d4=d.get("verdict_d4"),
            verdict_d5=d.get("verdict_d5"),
            verdict_d6=d.get("verdict_d6"),
            findings_d3=d.get("findings_d3"),
            findings_d4=d.get("findings_d4"),
            findings_d5=d.get("findings_d5"),
            findings_d6=d.get("findings_d6"),
            summary_d3=d.get("summary_d3"),
            summary_d4=d.get("summary_d4"),
            summary_d5=d.get("summary_d5"),
            summary_d6=d.get("summary_d6"),
            role_d3=d.get("role_d3"),
            role_d4=d.get("role_d4"),
            role_d5=d.get("role_d5"),
            role_d6=d.get("role_d6"),
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["verdict_swe"] = self.verdict_swe
        out["findings_swe"] = self.findings_swe
        out["summary_swe"] = self.summary_swe
        out["role_swe"] = self.role_swe
        out["verdict_d1"] = self.verdict_d1
        out["verdict_d2"] = self.verdict_d2
        out["findings_d1"] = self.findings_d1
        out["findings_d2"] = self.findings_d2
        out["summary_d1"] = self.summary_d1
        out["summary_d2"] = self.summary_d2
        out["role_d1"] = self.role_d1
        out["role_d2"] = self.role_d2
        if self.verdict_d3 is not None:
            out["verdict_d3"] = self.verdict_d3
        if self.verdict_d4 is not None:
            out["verdict_d4"] = self.verdict_d4
        if self.verdict_d5 is not None:
            out["verdict_d5"] = self.verdict_d5
        if self.verdict_d6 is not None:
            out["verdict_d6"] = self.verdict_d6
        if self.findings_d3 is not None:
            out["findings_d3"] = self.findings_d3
        if self.findings_d4 is not None:
            out["findings_d4"] = self.findings_d4
        if self.findings_d5 is not None:
            out["findings_d5"] = self.findings_d5
        if self.findings_d6 is not None:
            out["findings_d6"] = self.findings_d6
        if self.summary_d3 is not None:
            out["summary_d3"] = self.summary_d3
        if self.summary_d4 is not None:
            out["summary_d4"] = self.summary_d4
        if self.summary_d5 is not None:
            out["summary_d5"] = self.summary_d5
        if self.summary_d6 is not None:
            out["summary_d6"] = self.summary_d6
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
class ReviewDiffsMergeOutput:
    VERSION: ClassVar[int] = 3
    verdict: str
    findings: list
    summary: str

    @classmethod
    def from_dict(cls, d: dict) -> "ReviewDiffsMergeOutput":
        return cls(
            verdict=d["verdict"],
            findings=d["findings"],
            summary=d["summary"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["verdict"] = self.verdict
        out["findings"] = self.findings
        out["summary"] = self.summary
        return out
