# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class CommitVaultInput:
    VERSION: ClassVar[int] = 1
    vault_path: str
    name: str

    @classmethod
    def from_dict(cls, d: dict) -> "CommitVaultInput":
        return cls(
            vault_path=d["vault_path"],
            name=d["name"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["vault_path"] = self.vault_path
        out["name"] = self.name
        return out


@dataclass
class CommitVaultOutput:
    VERSION: ClassVar[int] = 1
    commit_sha: str
    message: str

    @classmethod
    def from_dict(cls, d: dict) -> "CommitVaultOutput":
        return cls(
            commit_sha=d["commit_sha"],
            message=d["message"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["commit_sha"] = self.commit_sha
        out["message"] = self.message
        return out
