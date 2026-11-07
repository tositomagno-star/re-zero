from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CombatStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enemies: list[UUID] = Field(min_length=1, max_length=12)


class CombatActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: UUID
    action: Literal["attack", "skill", "end_turn"]
    target_id: UUID | None = None
    skill_id: UUID | None = None
