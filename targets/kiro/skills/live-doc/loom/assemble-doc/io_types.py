# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class AssembleDocInput:
    VERSION: ClassVar[int] = 1
    intro: str
    instructions: dict
    result_header: str
    result_subsections: list
    scripts_ingestion: object
    scripts_inference: object
    scripts_presentation: object
    run_order_ingestion: object
    run_order_inference: object
    run_order_presentation: object
    vault_path: str

    @classmethod
    def from_dict(cls, d: dict) -> "AssembleDocInput":
        return cls(
            intro=d["intro"],
            instructions=d["instructions"],
            result_header=d["result_header"],
            result_subsections=d["result_subsections"],
            scripts_ingestion=d["scripts_ingestion"],
            scripts_inference=d["scripts_inference"],
            scripts_presentation=d["scripts_presentation"],
            run_order_ingestion=d["run_order_ingestion"],
            run_order_inference=d["run_order_inference"],
            run_order_presentation=d["run_order_presentation"],
            vault_path=d["vault_path"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["intro"] = self.intro
        out["instructions"] = self.instructions
        out["result_header"] = self.result_header
        out["result_subsections"] = self.result_subsections
        out["scripts_ingestion"] = self.scripts_ingestion
        out["scripts_inference"] = self.scripts_inference
        out["scripts_presentation"] = self.scripts_presentation
        out["run_order_ingestion"] = self.run_order_ingestion
        out["run_order_inference"] = self.run_order_inference
        out["run_order_presentation"] = self.run_order_presentation
        out["vault_path"] = self.vault_path
        return out


@dataclass
class AssembleDocOutput:
    VERSION: ClassVar[int] = 1
    vault_path: str
    bytes_written: int

    @classmethod
    def from_dict(cls, d: dict) -> "AssembleDocOutput":
        return cls(
            vault_path=d["vault_path"],
            bytes_written=d["bytes_written"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["vault_path"] = self.vault_path
        out["bytes_written"] = self.bytes_written
        return out
