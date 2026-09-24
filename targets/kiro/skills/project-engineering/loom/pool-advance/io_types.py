# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class PoolAdvanceInput:
    VERSION: ClassVar[int] = 1
    cursor: int
    total: int
    current_task: dict
    applied: object
    error: str
    diff: str
    files_changed: list
    notes: str
    cmds_used: list
    prev: dict | None
    retry_budget: str
    on_task_fail: str

    @classmethod
    def from_dict(cls, d: dict) -> "PoolAdvanceInput":
        return cls(
            cursor=d["cursor"],
            total=d["total"],
            current_task=d["current_task"],
            applied=d["applied"],
            error=d["error"],
            diff=d["diff"],
            files_changed=d["files_changed"],
            notes=d["notes"],
            cmds_used=d["cmds_used"],
            prev=d["prev"],
            retry_budget=d["retry_budget"],
            on_task_fail=d["on_task_fail"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["cursor"] = self.cursor
        out["total"] = self.total
        out["current_task"] = self.current_task
        out["applied"] = self.applied
        out["error"] = self.error
        out["diff"] = self.diff
        out["files_changed"] = self.files_changed
        out["notes"] = self.notes
        out["cmds_used"] = self.cmds_used
        out["prev"] = self.prev
        out["retry_budget"] = self.retry_budget
        out["on_task_fail"] = self.on_task_fail
        return out


@dataclass
class PoolAdvanceOutput:
    VERSION: ClassVar[int] = 1
    next_cursor: int
    remaining: int
    retries: dict
    failed_task_ids: list
    applied_count: int
    diff_bundle: str
    cmds_bundle: list
    prior_diffs_summary: str

    @classmethod
    def from_dict(cls, d: dict) -> "PoolAdvanceOutput":
        return cls(
            next_cursor=d["next_cursor"],
            remaining=d["remaining"],
            retries=d["retries"],
            failed_task_ids=d["failed_task_ids"],
            applied_count=d["applied_count"],
            diff_bundle=d["diff_bundle"],
            cmds_bundle=d["cmds_bundle"],
            prior_diffs_summary=d["prior_diffs_summary"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["next_cursor"] = self.next_cursor
        out["remaining"] = self.remaining
        out["retries"] = self.retries
        out["failed_task_ids"] = self.failed_task_ids
        out["applied_count"] = self.applied_count
        out["diff_bundle"] = self.diff_bundle
        out["cmds_bundle"] = self.cmds_bundle
        out["prior_diffs_summary"] = self.prior_diffs_summary
        return out
