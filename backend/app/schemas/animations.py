from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


Trajectory = Literal[
    "right_to_center",
    "left_to_center",
    "right_to_left",
    "left_to_right",
    "bottom_to_top",
    "top_to_bottom",
    "origin_to_target",
    "direct_impact",
    "area_effect",
]
Movement = Literal["linear", "ease_in", "ease_out", "arc"]
AnimationType = Literal["projectile", "impact", "area"]
RenderDirection = Literal["auto", "left", "right", "up", "down"]
AnimationEntityType = Literal["character", "npc", "enemy", "item", "skill"]


class NormalizedPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)


class AnimationAssociationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: AnimationEntityType
    entity_id: UUID


class AnimationConfigurationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=20000)
    asset_id: UUID
    impact_asset_id: UUID | None = None
    animation_type: AnimationType = "projectile"
    trajectory: Trajectory = "origin_to_target"
    movement: Movement = "linear"
    origin: NormalizedPoint
    target: NormalizedPoint
    scale: float = Field(default=1, ge=0.1, le=5, allow_inf_nan=False)
    rotation: float = Field(default=0, ge=-3600, le=3600, allow_inf_nan=False)
    gif_playback_rate: float = Field(default=1, ge=0.1, le=4, allow_inf_nan=False)
    travel_duration_ms: int = Field(default=700, ge=0, le=30000)
    travel_speed: float = Field(default=0.75, gt=0, le=10, allow_inf_nan=False)
    impact_time_ms: int = Field(default=0, ge=0, le=30000)
    render_layer: int = Field(default=10, ge=0, le=100)
    direction: RenderDirection = "auto"
    extra: dict[str, Any] = Field(default_factory=dict, max_length=100)
    associations: list[AnimationAssociationWrite] = Field(default_factory=list, max_length=100)

class AnimationConfigurationCreate(AnimationConfigurationWrite):
    pass


class AnimationConfigurationUpdate(AnimationConfigurationWrite):
    pass
