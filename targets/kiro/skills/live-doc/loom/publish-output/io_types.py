# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class PublishOutputInput:
    VERSION: ClassVar[int] = 1
    vault_path: str
    ingestion_runs: list
    inference_runs: list
    presentation_runs: list
    commit_sha: str

    @classmethod
    def from_dict(cls, d: dict) -> "PublishOutputInput":
        return cls(
            vault_path=d["vault_path"],
            ingestion_runs=d["ingestion_runs"],
            inference_runs=d["inference_runs"],
            presentation_runs=d["presentation_runs"],
            commit_sha=d["commit_sha"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["vault_path"] = self.vault_path
        out["ingestion_runs"] = self.ingestion_runs
        out["inference_runs"] = self.inference_runs
        out["presentation_runs"] = self.presentation_runs
        out["commit_sha"] = self.commit_sha
        return out


@dataclass
class PublishOutputOutput:
    VERSION: ClassVar[int] = 1
    vault_path: str
    scripts_run: int
    commit_sha: str

    @classmethod
    def from_dict(cls, d: dict) -> "PublishOutputOutput":
        return cls(
            vault_path=d["vault_path"],
            scripts_run=d["scripts_run"],
            commit_sha=d["commit_sha"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["vault_path"] = self.vault_path
        out["scripts_run"] = self.scripts_run
        out["commit_sha"] = self.commit_sha
        return out
