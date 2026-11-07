import asyncio
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.models import (
    Campaign,
    CampaignMember,
    Character,
    CharacterItem,
    CharacterRewardGrant,
    CharacterSkill,
    Item,
    Skill,
    User,
    WalletTransaction,
    WorldReward,
)
from app.schemas.progression import CharacterRewardSpec
from app.services.progression import (
    MAX_CHARACTER_LEVEL,
    MAX_CHARACTER_VALUE,
    apply_character_reward,
    apply_world_reward,
    xp_progress_percent,
    xp_required_for_next_level,
)

CampaignTestClient = tuple[AsyncClient, async_sessionmaker[AsyncSession]]


async def _create_player_campaign(
    client: AsyncClient,
) -> tuple[dict, UUID]:
    registered = await client.post(
        "/api/auth/register",
        json={"username": "ProgressionOwner", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201, registered.text
    response = await client.post(
        "/api/campaigns",
        json={"title": "Progressão", "max_players": 5},
    )
    assert response.status_code == 201, response.text
    campaign = response.json()
    return campaign, UUID(campaign["members"][0]["character_id"])


def _reward(
    *,
    source_type: str = "quest",
    xp: int = 0,
    gold: int = 0,
    items: list[dict] | None = None,
    skill_ids: list[UUID] | None = None,
) -> CharacterRewardSpec:
    return CharacterRewardSpec(
        source_type=source_type,
        xp=xp,
        gold=gold,
        items=items or [],
        skill_ids=skill_ids or [],
    )


async def _create_concurrency_database(
    tmp_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession], UUID, UUID]:
    engine = create_async_engine(
        URL.create(
            "sqlite+aiosqlite",
            database=str(tmp_path / "progression-concurrency.sqlite"),
        )
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    test_session = async_sessionmaker(engine, expire_on_commit=False)

    async with test_session() as session:
        owner = User(
            username="ConcurrentProgression",
            username_key="concurrentprogression",
            password_hash="not-used",
            display_name="Concurrent Progression",
        )
        session.add(owner)
        await session.flush()
        campaign = Campaign(
            owner_id=owner.id,
            title="Concurrent rewards",
            join_code="C" * 32,
            min_players=3,
            max_players=5,
        )
        session.add(campaign)
        await session.flush()
        character = Character(
            owner_id=owner.id,
            campaign_id=campaign.id,
            name="Concurrent character",
        )
        session.add(character)
        await session.flush()
        session.add(
            CampaignMember(
                campaign_id=campaign.id,
                user_id=owner.id,
                character_id=character.id,
                role="owner",
                status="active",
            )
        )
        await session.commit()
        campaign_id = campaign.id
        character_id = character.id
    return engine, test_session, campaign_id, character_id


def test_progression_rules_are_centralized_and_handle_level_cap() -> None:
    assert xp_required_for_next_level(1) == 100
    assert xp_required_for_next_level(4) == 400
    assert xp_required_for_next_level(MAX_CHARACTER_LEVEL) is None
    assert xp_progress_percent(50, 1) == 50
    assert xp_progress_percent(250, 1) == 100
    assert xp_progress_percent(0, MAX_CHARACTER_LEVEL) == 100
    with pytest.raises(ValueError, match="fora dos limites"):
        xp_required_for_next_level(MAX_CHARACTER_LEVEL + 1)


@pytest.mark.parametrize(
    "values",
    [
        {"source_type": "quest", "xp": -1},
        {"source_type": "quest", "gold": -1},
        {"source_type": "quest", "xp": 2_000_000_001},
        {"source_type": "quest"},
        {"source_type": "unsupported", "xp": 10},
    ],
)
def test_reward_spec_rejects_invalid_values(values: dict) -> None:
    with pytest.raises(ValidationError):
        CharacterRewardSpec(**values)


@pytest.mark.anyio
async def test_xp_reward_levels_character_and_persists_sheet_history(
    auth_client: CampaignTestClient,
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _create_player_campaign(client)

    async with test_session() as session:
        result = await apply_character_reward(
            session,
            campaign_id=UUID(campaign["id"]),
            character_id=character_id,
            idempotency_key="quest:initial-victory",
            reward=_reward(xp=100),
        )
        await session.commit()

    assert result.level_before == 1
    assert result.level_after == 2
    assert result.xp_after == 0
    assert result.attribute_points_awarded == 1
    sheet_response = await client.get(f"/api/campaigns/{campaign['id']}/character")
    assert sheet_response.status_code == 200
    sheet = sheet_response.json()
    assert sheet["level"] == 2
    assert sheet["xp"] == 0
    assert sheet["xp_to_next_level"] == 200
    assert sheet["xp_progress_percent"] == 0
    assert sheet["attribute_points"] == 1
    assert sheet["progression_history"][0]["level_after"] == 2
    assert sheet["progression_history"][0]["max_hp_increase"] == 5
    assert sheet["progression_history"][0]["max_mana_increase"] == 2


@pytest.mark.anyio
async def test_experience_carries_over_across_multiple_levels(
    auth_client: CampaignTestClient,
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _create_player_campaign(client)

    async with test_session() as session:
        character = await session.get(Character, character_id)
        assert character is not None
        character.hp = 4
        await session.flush()
        result = await apply_character_reward(
            session,
            campaign_id=UUID(campaign["id"]),
            character_id=character_id,
            idempotency_key="combat:boss-defeated",
            reward=_reward(source_type="combat", xp=750),
        )
        await session.commit()

    assert (result.level_before, result.level_after) == (1, 4)
    assert result.xp_after == 150
    async with test_session() as session:
        character = await session.get(Character, character_id)
        assert character is not None
        assert character.max_hp == 25
        assert character.hp == 19
        assert character.max_mana == 6
        assert character.mana == 6
        assert character.attribute_points == 3


@pytest.mark.anyio
async def test_reward_grants_gold_items_and_skills_once(
    auth_client: CampaignTestClient,
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _create_player_campaign(client)
    async with test_session() as session:
        item = Item(
            name="Poção de teste",
            category="consumable",
            rarity="common",
            is_stackable=True,
            is_active=True,
        )
        skill = Skill(
            name="Escudo de teste",
            category="support",
            status="published",
            is_active=True,
        )
        session.add_all([item, skill])
        await session.flush()
        item_id, skill_id = item.id, skill.id
        reward = _reward(
            source_type="quest",
            gold=25,
            items=[{"item_id": item_id, "quantity": 2}],
            skill_ids=[skill_id],
        )
        first = await apply_character_reward(
            session,
            campaign_id=UUID(campaign["id"]),
            character_id=character_id,
            idempotency_key="quest:reward-cache",
            reward=reward,
        )
        await session.commit()
        replay = await apply_character_reward(
            session,
            campaign_id=UUID(campaign["id"]),
            character_id=character_id,
            idempotency_key="quest:reward-cache",
            reward=reward,
        )
        await session.commit()

        assert first.already_applied is False
        assert replay.already_applied is True
        character = await session.get(Character, character_id)
        assert character is not None
        assert character.gold == 25
        assert await session.scalar(
            select(CharacterItem.quantity).where(
                CharacterItem.character_id == character_id,
                CharacterItem.item_id == item_id,
            )
        ) == 2
        assert await session.scalar(
            select(CharacterSkill.id).where(
                CharacterSkill.character_id == character_id,
                CharacterSkill.skill_id == skill_id,
            )
        ) is not None
        assert await session.scalar(
            select(WalletTransaction.id).where(
                WalletTransaction.character_id == character_id
            )
        ) is not None
        assert await session.scalar(
            select(CharacterRewardGrant.id).where(
                CharacterRewardGrant.character_id == character_id,
                CharacterRewardGrant.idempotency_key == "quest:reward-cache",
            )
        ) is not None


@pytest.mark.anyio
async def test_active_world_reward_uses_the_same_character_progression_service(
    auth_client: CampaignTestClient,
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _create_player_campaign(client)
    async with test_session() as session:
        reward = WorldReward(
            title="Marco da jornada",
            xp=50,
            gold=10,
            item_ids=[],
            is_active=True,
        )
        session.add(reward)
        await session.flush()
        result = await apply_world_reward(
            session,
            campaign_id=UUID(campaign["id"]),
            character_id=character_id,
            idempotency_key=f"world-reward:{reward.id}",
            reward_id=reward.id,
        )
        await session.commit()

    assert result.xp_after == 50
    assert result.gold_awarded == 10


@pytest.mark.anyio
async def test_reward_overflow_is_rejected_without_changing_character(
    auth_client: CampaignTestClient,
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _create_player_campaign(client)
    async with test_session() as session:
        character = await session.get(Character, character_id)
        assert character is not None
        character.gold = MAX_CHARACTER_VALUE
        await session.commit()

        with pytest.raises(HTTPException, match="ouro excede"):
            await apply_character_reward(
                session,
                campaign_id=UUID(campaign["id"]),
                character_id=character_id,
                idempotency_key="quest:gold-overflow",
                reward=_reward(gold=1),
            )
        await session.rollback()
        character = await session.get(Character, character_id)
        assert character is not None
        assert character.gold == MAX_CHARACTER_VALUE
        assert await session.scalar(
            select(CharacterRewardGrant.id).where(
                CharacterRewardGrant.character_id == character_id
            )
        ) is None


@pytest.mark.anyio
async def test_reused_idempotency_key_with_different_reward_is_rejected(
    auth_client: CampaignTestClient,
) -> None:
    _, test_session = auth_client
    client, _ = auth_client
    campaign, character_id = await _create_player_campaign(client)
    async with test_session() as session:
        await apply_character_reward(
            session,
            campaign_id=UUID(campaign["id"]),
            character_id=character_id,
            idempotency_key="quest:conflict",
            reward=_reward(xp=10),
        )
        await session.commit()
        with pytest.raises(HTTPException, match="chave desta recompensa"):
            await apply_character_reward(
                session,
                campaign_id=UUID(campaign["id"]),
                character_id=character_id,
                idempotency_key="quest:conflict",
                reward=_reward(xp=20),
            )
        await session.rollback()


@pytest.mark.anyio
async def test_campaign_mismatch_and_player_payload_cannot_change_progression(
    auth_client: CampaignTestClient,
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _create_player_campaign(client)
    other_campaign_response = await client.post(
        "/api/campaigns",
        json={"title": "Outra campanha", "max_players": 5},
    )
    assert other_campaign_response.status_code == 201
    other_campaign_id = UUID(other_campaign_response.json()["id"])

    async with test_session() as session:
        with pytest.raises(HTTPException, match="Personagem não encontrado"):
            await apply_character_reward(
                session,
                campaign_id=other_campaign_id,
                character_id=character_id,
                idempotency_key="quest:wrong-campaign",
                reward=_reward(xp=100),
            )
        await session.rollback()

    response = await client.post(
        f"/api/campaigns/{campaign['id']}/character",
        json={"name": "Elarion", "xp": 2_000_000, "level": 99},
    )
    assert response.status_code == 422
    async with test_session() as session:
        character = await session.get(Character, character_id)
        assert character is not None
        assert (character.xp, character.level) == (0, 1)


@pytest.mark.anyio
async def test_reward_requires_a_valid_campaign_member_link(
    auth_client: CampaignTestClient,
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _create_player_campaign(client)
    campaign_id = UUID(campaign["id"])
    async with test_session() as session:
        member = await session.scalar(
            select(CampaignMember).where(
                CampaignMember.campaign_id == campaign_id,
                CampaignMember.character_id == character_id,
            )
        )
        assert member is not None
        await session.delete(member)
        await session.commit()

        with pytest.raises(HTTPException, match="não está vinculado"):
            await apply_character_reward(
                session,
                campaign_id=campaign_id,
                character_id=character_id,
                idempotency_key="quest:missing-campaign-link",
                reward=_reward(xp=100),
            )
        await session.rollback()
        character = await session.get(Character, character_id)
        assert character is not None
        assert (character.level, character.xp) == (1, 0)
        assert await session.scalar(
            select(CharacterRewardGrant.id).where(
                CharacterRewardGrant.character_id == character_id
            )
        ) is None


@pytest.mark.anyio
async def test_concurrent_duplicate_reward_is_applied_once(
    tmp_path: Path,
) -> None:
    engine, test_session, campaign_id, character_id = (
        await _create_concurrency_database(tmp_path)
    )

    async def award():
        async with test_session() as session:
            result = await apply_character_reward(
                session,
                campaign_id=campaign_id,
                character_id=character_id,
                idempotency_key="quest:concurrent",
                reward=_reward(xp=100),
            )
            await session.commit()
            return result

    results = await asyncio.gather(award(), award())

    assert sorted(result.already_applied for result in results) == [False, True]
    async with test_session() as session:
        character = await session.get(Character, character_id)
        assert character is not None
        assert (character.level, character.xp) == (2, 0)
        assert await session.scalar(
            select(CharacterRewardGrant.id).where(
                CharacterRewardGrant.character_id == character_id,
                CharacterRewardGrant.idempotency_key == "quest:concurrent",
            )
        ) is not None
    await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_distinct_rewards_preserve_both_xp_awards(
    tmp_path: Path,
) -> None:
    engine, test_session, campaign_id, character_id = (
        await _create_concurrency_database(tmp_path)
    )
    first_reward_applied = asyncio.Event()
    allow_first_commit = asyncio.Event()
    second_reward_started = asyncio.Event()

    async def award_first():
        async with test_session() as session:
            result = await apply_character_reward(
                session,
                campaign_id=campaign_id,
                character_id=character_id,
                idempotency_key="quest:concurrent-a",
                reward=_reward(xp=100),
            )
            first_reward_applied.set()
            await allow_first_commit.wait()
            await session.commit()
            return result

    async def award_second():
        await first_reward_applied.wait()
        second_reward_started.set()
        async with test_session() as session:
            result = await apply_character_reward(
                session,
                campaign_id=campaign_id,
                character_id=character_id,
                idempotency_key="quest:concurrent-b",
                reward=_reward(xp=100),
            )
            await session.commit()
            return result

    first_task = asyncio.create_task(award_first())
    await first_reward_applied.wait()
    second_task = asyncio.create_task(award_second())
    try:
        await second_reward_started.wait()
        await asyncio.sleep(0.05)
        assert not second_task.done()
    finally:
        allow_first_commit.set()
    await asyncio.gather(first_task, second_task)

    async with test_session() as session:
        character = await session.get(Character, character_id)
        assert character is not None
        assert (character.level, character.xp) == (2, 100)
        assert await session.scalar(
            select(CharacterRewardGrant.id).where(
                CharacterRewardGrant.character_id == character_id
            )
        ) is not None
    await engine.dispose()
