from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


AssetCategory = Literal[
    "characters",
    "npcs",
    "allies",
    "hostiles",
    "monsters",
    "minibosses",
    "bosses",
    "weapons",
    "equipment",
    "spells",
    "powers",
    "visual_effects",
]

AssetEntityType = Literal["character", "npc", "enemy", "item", "skill"]


class AssetAssociationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    entity_type: AssetEntityType
    entity_id: UUID


class AssetMetadataWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=20000)
    category: AssetCategory
    subcategory: str | None = Field(default=None, max_length=80)
    asset_type: str | None = Field(default=None, max_length=80)
    is_public: bool = False
    associations: list[AssetAssociationWrite] = Field(default_factory=list, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def normalize_optional_labels(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for field in ("subcategory", "asset_type"):
            label = normalized.get(field)
            if isinstance(label, str):
                normalized[field] = label.strip() or None
        return normalized
