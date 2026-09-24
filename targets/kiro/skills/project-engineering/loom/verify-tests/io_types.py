# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class VerifyTestsInput:
    VERSION: ClassVar[int] = 1
    workspace_abs: str
    build_system: str
    installed_skills: list
    fallback_test_cmd: str

    @classmethod
    def from_dict(cls, d: dict) -> "VerifyTestsInput":
        return cls(
            workspace_abs=d["workspace_abs"],
            build_system=d["build_system"],
            installed_skills=d["installed_skills"],
            fallback_test_cmd=d["fallback_test_cmd"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["workspace_abs"] = self.workspace_abs
        out["build_system"] = self.build_system
        out["installed_skills"] = self.installed_skills
        out["fallback_test_cmd"] = self.fallback_test_cmd
        return out


@dataclass
class VerifyTestsOutput:
    VERSION: ClassVar[int] = 1
    test_cmd_used: str
    exit_code: int
    passed: bool
    stdout_tail: str
    stderr_tail: str

    @classmethod
    def from_dict(cls, d: dict) -> "VerifyTestsOutput":
        return cls(
            test_cmd_used=d["test_cmd_used"],
            exit_code=d["exit_code"],
            passed=d["passed"],
            stdout_tail=d["stdout_tail"],
            stderr_tail=d["stderr_tail"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["test_cmd_used"] = self.test_cmd_used
        out["exit_code"] = self.exit_code
        out["passed"] = self.passed
        out["stdout_tail"] = self.stdout_tail
        out["stderr_tail"] = self.stderr_tail
        return out
