# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class PublishOutputInput:
    VERSION: ClassVar[int] = 1
    applied_count: int
    branch: str
    diff_bundle: str
    diffs_verdict: str
    failed_task_ids: list
    final_decision: str
    final_note: str
    review_summary: str
    tasks_verdict: str
    total_tasks: int
    verify_passed: bool

    @classmethod
    def from_dict(cls, d: dict) -> "PublishOutputInput":
        return cls(
            applied_count=d["applied_count"],
            branch=d["branch"],
            diff_bundle=d["diff_bundle"],
            diffs_verdict=d["diffs_verdict"],
            failed_task_ids=d["failed_task_ids"],
            final_decision=d["final_decision"],
            final_note=d["final_note"],
            review_summary=d["review_summary"],
            tasks_verdict=d["tasks_verdict"],
            total_tasks=d["total_tasks"],
            verify_passed=d["verify_passed"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["applied_count"] = self.applied_count
        out["branch"] = self.branch
        out["diff_bundle"] = self.diff_bundle
        out["diffs_verdict"] = self.diffs_verdict
        out["failed_task_ids"] = self.failed_task_ids
        out["final_decision"] = self.final_decision
        out["final_note"] = self.final_note
        out["review_summary"] = self.review_summary
        out["tasks_verdict"] = self.tasks_verdict
        out["total_tasks"] = self.total_tasks
        out["verify_passed"] = self.verify_passed
        return out


@dataclass
class PublishOutputOutput:
    VERSION: ClassVar[int] = 1
    applied_count: int
    branch: str
    diff_bundle: str
    diffs_verdict: str
    failed_task_ids: list
    final_decision: str
    final_note: str
    review_summary: str
    tasks_verdict: str
    total_tasks: int
    verify_passed: bool

    @classmethod
    def from_dict(cls, d: dict) -> "PublishOutputOutput":
        return cls(
            applied_count=d["applied_count"],
            branch=d["branch"],
            diff_bundle=d["diff_bundle"],
            diffs_verdict=d["diffs_verdict"],
            failed_task_ids=d["failed_task_ids"],
            final_decision=d["final_decision"],
            final_note=d["final_note"],
            review_summary=d["review_summary"],
            tasks_verdict=d["tasks_verdict"],
            total_tasks=d["total_tasks"],
            verify_passed=d["verify_passed"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["applied_count"] = self.applied_count
        out["branch"] = self.branch
        out["diff_bundle"] = self.diff_bundle
        out["diffs_verdict"] = self.diffs_verdict
        out["failed_task_ids"] = self.failed_task_ids
        out["final_decision"] = self.final_decision
        out["final_note"] = self.final_note
        out["review_summary"] = self.review_summary
        out["tasks_verdict"] = self.tasks_verdict
        out["total_tasks"] = self.total_tasks
        out["verify_passed"] = self.verify_passed
        return out
