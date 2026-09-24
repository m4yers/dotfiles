# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class WorkspaceGuardInput:
    VERSION: ClassVar[int] = 1
    workspace_abs: str
    feature_slug: str

    @classmethod
    def from_dict(cls, d: dict) -> "WorkspaceGuardInput":
        return cls(
            workspace_abs=d["workspace_abs"],
            feature_slug=d["feature_slug"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["workspace_abs"] = self.workspace_abs
        out["feature_slug"] = self.feature_slug
        return out


@dataclass
class WorkspaceGuardOutput:
    VERSION: ClassVar[int] = 1
    dirty: bool
    status_tail: str
    current_branch: str
    proposed_branch: str

    @classmethod
    def from_dict(cls, d: dict) -> "WorkspaceGuardOutput":
        return cls(
            dirty=d["dirty"],
            status_tail=d["status_tail"],
            current_branch=d["current_branch"],
            proposed_branch=d["proposed_branch"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["dirty"] = self.dirty
        out["status_tail"] = self.status_tail
        out["current_branch"] = self.current_branch
        out["proposed_branch"] = self.proposed_branch
        return out
