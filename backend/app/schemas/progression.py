from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ItemReward(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: UUID
    quantity: int = Field(default=1, gt=0, le=1_000_000)


class CharacterRewardSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["campaign", "narrative", "quest", "combat", "world_reward"]
    xp: int = Field(default=0, ge=0, le=2_000_000_000)
    gold: int = Field(default=0, ge=0, le=2_000_000_000)
    items: list[ItemReward] = Field(default_factory=list, max_length=100)
    skill_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def reject_duplicate_catalog_entries(self) -> "CharacterRewardSpec":
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("A recompensa não pode repetir itens.")
        if len(self.skill_ids) != len(set(self.skill_ids)):
            raise ValueError("A recompensa não pode repetir habilidades.")
        if not (self.xp or self.gold or self.items or self.skill_ids):
            raise ValueError("A recompensa precisa conter ao menos um benefício.")
        return self
