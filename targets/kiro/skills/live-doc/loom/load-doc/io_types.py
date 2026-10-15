# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class LoadDocInput:
    VERSION: ClassVar[int] = 1
    vault_path: str

    @classmethod
    def from_dict(cls, d: dict) -> "LoadDocInput":
        return cls(
            vault_path=d["vault_path"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["vault_path"] = self.vault_path
        return out


@dataclass
class LoadDocOutput:
    VERSION: ClassVar[int] = 1
    intro: str
    instructions: dict
    prev_result_header: str
    prev_result_subsections: list
    appendix_scripts: dict
    run_order: dict

    @classmethod
    def from_dict(cls, d: dict) -> "LoadDocOutput":
        return cls(
            intro=d["intro"],
            instructions=d["instructions"],
            prev_result_header=d["prev_result_header"],
            prev_result_subsections=d["prev_result_subsections"],
            appendix_scripts=d["appendix_scripts"],
            run_order=d["run_order"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["intro"] = self.intro
        out["instructions"] = self.instructions
        out["prev_result_header"] = self.prev_result_header
        out["prev_result_subsections"] = self.prev_result_subsections
        out["appendix_scripts"] = self.appendix_scripts
        out["run_order"] = self.run_order
        return out
