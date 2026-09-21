# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class ReviewDiffsMergeInput:
    VERSION: ClassVar[int] = 1
    verdict_swe: str
    findings_swe: list
    summary_swe: str
    role_swe: str
    verdict_d1: str
    findings_d1: list
    summary_d1: str
    role_d1: str
    verdict_d2: str
    findings_d2: list
    summary_d2: str
    role_d2: str

    @classmethod
    def from_dict(cls, d: dict) -> "ReviewDiffsMergeInput":
        return cls(
            verdict_swe=d["verdict_swe"],
            findings_swe=d["findings_swe"],
            summary_swe=d["summary_swe"],
            role_swe=d["role_swe"],
            verdict_d1=d["verdict_d1"],
            findings_d1=d["findings_d1"],
            summary_d1=d["summary_d1"],
            role_d1=d["role_d1"],
            verdict_d2=d["verdict_d2"],
            findings_d2=d["findings_d2"],
            summary_d2=d["summary_d2"],
            role_d2=d["role_d2"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["verdict_swe"] = self.verdict_swe
        out["findings_swe"] = self.findings_swe
        out["summary_swe"] = self.summary_swe
        out["role_swe"] = self.role_swe
        out["verdict_d1"] = self.verdict_d1
        out["findings_d1"] = self.findings_d1
        out["summary_d1"] = self.summary_d1
        out["role_d1"] = self.role_d1
        out["verdict_d2"] = self.verdict_d2
        out["findings_d2"] = self.findings_d2
        out["summary_d2"] = self.summary_d2
        out["role_d2"] = self.role_d2
        return out


@dataclass
class ReviewDiffsMergeOutput:
    VERSION: ClassVar[int] = 1
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
