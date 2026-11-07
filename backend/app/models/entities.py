from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UUIDPrimaryKey:
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "username_key = lower(username)",
            name="ck_user_username_key_normalized",
        ),
    )

    username: Mapped[str] = mapped_column(String(32))
    username_key: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)

    profile: Mapped["PlayerProfile | None"] = relationship(back_populates="user")
    owned_campaigns: Mapped[list["Campaign"]] = relationship(back_populates="owner")


class PlayerProfile(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "player_profiles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    display_name: Mapped[str] = mapped_column(String(80))
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    bio: Mapped[str | None] = mapped_column(Text)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    user: Mapped["User"] = relationship(back_populates="profile")


class ExternalIdentity(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_external_identity_subject"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(128))


class Campaign(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint("min_players >= 1 AND min_players <= 7", name="ck_campaign_min_players"),
        CheckConstraint("max_players >= min_players AND max_players <= 7", name="ck_campaign_max_players"),
        Index("ix_campaign_last_activity", "last_activity_at"),
    )

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="waiting", nullable=False)
    visibility: Mapped[str] = mapped_column(String(24), default="private", nullable=False)
    min_players: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    max_players: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    join_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    current_chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "chapters.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_campaign_current_chapter",
        )
    )
    current_node_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("story_nodes.id", ondelete="SET NULL", name="fk_campaign_current_node")
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    owner: Mapped["User"] = relationship(back_populates="owned_campaigns")
    members: Mapped[list["CampaignMember"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", foreign_keys="Chapter.campaign_id"
    )


class CampaignMember(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "campaign_members"
    __table_args__ = (
        UniqueConstraint("campaign_id", "user_id", name="uq_campaign_member_user"),
        Index("ix_campaign_members_campaign_status", "campaign_id", "status"),
        ForeignKeyConstraint(
            ["character_id", "campaign_id", "user_id"],
            ["characters.id", "characters.campaign_id", "characters.owner_id"],
            name="fk_member_owned_campaign_character",
            ondelete="RESTRICT",
            match="SIMPLE",
        ),
    )

    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    character_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    role: Mapped[str] = mapped_column(String(24), default="player", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_ready: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    campaign: Mapped["Campaign"] = relationship(back_populates="members")


class CampaignInvitation(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "campaign_invitations"

    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    invited_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    invited_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    invite_code: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Character(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "characters"
    __table_args__ = (
        UniqueConstraint("id", "campaign_id", "owner_id", name="uq_character_campaign_owner"),
        CheckConstraint("level >= 1", name="ck_character_level"),
        CheckConstraint("hp >= 0 AND max_hp >= hp", name="ck_character_hp"),
        CheckConstraint("mana >= 0 AND max_mana >= mana", name="ck_character_mana"),
        CheckConstraint("xp >= 0 AND gold >= 0", name="ck_character_xp_gold"),
        CheckConstraint("attribute_points >= 0", name="ck_character_attribute_points"),
    )

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ancestry: Mapped[str | None] = mapped_column(String(80))
    character_class: Mapped[str | None] = mapped_column(String(80))
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attribute_points: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    hp: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_hp: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    mana: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_mana: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)


class Chapter(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("campaign_id", "position", name="uq_chapter_position"),
        Index(
            "uq_global_chapter_position",
            "position",
            unique=True,
            sqlite_where=text("campaign_id IS NULL"),
            postgresql_where=text("campaign_id IS NULL"),
        ),
    )

    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    narrative: Mapped[str] = mapped_column(Text, default="", nullable=False)
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    campaign: Mapped["Campaign"] = relationship(
        back_populates="chapters", foreign_keys=[campaign_id]
    )
    nodes: Mapped[list["StoryNode"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan"
    )


class StoryNode(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "story_nodes"
    __table_args__ = (UniqueConstraint("chapter_id", "position", name="uq_story_node_position"),)

    chapter_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    narrative: Mapped[str] = mapped_column(Text, default="", nullable=False)
    node_type: Mapped[str] = mapped_column(String(32), default="narrative", nullable=False)
    position: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    chapter: Mapped["Chapter"] = relationship(back_populates="nodes")
    choices: Mapped[list["StoryChoice"]] = relationship(
        back_populates="node", cascade="all, delete-orphan", foreign_keys="StoryChoice.node_id"
    )


class StoryChoice(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "story_choices"
    __table_args__ = (
        UniqueConstraint("node_id", "position", name="uq_story_choice_position"),
        UniqueConstraint("id", "node_id", name="uq_story_choice_node"),
    )

    node_id: Mapped[UUID] = mapped_column(
        ForeignKey("story_nodes.id", ondelete="CASCADE"), index=True
    )
    next_node_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("story_nodes.id", ondelete="SET NULL")
    )
    label: Mapped[str] = mapped_column(String(240))
    position: Mapped[int] = mapped_column(Integer)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    consequences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    node: Mapped["StoryNode"] = relationship(back_populates="choices", foreign_keys=[node_id])


class StoryNodeNpc(Base):
    __tablename__ = "story_node_npcs"

    node_id: Mapped[UUID] = mapped_column(
        ForeignKey("story_nodes.id", ondelete="CASCADE"), primary_key=True
    )
    npc_id: Mapped[UUID] = mapped_column(
        ForeignKey("non_player_characters.id", ondelete="CASCADE"), primary_key=True
    )


class ChapterNpc(Base):
    __tablename__ = "chapter_npcs"

    chapter_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), primary_key=True
    )
    npc_id: Mapped[UUID] = mapped_column(
        ForeignKey("non_player_characters.id", ondelete="RESTRICT"), primary_key=True
    )


class ChapterEnemy(Base):
    __tablename__ = "chapter_enemies"

    chapter_id: Mapped[UUID] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), primary_key=True
    )
    enemy_id: Mapped[UUID] = mapped_column(
        ForeignKey("enemies.id", ondelete="RESTRICT"), primary_key=True
    )


class StoryVote(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "story_votes"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "node_id", "round_number", "user_id", name="uq_story_vote_per_round"
        ),
        ForeignKeyConstraint(
            ["choice_id", "node_id"],
            ["story_choices.id", "story_choices.node_id"],
            name="fk_story_vote_choice_node",
            ondelete="CASCADE",
        ),
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[UUID] = mapped_column(ForeignKey("story_nodes.id", ondelete="CASCADE"))
    choice_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    round_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class NonPlayerCharacter(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "non_player_characters"

    campaign_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    personality: Mapped[str] = mapped_column(Text, default="", nullable=False)
    story_role: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    campaign_relation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    player_relations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    quests: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    relationship_conditions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_placeholder: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class NpcDialogue(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "npc_dialogues"
    __table_args__ = (
        UniqueConstraint("npc_id", "position", name="uq_npc_dialogue_position"),
    )

    npc_id: Mapped[UUID] = mapped_column(
        ForeignKey("non_player_characters.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(120))
    line: Mapped[str] = mapped_column(Text)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class NpcRelationship(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "npc_relationships"
    __table_args__ = (
        UniqueConstraint("npc_id", "character_id", name="uq_npc_character_relationship"),
    )

    npc_id: Mapped[UUID] = mapped_column(
        ForeignKey("non_player_characters.id", ondelete="CASCADE")
    )
    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE")
    )
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Quest(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "quests"

    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    npc_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("non_player_characters.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    rewards: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class CharacterQuest(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "character_quests"
    __table_args__ = (
        UniqueConstraint("character_id", "quest_id", name="uq_character_quest"),
    )

    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    quest_id: Mapped[UUID] = mapped_column(ForeignKey("quests.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(24), default="available", nullable=False)
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Item(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("price >= 0 AND weight >= 0", name="ck_item_price_weight"),
    )

    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(32))
    rarity: Mapped[str] = mapped_column(String(32), default="common", nullable=False)
    price: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    effects: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_stackable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    requirements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usage: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    previous_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("items.id", ondelete="SET NULL")
    )


class CharacterItem(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "character_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_character_item_quantity"),
        UniqueConstraint("character_id", "item_id", name="uq_character_item"),
    )

    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[UUID] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_equipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    slot: Mapped[str | None] = mapped_column(String(32))
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    origin: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Skill(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "skills"
    __table_args__ = (
        CheckConstraint(
            "mana_cost >= 0 AND cooldown_seconds >= 0", name="ck_skill_cost_cooldown"
        ),
    )

    name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    mana_cost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    effects: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    target: Mapped[str] = mapped_column(String(32), default="single", nullable=False)
    requirements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)


class CharacterSkill(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "character_skills"
    __table_args__ = (UniqueConstraint("character_id", "skill_id", name="uq_character_skill"),)

    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    skill_id: Mapped[UUID] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"))
    learned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    origin: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Enemy(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "enemies"
    __table_args__ = (
        CheckConstraint("level >= 1 AND hp > 0", name="ck_enemy_level_hp"),
        CheckConstraint("xp_reward >= 0", name="ck_enemy_xp_reward"),
    )

    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    hp: Mapped[int] = mapped_column(Integer)
    attack: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    defense: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    speed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    abilities: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    resistances: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    weaknesses: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rewards: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    difficulty: Mapped[str] = mapped_column(String(24), default="normal", nullable=False)
    appearance_chance: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    previous_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("enemies.id", ondelete="SET NULL")
    )


class Asset(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint(
            "category IN ('characters', 'npcs', 'allies', 'hostiles', 'monsters', "
            "'minibosses', 'bosses', 'weapons', 'equipment', 'spells', 'powers', "
            "'visual_effects')",
            name="ck_asset_category",
        ),
        CheckConstraint("size_bytes > 0 AND size_bytes <= 5242880", name="ck_asset_size"),
        CheckConstraint(
            "width >= 1 AND width <= 8192 AND height >= 1 AND height <= 8192",
            name="ck_asset_dimensions",
        ),
        UniqueConstraint("storage_key", name="uq_assets_storage_key"),
        Index("ix_assets_category_created_at", "category", "created_at"),
    )

    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(32))
    subcategory: Mapped[str | None] = mapped_column(String(80))
    asset_type: Mapped[str | None] = mapped_column(String(80))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(32))
    extension: Mapped[str] = mapped_column(String(8))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(64))
    analysis_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        server_default=text("'{}'"),
        nullable=False,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )


class AssetAssociation(UUIDPrimaryKey, Base):
    __tablename__ = "asset_entity_associations"
    __table_args__ = (
        CheckConstraint(
            "(character_id IS NOT NULL AND npc_id IS NULL AND enemy_id IS NULL "
            "AND item_id IS NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NOT NULL AND enemy_id IS NULL "
            "AND item_id IS NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NULL AND enemy_id IS NOT NULL "
            "AND item_id IS NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NULL AND enemy_id IS NULL "
            "AND item_id IS NOT NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NULL AND enemy_id IS NULL "
            "AND item_id IS NULL AND skill_id IS NOT NULL)",
            name="ck_asset_association_one_entity",
        ),
        Index(
            "uq_asset_association_character",
            "asset_id",
            "character_id",
            unique=True,
            sqlite_where=text("character_id IS NOT NULL"),
            postgresql_where=text("character_id IS NOT NULL"),
        ),
        Index(
            "uq_asset_association_npc",
            "asset_id",
            "npc_id",
            unique=True,
            sqlite_where=text("npc_id IS NOT NULL"),
            postgresql_where=text("npc_id IS NOT NULL"),
        ),
        Index(
            "uq_asset_association_enemy",
            "asset_id",
            "enemy_id",
            unique=True,
            sqlite_where=text("enemy_id IS NOT NULL"),
            postgresql_where=text("enemy_id IS NOT NULL"),
        ),
        Index(
            "uq_asset_association_item",
            "asset_id",
            "item_id",
            unique=True,
            sqlite_where=text("item_id IS NOT NULL"),
            postgresql_where=text("item_id IS NOT NULL"),
        ),
        Index(
            "uq_asset_association_skill",
            "asset_id",
            "skill_id",
            unique=True,
            sqlite_where=text("skill_id IS NOT NULL"),
            postgresql_where=text("skill_id IS NOT NULL"),
        ),
        Index("ix_asset_association_asset_id", "asset_id"),
    )

    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    character_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("characters.id", ondelete="RESTRICT")
    )
    npc_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("non_player_characters.id", ondelete="RESTRICT")
    )
    enemy_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("enemies.id", ondelete="RESTRICT")
    )
    item_id: Mapped[UUID | None] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    skill_id: Mapped[UUID | None] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"))


class AnimationConfiguration(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "animation_configurations"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    impact_asset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT")
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class AnimationConfigurationAssociation(UUIDPrimaryKey, Base):
    __tablename__ = "animation_configuration_associations"
    __table_args__ = (
        CheckConstraint(
            "(character_id IS NOT NULL AND npc_id IS NULL AND enemy_id IS NULL "
            "AND item_id IS NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NOT NULL AND enemy_id IS NULL "
            "AND item_id IS NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NULL AND enemy_id IS NOT NULL "
            "AND item_id IS NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NULL AND enemy_id IS NULL "
            "AND item_id IS NOT NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NULL AND enemy_id IS NULL "
            "AND item_id IS NULL AND skill_id IS NOT NULL)",
            name="ck_animation_association_one_entity",
        ),
        Index(
            "uq_animation_association_character",
            "configuration_id",
            "character_id",
            unique=True,
            sqlite_where=text("character_id IS NOT NULL"),
            postgresql_where=text("character_id IS NOT NULL"),
        ),
        Index(
            "uq_animation_association_npc",
            "configuration_id",
            "npc_id",
            unique=True,
            sqlite_where=text("npc_id IS NOT NULL"),
            postgresql_where=text("npc_id IS NOT NULL"),
        ),
        Index(
            "uq_animation_association_enemy",
            "configuration_id",
            "enemy_id",
            unique=True,
            sqlite_where=text("enemy_id IS NOT NULL"),
            postgresql_where=text("enemy_id IS NOT NULL"),
        ),
        Index(
            "uq_animation_association_item",
            "configuration_id",
            "item_id",
            unique=True,
            sqlite_where=text("item_id IS NOT NULL"),
            postgresql_where=text("item_id IS NOT NULL"),
        ),
        Index(
            "uq_animation_association_skill",
            "configuration_id",
            "skill_id",
            unique=True,
            sqlite_where=text("skill_id IS NOT NULL"),
            postgresql_where=text("skill_id IS NOT NULL"),
        ),
        Index("ix_animation_association_configuration_id", "configuration_id"),
    )

    configuration_id: Mapped[UUID] = mapped_column(
        ForeignKey("animation_configurations.id", ondelete="CASCADE"), nullable=False
    )
    character_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("characters.id", ondelete="RESTRICT")
    )
    npc_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("non_player_characters.id", ondelete="RESTRICT")
    )
    enemy_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("enemies.id", ondelete="RESTRICT")
    )
    item_id: Mapped[UUID | None] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    skill_id: Mapped[UUID | None] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"))


class EntityContentProfile(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "entity_content_profiles"
    __table_args__ = (
        CheckConstraint(
            "(character_id IS NOT NULL AND npc_id IS NULL AND enemy_id IS NULL "
            "AND item_id IS NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NOT NULL AND enemy_id IS NULL "
            "AND item_id IS NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NULL AND enemy_id IS NOT NULL "
            "AND item_id IS NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NULL AND enemy_id IS NULL "
            "AND item_id IS NOT NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NULL AND enemy_id IS NULL "
            "AND item_id IS NULL AND skill_id IS NOT NULL)",
            name="ck_entity_content_profile_one_entity",
        ),
        CheckConstraint(
            "availability IN ('draft', 'available', 'archived')",
            name="ck_entity_content_profile_availability",
        ),
        Index(
            "uq_entity_content_profile_character",
            "character_id",
            unique=True,
            sqlite_where=text("character_id IS NOT NULL"),
            postgresql_where=text("character_id IS NOT NULL"),
        ),
        Index(
            "uq_entity_content_profile_npc",
            "npc_id",
            unique=True,
            sqlite_where=text("npc_id IS NOT NULL"),
            postgresql_where=text("npc_id IS NOT NULL"),
        ),
        Index(
            "uq_entity_content_profile_enemy",
            "enemy_id",
            unique=True,
            sqlite_where=text("enemy_id IS NOT NULL"),
            postgresql_where=text("enemy_id IS NOT NULL"),
        ),
        Index(
            "uq_entity_content_profile_item",
            "item_id",
            unique=True,
            sqlite_where=text("item_id IS NOT NULL"),
            postgresql_where=text("item_id IS NOT NULL"),
        ),
        Index(
            "uq_entity_content_profile_skill",
            "skill_id",
            unique=True,
            sqlite_where=text("skill_id IS NOT NULL"),
            postgresql_where=text("skill_id IS NOT NULL"),
        ),
    )

    character_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE")
    )
    npc_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("non_player_characters.id", ondelete="CASCADE")
    )
    enemy_id: Mapped[UUID | None] = mapped_column(ForeignKey("enemies.id", ondelete="CASCADE"))
    item_id: Mapped[UUID | None] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    skill_id: Mapped[UUID | None] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    availability: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    scale: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    orientation: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)
    default_position: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    attributes: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class EntityContentAssetBinding(UUIDPrimaryKey, Base):
    __tablename__ = "entity_content_asset_bindings"
    __table_args__ = (UniqueConstraint("profile_id", "role", name="uq_content_asset_profile_role"),)

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("entity_content_profiles.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32))
    asset_id: Mapped[UUID] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), index=True)


class EntityContentAnimationBinding(UUIDPrimaryKey, Base):
    __tablename__ = "entity_content_animation_bindings"
    __table_args__ = (
        UniqueConstraint("profile_id", "role", name="uq_content_animation_profile_role"),
    )

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("entity_content_profiles.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32))
    animation_id: Mapped[UUID] = mapped_column(
        ForeignKey("animation_configurations.id", ondelete="RESTRICT"), index=True
    )


class EntityContentSkillAssociation(UUIDPrimaryKey, Base):
    __tablename__ = "entity_content_skill_associations"
    __table_args__ = (
        UniqueConstraint("profile_id", "skill_id", name="uq_content_profile_skill"),
        CheckConstraint(
            "attack_speed_override IS NULL OR attack_speed_override > 0",
            name="ck_content_profile_skill_attack_speed",
        ),
    )

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("entity_content_profiles.id", ondelete="CASCADE"), index=True
    )
    skill_id: Mapped[UUID] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"), index=True)
    attack_speed_override: Mapped[float | None] = mapped_column(Float)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class EntityContentEquipmentAssociation(UUIDPrimaryKey, Base):
    __tablename__ = "entity_content_equipment_associations"
    __table_args__ = (
        UniqueConstraint("profile_id", "item_id", name="uq_content_profile_equipment"),
    )

    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("entity_content_profiles.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[UUID] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"), index=True)


class WorldSetting(TimestampMixin, Base):
    __tablename__ = "world_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class WorldReward(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "world_rewards"
    __table_args__ = (
        CheckConstraint("gold >= 0 AND xp >= 0", name="ck_world_reward_gold_xp"),
    )

    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    gold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    item_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DropRule(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "drop_rules"
    __table_args__ = (
        CheckConstraint(
            "chance_basis_points >= 0 AND chance_basis_points <= 10000",
            name="ck_drop_rule_chance",
        ),
        CheckConstraint(
            "min_quantity > 0 AND max_quantity >= min_quantity",
            name="ck_drop_rule_quantity",
        ),
        UniqueConstraint("enemy_id", "item_id", name="uq_enemy_drop_item"),
    )

    enemy_id: Mapped[UUID] = mapped_column(ForeignKey("enemies.id", ondelete="CASCADE"))
    item_id: Mapped[UUID] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    chance_basis_points: Mapped[int] = mapped_column(Integer)
    min_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Encounter(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "encounters"

    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    chapter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="planned", nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Combatant(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "combatants"
    __table_args__ = (
        UniqueConstraint("encounter_id", "character_id", name="uq_encounter_character"),
        UniqueConstraint(
            "encounter_id", "enemy_id", "instance_index", name="uq_encounter_enemy_instance"
        ),
        CheckConstraint(
            "(character_id IS NOT NULL AND enemy_id IS NULL) OR "
            "(character_id IS NULL AND enemy_id IS NOT NULL)",
            name="ck_combatant_entity",
        ),
    )

    encounter_id: Mapped[UUID] = mapped_column(
        ForeignKey("encounters.id", ondelete="CASCADE"), index=True
    )
    character_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE")
    )
    enemy_id: Mapped[UUID | None] = mapped_column(ForeignKey("enemies.id", ondelete="RESTRICT"))
    initiative: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_hp: Mapped[int] = mapped_column(Integer)
    current_mana: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    instance_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class CombatActionEvent(UUIDPrimaryKey, Base):
    __tablename__ = "combat_action_events"
    __table_args__ = (
        UniqueConstraint("encounter_id", "sequence_number", name="uq_combat_event_sequence"),
        UniqueConstraint("encounter_id", "idempotency_key", name="uq_combat_event_idempotency"),
        Index("ix_combat_event_encounter_created", "encounter_id", "created_at"),
    )

    encounter_id: Mapped[UUID] = mapped_column(
        ForeignKey("encounters.id", ondelete="CASCADE"), index=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CombatBalanceSetting(Base):
    __tablename__ = "combat_balance_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)


class GameSession(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "game_sessions"

    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    current_node_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("story_nodes.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), default="waiting", nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GameEvent(UUIDPrimaryKey, Base):
    __tablename__ = "game_events"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_number", name="uq_game_event_sequence"),
        UniqueConstraint("session_id", "idempotency_key", name="uq_game_event_idempotency"),
        Index("ix_game_event_session_created", "session_id", "created_at"),
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("game_sessions.id", ondelete="CASCADE")
    )
    sequence_number: Mapped[int] = mapped_column(Integer)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WalletTransaction(UUIDPrimaryKey, Base):
    __tablename__ = "wallet_transactions"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_wallet_transaction_amount"),)

    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    amount: Mapped[int] = mapped_column(Integer)
    transaction_type: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(String(240))
    source_type: Mapped[str | None] = mapped_column(String(32))
    source_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CharacterRewardGrant(UUIDPrimaryKey, Base):
    __tablename__ = "character_reward_grants"
    __table_args__ = (
        UniqueConstraint(
            "character_id",
            "idempotency_key",
            name="uq_character_reward_idempotency",
        ),
        CheckConstraint(
            "xp_awarded >= 0 AND xp_before >= 0 AND xp_after >= 0",
            name="ck_character_reward_xp",
        ),
        CheckConstraint(
            "gold_awarded >= 0 AND gold_before >= 0 AND gold_after >= 0",
            name="ck_character_reward_gold",
        ),
        CheckConstraint(
            "level_before >= 1 AND level_after >= level_before",
            name="ck_character_reward_level",
        ),
        Index(
            "ix_character_reward_history",
            "character_id",
            "created_at",
        ),
    )

    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(160))
    source_type: Mapped[str] = mapped_column(String(24))
    xp_awarded: Mapped[int] = mapped_column(Integer)
    xp_before: Mapped[int] = mapped_column(Integer)
    xp_after: Mapped[int] = mapped_column(Integer)
    level_before: Mapped[int] = mapped_column(Integer)
    level_after: Mapped[int] = mapped_column(Integer)
    gold_awarded: Mapped[int] = mapped_column(Integer)
    gold_before: Mapped[int] = mapped_column(Integer)
    gold_after: Mapped[int] = mapped_column(Integer)
    hp_before: Mapped[int] = mapped_column(Integer)
    hp_after: Mapped[int] = mapped_column(Integer)
    max_hp_before: Mapped[int] = mapped_column(Integer)
    max_hp_after: Mapped[int] = mapped_column(Integer)
    mana_before: Mapped[int] = mapped_column(Integer)
    mana_after: Mapped[int] = mapped_column(Integer)
    max_mana_before: Mapped[int] = mapped_column(Integer)
    max_mana_after: Mapped[int] = mapped_column(Integer)
    attribute_points_before: Mapped[int] = mapped_column(Integer)
    attribute_points_after: Mapped[int] = mapped_column(Integer)
    reward_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Notification(UUIDPrimaryKey, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notification_user_created", "user_id", "created_at"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    notification_type: Mapped[str] = mapped_column(String(48))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DiscordIntegration(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "discord_integrations"

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(24), default="not_configured", nullable=False)
    application_id: Mapped[str | None] = mapped_column(String(32))
    # OAuth tokens and bot secrets belong in a dedicated secret store, never in this table.


class DiscordGuild(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "discord_guilds"
    __table_args__ = (UniqueConstraint("integration_id", "external_guild_id"),)

    integration_id: Mapped[UUID] = mapped_column(
        ForeignKey("discord_integrations.id", ondelete="CASCADE")
    )
    campaign_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL")
    )
    external_guild_id: Mapped[str] = mapped_column(String(32))
    name: Mapped[str | None] = mapped_column(String(120))


class DiscordChannelMapping(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "discord_channel_mappings"
    __table_args__ = (
        UniqueConstraint("guild_id", "external_channel_id"),
        UniqueConstraint("campaign_id", "purpose"),
    )

    guild_id: Mapped[UUID] = mapped_column(
        ForeignKey("discord_guilds.id", ondelete="CASCADE")
    )
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    external_channel_id: Mapped[str] = mapped_column(String(32))
    purpose: Mapped[str] = mapped_column(String(32))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_session_user_expires", "user_id", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    audience: Mapped[str] = mapped_column(String(16))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AdminBootstrapState(Base):
    __tablename__ = "admin_bootstrap_state"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_admin_bootstrap_singleton"),
        CheckConstraint(
            "completed_at IS NULL OR consumed_at IS NOT NULL",
            name="ck_admin_bootstrap_completion_consumed",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    secret_hash: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    operation_id: Mapped[str | None] = mapped_column(String(36))
    issued_by: Mapped[str | None] = mapped_column(String(128))
    completed_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AdminBootstrapEvent(Base):
    __tablename__ = "admin_bootstrap_events"
    __table_args__ = (
        UniqueConstraint(
            "operation_id",
            "event_type",
            name="uq_admin_bootstrap_event_operation_type",
        ),
        CheckConstraint(
            "event_type IN ('grant_issued', 'admin_created')",
            name="ck_admin_bootstrap_event_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    operation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    admin_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    target_environment: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    __table_args__ = (Index("ix_auth_rate_limit_updated", "updated_at"),)

    bucket_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
