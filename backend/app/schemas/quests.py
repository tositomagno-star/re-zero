import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.progression import ItemReward


_OBJECTIVE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


class StrictQuestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class QuestObjective(StrictQuestSchema):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    target: int = Field(default=1, ge=1, le=1_000_000)

    @model_validator(mode="after")
    def validate_id(self) -> "QuestObjective":
        if _OBJECTIVE_ID.fullmatch(self.id) is None:
            raise ValueError("O identificador do objetivo contém caracteres inválidos.")
        return self


class QuestConditions(StrictQuestSchema):
    objectives: list[QuestObjective] = Field(default_factory=list, max_length=50)
    require_all_objectives: bool = True

    @model_validator(mode="after")
    def reject_duplicate_objectives(self) -> "QuestConditions":
        ids = [objective.id for objective in self.objectives]
        if len(ids) != len(set(ids)):
            raise ValueError("Os objetivos da missão não podem repetir identificadores.")
        return self


class QuestReward(StrictQuestSchema):
    xp: int = Field(default=0, ge=0, le=2_000_000_000)
    gold: int = Field(default=0, ge=0, le=2_000_000_000)
    items: list[ItemReward] = Field(default_factory=list, max_length=100)
    skill_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def reject_duplicate_rewards(self) -> "QuestReward":
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("A recompensa da missão não pode repetir itens.")
        if len(self.skill_ids) != len(set(self.skill_ids)):
            raise ValueError("A recompensa da missão não pode repetir habilidades.")
        return self


class QuestWrite(StrictQuestSchema):
    campaign_id: UUID
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=20_000)
    status: Literal["draft", "published", "inactive"] = "draft"
    npc_id: UUID | None = None
    conditions: QuestConditions = Field(default_factory=QuestConditions)
    rewards: QuestReward = Field(default_factory=QuestReward)


class QuestAssignmentWrite(StrictQuestSchema):
    character_ids: list[UUID] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def reject_duplicate_characters(self) -> "QuestAssignmentWrite":
        if len(self.character_ids) != len(set(self.character_ids)):
            raise ValueError("Um personagem não pode ser atribuído duas vezes.")
        return self


class QuestAcceptResponse(BaseModel):
    quest_id: UUID
    status: str
    progress: dict[str, Any]
