from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


EntityType = Literal["character", "npc", "enemy", "item", "skill"]
ProfileAvailability = Literal["draft", "available", "archived"]
AssetRole = Literal["main_image", "sprite", "idle", "attack", "damage", "defeat", "impact"]
AnimationRole = Literal["idle", "attack", "damage", "defeat", "impact", "ability", "weapon_attack"]
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


class StrictProfileSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NormalizedPosition(StrictProfileSchema):
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)


class ContentAssetBindingWrite(StrictProfileSchema):
    role: AssetRole
    asset_id: UUID


class ContentAnimationBindingWrite(StrictProfileSchema):
    role: AnimationRole
    animation_id: UUID


class ContentSkillAssociationWrite(StrictProfileSchema):
    skill_id: UUID
    attack_speed_override: float | None = Field(default=None, gt=0, le=100, allow_inf_nan=False)


class EnemySpecialRewardWrite(StrictProfileSchema):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    item_ids: list[UUID] = Field(default_factory=list, max_length=50)


class CharacterContentSettings(StrictProfileSchema):
    actor_type: Literal["playable_character"] = "playable_character"
    attack_release_delay_ms: int = Field(default=500, ge=0, le=30000)
    attack_animation_duration_ms: int = Field(default=700, ge=1, le=30000)


class NpcContentSettings(StrictProfileSchema):
    actor_type: Literal["npc", "ally", "hostile"] = "npc"


class EnemyContentSettings(StrictProfileSchema):
    category: Literal["common", "special", "miniboss", "boss"] = "common"
    default_attack_speed: float = Field(default=1, gt=0, le=100, allow_inf_nan=False)
    gold_reward: int = Field(default=0, ge=0, le=2_000_000_000)
    special_rewards: list[EnemySpecialRewardWrite] = Field(default_factory=list, max_length=50)
    boss_difficulty: Literal["common", "medium", "difficult", "hard", "impossible"] = "common"
    max_attacks_per_turn: Literal[1, 2] = 1
    can_interrupt_turns: bool = False
    strategy: Literal[
        "baseline",
        "effective_damage",
        "mana_conservation",
        "focus_low_hp",
        "elemental_weakness",
        "survival",
        "aggressive",
        "conservative",
        "economic",
        "tactical",
        "adaptive",
    ] = "baseline"
    attack_release_delay_ms: int = Field(default=500, ge=0, le=30000)
    attack_animation_duration_ms: int = Field(default=700, ge=1, le=30000)

    @model_validator(mode="after")
    def validate_boss_turn_options(self) -> "EnemyContentSettings":
        if self.max_attacks_per_turn == 2 and self.boss_difficulty not in {"hard", "impossible"}:
            raise ValueError("Somente bosses HARD ou IMPOSSÍVEIS podem ter dois ataques por turno.")
        if self.can_interrupt_turns and self.boss_difficulty not in {
            "difficult",
            "hard",
            "impossible",
        }:
            raise ValueError("Somente bosses DIFÍCIL, HARD ou IMPOSSÍVEIS podem interromper turnos.")
        return self


class WeaponContentSettings(StrictProfileSchema):
    weapon_type: str = Field(default="", max_length=80)
    attack: int = Field(default=0, ge=0, le=2_000_000_000)
    defense: int = Field(default=0, ge=0, le=2_000_000_000)
    reach: float = Field(default=1, ge=0, le=1000, allow_inf_nan=False)
    speed: float = Field(default=1, gt=0, le=100, allow_inf_nan=False)
    animation_display: Literal[
        "with_character",
        "follow_character",
        "during_strike",
        "effect_only",
    ] = "with_character"
    special_effects: dict[str, Any] = Field(default_factory=dict, max_length=50)


class SkillContentSettings(StrictProfileSchema):
    skill_type: str = Field(min_length=1, max_length=80)
    damage_base: int | None = Field(default=None, ge=0, le=2_000_000_000)
    reach: float = Field(default=1, ge=0, le=1000, allow_inf_nan=False)
    target_type: str = Field(default="single", min_length=1, max_length=40)
    default_speed: float = Field(default=1, gt=0, le=100, allow_inf_nan=False)
    travel_duration_ms: int = Field(default=700, ge=0, le=30000)
    impact_time_ms: int = Field(default=0, ge=0, le=30000)
    attack_release_delay_ms: int = Field(default=500, ge=0, le=30000)
    attack_animation_duration_ms: int = Field(default=700, ge=1, le=30000)
    projectile_only: bool = False
    combat_visual_mode: Literal["legacy", "separated"] = "legacy"
    trajectory: Trajectory = "origin_to_target"
    direction: Literal["auto", "left", "right", "up", "down"] = "auto"
    additional_effects: dict[str, Any] = Field(default_factory=dict, max_length=50)


class EntityContentProfileWrite(StrictProfileSchema):
    kind: str = Field(default="", max_length=80)
    availability: ProfileAvailability = "draft"
    scale: float = Field(default=1, ge=0.1, le=5, allow_inf_nan=False)
    orientation: Literal["auto", "left", "right"] = "auto"
    default_position: NormalizedPosition = Field(
        default_factory=lambda: NormalizedPosition(x=0.5, y=0.5)
    )
    attributes: dict[str, float] = Field(default_factory=dict, max_length=50)
    settings: dict[str, Any] = Field(default_factory=dict, max_length=50)
    assets: list[ContentAssetBindingWrite] = Field(default_factory=list, max_length=7)
    animations: list[ContentAnimationBindingWrite] = Field(default_factory=list, max_length=7)
    skills: list[ContentSkillAssociationWrite] = Field(default_factory=list, max_length=100)
    equipment_ids: list[UUID] = Field(default_factory=list, max_length=100)
