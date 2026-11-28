# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class IngestInputInput:
    VERSION: ClassVar[int] = 1
    skill_dir: str
    name: str
    category: str
    type: str
    design_kind: str
    design: dict | None | None = None
    plan: dict | None | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "IngestInputInput":
        return cls(
            skill_dir=d["skill_dir"],
            name=d["name"],
            category=d["category"],
            type=d["type"],
            design_kind=d["design_kind"],
            design=d.get("design"),
            plan=d.get("plan"),
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["skill_dir"] = self.skill_dir
        out["name"] = self.name
        out["category"] = self.category
        out["type"] = self.type
        out["design_kind"] = self.design_kind
        if self.design is not None:
            out["design"] = self.design
        if self.plan is not None:
            out["plan"] = self.plan
        return out


@dataclass
class IngestInputOutput:
    VERSION: ClassVar[int] = 1
    skill_dir: str
    name: str
    category: str
    type: str
    design_kind: str
    design: dict | None | None = None
    plan: dict | None | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "IngestInputOutput":
        return cls(
            skill_dir=d["skill_dir"],
            name=d["name"],
            category=d["category"],
            type=d["type"],
            design_kind=d["design_kind"],
            design=d.get("design"),
            plan=d.get("plan"),
        )

    def to_dict(self) -> dict:
        out: dict = {}
        out["skill_dir"] = self.skill_dir
        out["name"] = self.name
        out["category"] = self.category
        out["type"] = self.type
        out["design_kind"] = self.design_kind
        if self.design is not None:
            out["design"] = self.design
        if self.plan is not None:
            out["plan"] = self.plan
        return out
