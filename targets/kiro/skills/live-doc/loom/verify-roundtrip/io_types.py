# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class VerifyRoundtripInput:
    VERSION: ClassVar[int] = 1
    vault_path: str
    scripts_ingestion: object
    scripts_inference: object
    scripts_presentation: object
    run_order_ingestion: object
    run_order_inference: object
    run_order_presentation: object
    result_subsections: list

    @classmethod
    def from_dict(cls, d: dict) -> "VerifyRoundtripInput":
        return cls(
            vault_path=d["vault_path"],
            scripts_ingestion=d["scripts_ingestion"],
            scripts_inference=d["scripts_inference"],
            scripts_presentation=d["scripts_presentation"],
            run_order_ingestion=d["run_order_ingestion"],
            run_order_inference=d["run_order_inference"],
            run_order_presentation=d["run_order_presentation"],
            result_subsections=d["result_subsections"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["vault_path"] = self.vault_path
        out["scripts_ingestion"] = self.scripts_ingestion
        out["scripts_inference"] = self.scripts_inference
        out["scripts_presentation"] = self.scripts_presentation
        out["run_order_ingestion"] = self.run_order_ingestion
        out["run_order_inference"] = self.run_order_inference
        out["run_order_presentation"] = self.run_order_presentation
        out["result_subsections"] = self.result_subsections
        return out


@dataclass
class VerifyRoundtripOutput:
    VERSION: ClassVar[int] = 1
    ok: bool

    @classmethod
    def from_dict(cls, d: dict) -> "VerifyRoundtripOutput":
        return cls(
            ok=d["ok"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["ok"] = self.ok
        return out
