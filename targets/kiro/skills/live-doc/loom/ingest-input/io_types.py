# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar
from loom.engine.reserved import LoomMeta, TaskMeta


@dataclass
class IngestInputInput:
    VERSION: ClassVar[int] = 1
    name: str
    vault_path: str
    loom: LoomMeta | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "IngestInputInput":
        return cls(
            name=d["name"],
            vault_path=d["vault_path"],
            loom=(LoomMeta.from_dict(d["__loom"]) if "__loom" in d else None),
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["name"] = self.name
        out["vault_path"] = self.vault_path
        if self.loom is not None:
            out["__loom"] = self.loom.to_dict()
        return out


@dataclass
class IngestInputOutput:
    VERSION: ClassVar[int] = 1
    name: str
    vault_path: str
    data_dir: str

    @classmethod
    def from_dict(cls, d: dict) -> "IngestInputOutput":
        return cls(
            name=d["name"],
            vault_path=d["vault_path"],
            data_dir=d["data_dir"],
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["name"] = self.name
        out["vault_path"] = self.vault_path
        out["data_dir"] = self.data_dir
        return out
