# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class BranchCreateInput:
    VERSION: ClassVar[int] = 1
    decision: str
    workspace_abs: str
    proposed_branch: str

    @classmethod
    def from_dict(cls, d: dict) -> "BranchCreateInput":
        return cls(
            decision=d["decision"],
            workspace_abs=d["workspace_abs"],
            proposed_branch=d["proposed_branch"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["decision"] = self.decision
        out["workspace_abs"] = self.workspace_abs
        out["proposed_branch"] = self.proposed_branch
        return out


@dataclass
class BranchCreateOutput:
    VERSION: ClassVar[int] = 1
    branch: str
    created: bool

    @classmethod
    def from_dict(cls, d: dict) -> "BranchCreateOutput":
        return cls(
            branch=d["branch"],
            created=d["created"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["branch"] = self.branch
        out["created"] = self.created
        return out
