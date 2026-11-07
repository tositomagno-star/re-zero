import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CampaignVotingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_vote_change: bool = True
    deadline_seconds: int | None = Field(default=None, gt=0)
    tie_breaker: Literal["unresolved", "choice_order"] = "unresolved"


class CampaignCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    max_players: int = Field(default=7, ge=3, le=7)
    solo: bool = False
    difficulty: Literal["normal", "hard", "legendary"] = "normal"
    voting_settings: CampaignVotingSettings = Field(default_factory=CampaignVotingSettings)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("O nome da campanha não pode ficar vazio.")
        return normalized


class JoinCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=32)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Informe um código de campanha válido.")
        normalized = value.strip().upper()
        if (
            re.fullmatch(r"RZ-[0-9]{5}", normalized) is None
            and re.fullmatch(r"[0-9A-F]{32}", normalized) is None
        ):
            raise ValueError("Informe um código de campanha válido.")
        return normalized


class CharacterUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("O nome do personagem não pode ficar vazio.")
        return normalized


class SoloCharacterCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("O nome do personagem não pode ficar vazio.")
        return normalized


class SoloCharacterResponse(BaseModel):
    id: UUID
    name: str
    character_class: str | None
    ancestry: str | None
    level: int
    hp: int
    max_hp: int
    active: bool


class ReadyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_ready: bool


class EquipmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: str = Field(min_length=1, max_length=32)


class ShopTransactionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: UUID
    quantity: int = Field(default=1, ge=1, le=100)


class CampaignMemberResponse(BaseModel):
    user_id: UUID
    username: str
    display_name: str
    role: str
    is_ready: bool
    is_connected: bool
    character_id: UUID | None
    character_name: str | None
    level: int | None
    hp: int | None
    max_hp: int | None
    mana: int | None
    max_mana: int | None


class CampaignSummaryResponse(BaseModel):
    id: UUID
    title: str
    description: str
    join_code: str
    status: str
    owner_id: UUID
    owner_display_name: str
    min_players: int
    max_players: int
    participant_count: int
    available_slots: int
    current_chapter_id: UUID | None
    current_node_id: UUID | None
    last_activity_at: datetime
    membership_status: str
    is_owner: bool
    solo: bool = False


class CampaignResponse(CampaignSummaryResponse):
    members: list[CampaignMemberResponse]


class CharacterSheetItemResponse(BaseModel):
    item_id: UUID
    name: str
    description: str
    category: str
    is_career: bool = False
    rarity: str
    image_url: str | None
    weight: int
    effects: dict[str, Any]
    quantity: int
    is_equipped: bool
    slot: str | None
    origin: dict[str, Any] = Field(default_factory=dict)


class CharacterSheetSkillResponse(BaseModel):
    id: UUID
    name: str
    category: str
    description: str
    mana_cost: int
    effects: dict[str, Any]
    target: str
    cooldown_seconds: int
    origin: dict[str, Any] = Field(default_factory=dict)


class CharacterSheetQuestResponse(BaseModel):
    id: UUID
    title: str
    description: str
    status: str
    progress: dict[str, Any]
    objectives: list[dict[str, Any]]
    rewards: dict[str, Any]


class CampaignQuestResponse(BaseModel):
    id: UUID
    title: str
    description: str
    status: str
    progress: dict[str, Any]
    objectives: list[dict[str, Any]]
    rewards: dict[str, Any]


class CampaignQuestAcceptResponse(BaseModel):
    quest_id: UUID
    status: str
    progress: dict[str, Any]


class CharacterRewardItemResponse(BaseModel):
    item_id: UUID
    name: str
    quantity: int


class CharacterProgressionEventResponse(BaseModel):
    id: UUID
    created_at: datetime
    source_type: str
    source_id: UUID | None = None
    source_name: str | None = None
    xp_awarded: int
    xp_before: int
    xp_after: int
    level_before: int
    level_after: int
    gold_awarded: int
    attribute_points_awarded: int
    max_hp_increase: int
    max_mana_increase: int
    items: list[CharacterRewardItemResponse]


class CharacterSheetResponse(BaseModel):
    name: str
    description: str
    character_class: str | None
    ancestry: str | None
    level: int
    xp: int
    xp_to_next_level: int | None
    xp_progress_percent: int
    attribute_points: int
    gold: int
    hp: int
    max_hp: int
    mana: int
    max_mana: int
    attributes: dict[str, Any]
    attribute_resolution: dict[str, Any] = {}
    inventory: list[CharacterSheetItemResponse]
    skills: list[CharacterSheetSkillResponse]
    quests: list[CharacterSheetQuestResponse]
    progression_history: list[CharacterProgressionEventResponse]


class StoryVoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice_id: UUID


class CampaignMemberActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID


class NarrativeChoiceResponse(BaseModel):
    id: UUID
    label: str
    position: int
    next_node_id: UUID | None
    conditions: dict[str, Any]
    consequences: dict[str, Any]


class NarrativeChapterResponse(BaseModel):
    id: UUID
    title: str
    summary: str
    narrative: str


class NarrativeSceneResponse(BaseModel):
    id: UUID
    title: str
    narrative: str
    choices: list[NarrativeChoiceResponse]


class NarrativeVoteTallyResponse(BaseModel):
    choice_id: UUID
    label: str
    votes: int


class NarrativeVoteResponse(BaseModel):
    status: str
    round_number: int
    deadline_at: datetime | None
    allow_vote_change: bool
    eligible_count: int
    voted_count: int
    my_choice_id: UUID | None
    tally: list[NarrativeVoteTallyResponse]
    result: dict[str, Any] | None


class CampaignEventResponse(BaseModel):
    sequence_number: int
    actor_user_id: UUID | None
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class NarrativeGameResponse(BaseModel):
    session_id: UUID
    status: str
    chapter: NarrativeChapterResponse
    scene: NarrativeSceneResponse
    participants: list[CampaignMemberResponse]
    vote: NarrativeVoteResponse | None
    last_result: dict[str, Any] | None
    history: list[CampaignEventResponse]
