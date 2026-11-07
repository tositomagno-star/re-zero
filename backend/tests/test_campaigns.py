import asyncio
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import ANY
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import dependencies as api_dependencies
from app.db.session import get_db
from app.main import app
from app.services import campaigns as campaigns_service
from app.models import (
    Campaign,
    CampaignMember,
    Character,
    CharacterItem,
    CharacterQuest,
    CharacterSkill,
    Chapter,
    GameEvent,
    GameSession,
    Item,
    Quest,
    Skill,
    StoryChoice,
    StoryNode,
    User,
)

CampaignTestClient = tuple[AsyncClient, async_sessionmaker[AsyncSession]]


def test_default_character_name_preserves_prefix_and_character_limit() -> None:
    assert campaigns_service._default_character_name(
        "Elarion"
    ) == "Personagem de Elarion"

    long_name = campaigns_service._default_character_name("A" * 100)

    assert long_name == f"Personagem de {'A' * 86}"
    assert len(long_name) == 100


def test_join_codes_have_at_least_128_bits_and_do_not_collide_in_sample() -> None:
    codes = [campaigns_service._new_join_code() for _ in range(1000)]

    assert all(re.fullmatch(r"[0-9A-F]{32}", code) for code in codes)
    assert len(set(codes)) == len(codes)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("campaign_count", "active_members_per_campaign"),
    [(0, 1), (1, 1), (3, 2), (3, 5)],
)
async def test_campaign_summaries_use_constant_query_count(
    auth_client: CampaignTestClient,
    campaign_count: int,
    active_members_per_campaign: int,
) -> None:
    _, test_session = auth_client
    async with test_session() as session:
        viewer = User(
            username="SummaryViewer",
            username_key="summaryviewer",
            password_hash="not-used",
            display_name="Summary Viewer",
        )
        session.add(viewer)
        await session.flush()
        viewer_id = viewer.id

        for campaign_index in range(campaign_count):
            owner = viewer
            if campaign_index:
                owner = User(
                    username=f"SummaryOwner{campaign_index}",
                    username_key=f"summaryowner{campaign_index}",
                    password_hash="not-used",
                    display_name=f"Summary Owner {campaign_index}",
                )
                session.add(owner)
                await session.flush()
            campaign = Campaign(
                owner_id=owner.id,
                title=f"Summary Campaign {campaign_index}",
                join_code=f"{campaign_index:032X}",
                max_players=5,
            )
            session.add(campaign)
            await session.flush()

            active_users = [owner] if owner is viewer else [owner, viewer]
            for member_index in range(active_members_per_campaign - len(active_users)):
                member_user = User(
                    username=f"SummaryPlayer{campaign_index}{member_index}",
                    username_key=f"summaryplayer{campaign_index}{member_index}",
                    password_hash="not-used",
                    display_name=f"Summary Player {campaign_index}-{member_index}",
                )
                session.add(member_user)
                await session.flush()
                active_users.append(member_user)
            session.add_all(
                [
                    CampaignMember(
                        campaign_id=campaign.id,
                        user_id=member_user.id,
                        role="owner" if member_user is owner else "player",
                        status="active",
                    )
                    for member_user in active_users
                ]
            )

        await session.commit()

    async with test_session() as session:
        viewer = await session.get(User, viewer_id)
        assert viewer is not None
        query_count = 0

        def count_query(*_: object) -> None:
            nonlocal query_count
            query_count += 1

        engine = session.bind
        assert engine is not None
        event.listen(engine.sync_engine, "before_cursor_execute", count_query)
        try:
            summaries = await campaigns_service._campaign_summaries(session, viewer)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", count_query)

    assert len(summaries) == campaign_count
    assert [summary.participant_count for summary in summaries] == [
        active_members_per_campaign
    ] * campaign_count
    assert [summary.available_slots for summary in summaries] == [
        max(5 - active_members_per_campaign, 0)
    ] * campaign_count
    assert [summary.membership_status for summary in summaries] == [
        "active"
    ] * campaign_count
    assert sum(summary.is_owner for summary in summaries) == int(campaign_count > 0)
    expected_queries = 1 if campaign_count == 0 else 2
    assert query_count == expected_queries


@pytest.mark.anyio
@pytest.mark.parametrize("member_count", [0, 1, 5])
async def test_member_response_projection_uses_one_joined_query(
    auth_client: CampaignTestClient,
    member_count: int,
) -> None:
    _, test_session = auth_client
    async with test_session() as session:
        owner = User(
            username="MemberProjectionOwner",
            username_key="memberprojectionowner",
            password_hash="not-used",
            display_name="Member Projection Owner",
        )
        session.add(owner)
        await session.flush()
        campaign = Campaign(
            owner_id=owner.id,
            title="Member Projection",
            join_code="RZ-99991",
            max_players=5,
        )
        session.add(campaign)
        await session.flush()
        campaign_id = campaign.id

        members: list[CampaignMember] = []
        for index in range(member_count):
            user = User(
                username=f"ProjectionPlayer{index}",
                username_key=f"projectionplayer{index}",
                password_hash="not-used",
                display_name=f"Projection Player {index}",
            )
            session.add(user)
            await session.flush()
            members.append(
                CampaignMember(
                    campaign_id=campaign.id,
                    user_id=user.id,
                    role="player",
                    status="active",
                )
            )
        session.add_all(members)
        await session.commit()

    async with test_session() as session:
        query_count = 0

        def count_query(*_: object) -> None:
            nonlocal query_count
            query_count += 1

        engine = session.bind
        assert engine is not None
        event.listen(engine.sync_engine, "before_cursor_execute", count_query)
        try:
            responses = await campaigns_service._member_responses(session, campaign_id)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", count_query)

    assert len(responses) == member_count
    assert {response.username for response in responses} == {
        f"ProjectionPlayer{index}" for index in range(member_count)
    }
    assert all(response.character_id is None for response in responses)
    assert query_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize("member_count", [1, 5])
async def test_campaign_response_query_count_does_not_grow_with_members(
    auth_client: CampaignTestClient,
    member_count: int,
) -> None:
    _, test_session = auth_client
    async with test_session() as session:
        owner = User(
            username="CampaignResponseOwner",
            username_key="campaignresponseowner",
            password_hash="not-used",
            display_name="Campaign Response Owner",
        )
        viewer = User(
            username="CampaignResponseViewer",
            username_key="campaignresponseviewer",
            password_hash="not-used",
            display_name="Campaign Response Viewer",
        )
        session.add_all([owner, viewer])
        await session.flush()
        campaign = Campaign(
            owner_id=owner.id,
            title="Campaign Response",
            join_code="RZ-99992",
            max_players=5,
        )
        session.add(campaign)
        await session.flush()
        campaign_id = campaign.id
        viewer_id = viewer.id
        members = [
            CampaignMember(
                campaign_id=campaign.id,
                user_id=viewer.id,
                role="player",
                status="active",
            )
        ]
        for index in range(member_count - 1):
            user = User(
                username=f"CampaignResponsePlayer{index}",
                username_key=f"campaignresponseplayer{index}",
                password_hash="not-used",
                display_name=f"Campaign Response Player {index}",
            )
            session.add(user)
            await session.flush()
            members.append(
                CampaignMember(
                    campaign_id=campaign.id,
                    user_id=user.id,
                    role="player",
                    status="active",
                )
            )
        session.add_all(members)
        await session.commit()

    async with test_session() as session:
        campaign = await session.get(Campaign, campaign_id)
        viewer = await session.get(User, viewer_id)
        member = await session.scalar(
            select(CampaignMember).where(
                CampaignMember.campaign_id == campaign_id,
                CampaignMember.user_id == viewer_id,
            )
        )
        assert campaign is not None
        assert viewer is not None
        assert member is not None
        query_count = 0

        def count_query(*_: object) -> None:
            nonlocal query_count
            query_count += 1

        engine = session.bind
        assert engine is not None
        event.listen(engine.sync_engine, "before_cursor_execute", count_query)
        try:
            response = await campaigns_service._campaign_response(
                session,
                campaign,
                viewer,
                member,
            )
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", count_query)

    assert response.participant_count == member_count
    assert len(response.members) == member_count
    assert query_count == 4


async def _new_player_client(
    username: str,
    *,
    client_host: str = "127.0.0.1",
) -> AsyncClient:
    client = AsyncClient(
        transport=ASGITransport(app=app, client=(client_host, 12345)),
        base_url="http://testserver",
    )
    response = await client.post(
        "/api/auth/register",
        json={"username": username, "password": "strong-player-password-2026"},
    )
    assert response.status_code == 201
    return client


async def _create_campaign(client: AsyncClient, *, max_players: int = 5) -> dict:
    response = await client.post(
        "/api/campaigns",
        json={
            "title": "A Vigília de Cinzas",
            "description": "Uma campanha persistente.",
            "max_players": max_players,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.anyio
async def test_create_solo_campaign_starts_with_one_player(auth_client) -> None:
    client, test_session = auth_client
    register = await client.post(
        "/api/auth/register",
        json={"username": "SoloPlayerTest", "password": "strong-player-password-2026"},
    )
    assert register.status_code == 201
    response = await client.post(
        "/api/campaigns",
        json={
            "title": "Crônicas Solo",
            "description": "Campanha individual persistente.",
            "solo": True,
            "difficulty": "legendary",
        },
    )
    assert response.status_code == 201, response.text
    campaign = response.json()
    assert campaign["min_players"] == 1
    assert campaign["max_players"] == 1
    async with test_session() as session:
        stored = await session.get(Campaign, UUID(campaign["id"]))
        assert stored is not None
        assert stored.settings["difficulty"] == "legendary"


@pytest.mark.anyio
async def test_solo_campaign_supports_multiple_persistent_characters(auth_client) -> None:
    client, test_session = auth_client
    registered = await client.post(
        "/api/auth/register",
        json={"username": "SoloRoster", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    created = await client.post(
        "/api/campaigns",
        json={"title": "Aventura com elenco", "solo": True},
    )
    assert created.status_code == 201
    campaign_id = created.json()["id"]

    initial = await client.get(f"/api/campaigns/{campaign_id}/characters")
    assert initial.status_code == 200
    assert len(initial.json()) == 1
    assert initial.json()[0]["active"] is True

    second = await client.post(
        f"/api/campaigns/{campaign_id}/characters",
        json={"name": "Guardião"},
    )
    assert second.status_code == 201
    second_character_id = second.json()["id"]
    assert second.json()["active"] is False

    selected = await client.put(
        f"/api/campaigns/{campaign_id}/characters/{second_character_id}/active",
        json={},
    )
    assert selected.status_code == 200
    assert selected.json()["active"] is True

    roster = await client.get(f"/api/campaigns/{campaign_id}/characters")
    assert roster.status_code == 200
    assert len(roster.json()) == 2
    assert [character["name"] for character in roster.json() if character["active"]] == [
        "Guardião"
    ]
    async with test_session() as session:
        member = await session.scalar(
            select(CampaignMember).where(
                CampaignMember.campaign_id == UUID(campaign_id),
            )
        )
        assert member is not None
        assert str(member.character_id) == second_character_id


@pytest.mark.anyio
async def test_solo_campaign_can_pause_and_resume(auth_client) -> None:
    client, test_session = auth_client
    registered = await client.post(
        "/api/auth/register",
        json={"username": "SoloPauseTest", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    created = await client.post(
        "/api/campaigns",
        json={"title": "Aventura pausável", "solo": True},
    )
    assert created.status_code == 201
    campaign_id = UUID(created.json()["id"])
    async with test_session() as session:
        campaign = await session.get(Campaign, campaign_id)
        assert campaign is not None
        campaign.status = "in_progress"
        await session.commit()

    paused = await client.post(f"/api/campaigns/{campaign_id}/pause")
    assert paused.status_code == 200, paused.text
    assert paused.json()["status"] == "paused"
    resumed = await client.post(f"/api/campaigns/{campaign_id}/resume")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "in_progress"


@pytest.mark.anyio
async def test_player_character_sheet_returns_persisted_character_and_related_data(
    auth_client: CampaignTestClient,
) -> None:
    client, test_session = auth_client
    registered = await client.post(
        "/api/auth/register",
        json={"username": "SheetOwner", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    campaign = await _create_campaign(client)
    character_id = UUID(campaign["members"][0]["character_id"])
    async with test_session() as session:
        character = await session.get(Character, character_id)
        assert character is not None
        character.name = "Elarion"
        character.description = "Guardião das antigas ruínas."
        character.character_class = "Sentinela"
        character.ancestry = "Elfo"
        character.level = 4
        character.xp = 275
        character.gold = 83
        character.hp = 18
        character.max_hp = 24
        character.mana = 7
        character.max_mana = 12
        character.attributes = {"forca": 8, "vitalidade": 11}
        item = Item(
            name="Espada de treino",
            description="Uma lâmina simples.",
            category="weapon",
            rarity="common",
            weight=3,
            effects={"attack": 2},
        )
        skill = Skill(
            name="Barreira",
            category="support",
            description="Protege o grupo.",
            mana_cost=2,
            effects={"defense": 1},
            target="ally",
            cooldown_seconds=10,
        )
        quest = Quest(
            campaign_id=UUID(campaign["id"]),
            title="Ruínas antigas",
            description="Investigue o santuário.",
            status="active",
        )
        session.add_all([item, skill, quest])
        await session.flush()
        session.add_all(
            [
                CharacterItem(
                    character_id=character_id,
                    item_id=item.id,
                    quantity=2,
                    is_equipped=True,
                    slot="main_hand",
                ),
                CharacterSkill(character_id=character_id, skill_id=skill.id),
                CharacterQuest(
                    character_id=character_id,
                    quest_id=quest.id,
                    status="in_progress",
                    progress={"clues_found": 2},
                ),
            ]
        )
        await session.commit()

    response = await client.get(f"/api/campaigns/{campaign['id']}/character")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Elarion",
        "description": "Guardião das antigas ruínas.",
        "character_class": "Sentinela",
        "ancestry": "Elfo",
        "level": 4,
        "xp": 275,
        "xp_to_next_level": 400,
        "xp_progress_percent": 68,
        "attribute_points": 0,
        "gold": 83,
        "hp": 18,
        "max_hp": 24,
        "mana": 7,
        "max_mana": 12,
        "attributes": {"forca": 8, "vitalidade": 11},
        "attribute_resolution": ANY,
        "inventory": [
            {
                "item_id": str(item.id),
                "name": "Espada de treino",
                "description": "Uma lâmina simples.",
                "category": "weapon",
                "is_career": False,
                "rarity": "common",
                "image_url": None,
                "weight": 3,
                "effects": {"attack": 2},
                "quantity": 2,
                "is_equipped": True,
                "slot": "main_hand",
                "origin": {},
            }
        ],
        "skills": [
            {
                "id": str(skill.id),
                "name": "Barreira",
                "category": "support",
                "description": "Protege o grupo.",
                "mana_cost": 2,
                "effects": {"defense": 1},
                "target": "ally",
                "cooldown_seconds": 10,
                "origin": {},
            }
        ],
        "quests": [
            {
                "id": str(quest.id),
                "title": "Ruínas antigas",
                "description": "Investigue o santuário.",
                "status": "in_progress",
                "progress": {"clues_found": 2},
                "objectives": [],
                "rewards": {"xp": 0, "gold": 0, "items": [], "skill_ids": []},
            }
        ],
        "progression_history": [],
    }


@pytest.mark.anyio
async def test_player_character_sheet_returns_empty_related_collections(
    auth_client: CampaignTestClient,
) -> None:
    client, _ = auth_client
    registered = await client.post(
        "/api/auth/register",
        json={"username": "EmptySheetOwner", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    campaign = await _create_campaign(client)

    response = await client.get(f"/api/campaigns/{campaign['id']}/character")

    assert response.status_code == 200
    assert response.json()["inventory"] == []
    assert response.json()["skills"] == []
    assert response.json()["quests"] == []


@pytest.mark.anyio
async def test_player_lists_and_accepts_published_campaign_quests_persistently(
    auth_client: CampaignTestClient,
) -> None:
    client, test_session = auth_client
    registered = await client.post(
        "/api/auth/register",
        json={"username": "QuestPlayer", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    campaign = await _create_campaign(client)
    character_id = UUID(campaign["members"][0]["character_id"])
    quest_id = UUID(int=456)
    async with test_session() as session:
        session.add(
            Quest(
                id=quest_id,
                campaign_id=UUID(campaign["id"]),
                title="A chave esquecida",
                description="Encontre a chave.",
                status="published",
                conditions={
                    "objectives": [
                        {
                            "id": "find-key",
                            "title": "Encontrar a chave",
                            "description": "Investigue a biblioteca.",
                            "target": 1,
                        }
                    ],
                    "require_all_objectives": True,
                },
                rewards={"xp": 50, "gold": 10, "items": [], "skill_ids": []},
            )
        )
        await session.commit()

    listed = await client.get(f"/api/campaigns/{campaign['id']}/quests")
    assert listed.status_code == 200
    assert listed.json() == [
        {
            "id": str(quest_id),
            "title": "A chave esquecida",
            "description": "Encontre a chave.",
            "status": "available",
            "progress": {},
            "objectives": [
                {
                    "id": "find-key",
                    "title": "Encontrar a chave",
                    "description": "Investigue a biblioteca.",
                    "target": 1,
                }
            ],
            "rewards": {"xp": 50, "gold": 10, "items": [], "skill_ids": []},
        }
    ]
    accepted = await client.post(
        f"/api/campaigns/{campaign['id']}/quests/{quest_id}/accept"
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "in_progress"
    assert accepted.json()["progress"]["objectives"] == {}
    async with test_session() as session:
        quest = await session.get(Quest, quest_id)
        assert quest is not None
        quest.status = "inactive"
        await session.commit()
    reloaded = await client.get(f"/api/campaigns/{campaign['id']}/quests")
    assert reloaded.status_code == 200
    assert reloaded.json()[0]["status"] == "in_progress"
    sheet = await client.get(f"/api/campaigns/{campaign['id']}/character")
    assert sheet.status_code == 200
    assert sheet.json()["quests"][0]["id"] == str(quest_id)
    assert sheet.json()["quests"][0]["status"] == "in_progress"
    assert sheet.json()["quests"][0]["objectives"][0]["id"] == "find-key"
    async with test_session() as session:
        assignment = await session.scalar(
            select(CharacterQuest).where(
                CharacterQuest.character_id == character_id,
                CharacterQuest.quest_id == quest_id,
            )
        )
        assert assignment is not None
        assert assignment.status == "in_progress"
        assert assignment.progress["reward_snapshot"]["xp"] == 50


@pytest.mark.anyio
async def test_player_character_sheet_requires_active_membership_and_exact_character_link(
    auth_client: CampaignTestClient,
) -> None:
    client, test_session = auth_client
    registered = await client.post(
        "/api/auth/register",
        json={"username": "SheetAccessOwner", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    campaign = await _create_campaign(client)
    own_character_id = campaign["members"][0]["character_id"]
    outsider = await _new_player_client("SheetOutsider")

    outsider_response = await outsider.get(
        f"/api/campaigns/{campaign['id']}/character"
    )
    anonymous = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )
    anonymous_response = await anonymous.get(
        f"/api/campaigns/{campaign['id']}/character"
    )
    other_character_id = None
    other_campaign_character_id = None
    async with test_session() as session:
        owner = await session.scalar(
            select(User).where(User.username_key == "sheetaccessowner")
        )
        assert owner is not None
        foreign_user = User(
            username="SheetForeign",
            username_key="sheetforeign",
            password_hash="not-used",
            display_name="Foreign Player",
        )
        session.add(foreign_user)
        await session.flush()
        foreign_character = Character(
            owner_id=foreign_user.id,
            campaign_id=UUID(campaign["id"]),
            name="Outro jogador",
        )
        other_campaign_character = Character(
            owner_id=owner.id,
            campaign_id=None,
            name="Outra campanha",
        )
        other_campaign = Campaign(
            owner_id=owner.id,
            title="Outra campanha",
            join_code="F" * 32,
        )
        session.add(other_campaign)
        await session.flush()
        other_campaign_character.campaign_id = other_campaign.id
        session.add_all([foreign_character, other_campaign_character])
        await session.flush()
        other_character_id = foreign_character.id
        other_campaign_character_id = other_campaign_character.id
        member = await session.scalar(
            select(CampaignMember).where(
                CampaignMember.campaign_id == UUID(campaign["id"]),
                CampaignMember.user_id == owner.id,
            )
        )
        assert member is not None
        member.character_id = foreign_character.id
        await session.commit()

    foreign_character_response = await client.get(
        f"/api/campaigns/{campaign['id']}/character"
    )
    async with test_session() as session:
        member = await session.scalar(
            select(CampaignMember).where(
                CampaignMember.campaign_id == UUID(campaign["id"]),
                CampaignMember.user_id == UUID(registered.json()["id"]),
            )
        )
        assert member is not None
        member.character_id = other_campaign_character_id
        await session.commit()
    foreign_campaign_response = await client.get(
        f"/api/campaigns/{campaign['id']}/character"
    )
    without_character_id = await client.get(
        f"/api/campaigns/{campaign['id']}/character?character_id={other_character_id}"
    )
    async with test_session() as session:
        member = await session.scalar(
            select(CampaignMember).where(
                CampaignMember.campaign_id == UUID(campaign["id"]),
                CampaignMember.user_id == UUID(registered.json()["id"]),
            )
        )
        assert member is not None
        member.character_id = UUID(own_character_id)
        await session.commit()

    assert outsider_response.status_code == 404
    assert anonymous_response.status_code == 401
    assert foreign_character_response.status_code == 404
    assert foreign_campaign_response.status_code == 404
    assert without_character_id.status_code == 404
    assert (await client.get(f"/api/campaigns/{campaign['id']}")).status_code == 200
    assert (
        await client.post(
            f"/api/campaigns/{campaign['id']}/character",
            json={"name": "Novo"},
        )
    ).status_code == 200

    await anonymous.aclose()
    await outsider.aclose()


@pytest.mark.anyio
async def test_create_campaign_generates_unique_code_and_lists_owner_campaigns(
    auth_client: CampaignTestClient,
) -> None:
    client, test_session = auth_client
    first_user = await client.post(
        "/api/auth/register",
        json={"username": "CampaignOwner", "password": "strong-player-password-2026"},
    )
    assert first_user.status_code == 201
    first = await _create_campaign(client)
    second = await _create_campaign(client)
    listed = await client.get("/api/campaigns")

    assert re.fullmatch(r"[0-9A-F]{32}", first["join_code"])
    assert first["join_code"] != second["join_code"]
    assert first["status"] == "waiting"
    assert first["participant_count"] == 1
    assert first["members"][0]["role"] == "owner"
    assert first["members"][0]["character_name"]
    assert [entry["id"] for entry in listed.json()] == [second["id"], first["id"]]

    async with test_session() as session:
        stored = await session.get(Campaign, UUID(first["id"]))
        owner_member = await session.scalar(
            select(CampaignMember).where(CampaignMember.campaign_id == UUID(first["id"]))
        )
        character = await session.get(Character, owner_member.character_id)
        assert stored is not None
        assert stored.join_code == first["join_code"]
        assert stored.last_activity_at is not None
        assert character is not None
        assert str(character.owner_id) == first_user.json()["id"]


@pytest.mark.anyio
async def test_campaign_capacity_supports_seven_players_and_rejects_eight(
    auth_client: CampaignTestClient,
) -> None:
    client, _ = auth_client
    registered = await client.post(
        "/api/auth/register",
        json={"username": "SevenPlayerOwner", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201

    campaign = await _create_campaign(client, max_players=7)
    too_many_players = await client.post(
        "/api/campaigns",
        json={"title": "Grupo grande demais", "max_players": 8},
    )

    assert campaign["max_players"] == 7
    assert too_many_players.status_code == 422


@pytest.mark.anyio
async def test_seven_players_can_join_one_campaign(auth_client: CampaignTestClient) -> None:
    owner_client, _ = auth_client
    registered = await owner_client.post(
        "/api/auth/register",
        json={"username": "SevenMemberOwner", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    campaign = await _create_campaign(owner_client, max_players=7)
    clients = [
        await _new_player_client(
            f"SevenMember{index}",
            client_host=f"192.0.2.{index + 1}",
        )
        for index in range(7)
    ]

    try:
        responses = [
            await client.post(
                "/api/campaigns/join",
                json={"code": campaign["join_code"]},
            )
            for client in clients
        ]
        lobby = await owner_client.get(f"/api/campaigns/{campaign['id']}")

        assert [response.status_code for response in responses].count(201) == 6
        assert responses[6].status_code == 409
        assert lobby.status_code == 200
        assert lobby.json()["participant_count"] == 7
        assert lobby.json()["available_slots"] == 0
    finally:
        await asyncio.gather(*(client.aclose() for client in clients))


@pytest.mark.anyio
async def test_member_response_preserves_order_and_presence_timeout(
    auth_client: CampaignTestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_client, test_session = auth_client
    registered = await owner_client.post(
        "/api/auth/register",
        json={"username": "PresenceWindowOwner", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    campaign = await _create_campaign(owner_client)
    player_client = await _new_player_client("PresenceWindowPlayer")
    joined = await player_client.post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"]},
    )
    assert joined.status_code == 201

    fixed_now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(campaigns_service, "_now", lambda: fixed_now)
    player_user_id = (await player_client.get("/api/auth/session")).json()["id"]
    async with test_session() as session:
        owner_member = await session.scalar(
            select(CampaignMember).where(
                CampaignMember.campaign_id == UUID(campaign["id"]),
                CampaignMember.user_id == UUID(registered.json()["id"]),
            )
        )
        player_member = await session.scalar(
            select(CampaignMember).where(
                CampaignMember.campaign_id == UUID(campaign["id"]),
                CampaignMember.user_id == UUID(player_user_id),
            )
        )
        assert owner_member is not None and player_member is not None
        owner_member.created_at = fixed_now - timedelta(minutes=2)
        player_member.created_at = fixed_now - timedelta(minutes=1)
        owner_member.last_seen_at = fixed_now - timedelta(seconds=45)
        player_member.last_seen_at = fixed_now - timedelta(
            seconds=45,
            microseconds=1,
        )
        await session.commit()

    response = await owner_client.get(f"/api/campaigns/{campaign['id']}")

    assert response.status_code == 200
    members = response.json()["members"]
    assert [member["username"] for member in members] == [
        "PresenceWindowOwner",
        "PresenceWindowPlayer",
    ]
    assert [member["is_connected"] for member in members] == [True, False]
    await player_client.aclose()


@pytest.mark.anyio
async def test_three_player_lobby_syncs_readiness_presence_leave_and_rejoin(
    auth_client: CampaignTestClient,
) -> None:
    owner_client, _ = auth_client
    registered = await owner_client.post(
        "/api/auth/register",
        json={"username": "SyncLobbyOwner", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    campaign = await _create_campaign(owner_client, max_players=3)
    first_client = await _new_player_client("SyncLobbyFirst")
    second_client = await _new_player_client("SyncLobbySecond")
    for client in (first_client, second_client):
        joined = await client.post(
            "/api/campaigns/join",
            json={"code": campaign["join_code"]},
        )
        assert joined.status_code == 201

    first_ready, second_ready = await asyncio.gather(
        first_client.post(
            f"/api/campaigns/{campaign['id']}/ready",
            json={"is_ready": True},
        ),
        second_client.post(
            f"/api/campaigns/{campaign['id']}/ready",
            json={"is_ready": True},
        ),
    )
    duplicate_ready = await first_client.post(
        f"/api/campaigns/{campaign['id']}/ready",
        json={"is_ready": True},
    )
    first_presence = await first_client.post(
        f"/api/campaigns/{campaign['id']}/presence",
        json={},
    )
    shared_lobby = await owner_client.get(f"/api/campaigns/{campaign['id']}")

    assert first_ready.status_code == second_ready.status_code == 200
    assert duplicate_ready.status_code == 200
    assert first_presence.status_code == 204
    assert shared_lobby.status_code == 200
    assert shared_lobby.json()["participant_count"] == 3
    members = {member["username"]: member for member in shared_lobby.json()["members"]}
    assert members["SyncLobbyFirst"]["is_ready"] is True
    assert members["SyncLobbySecond"]["is_ready"] is True
    assert members["SyncLobbyFirst"]["is_connected"] is True
    assert members["SyncLobbySecond"]["is_connected"] is True

    left = await second_client.post(f"/api/campaigns/{campaign['id']}/leave")
    after_leave = await owner_client.get(f"/api/campaigns/{campaign['id']}")
    inactive_access = await second_client.get(f"/api/campaigns/{campaign['id']}")

    assert left.status_code == 204
    assert after_leave.status_code == 200
    assert after_leave.json()["participant_count"] == 2
    assert {
        member["username"] for member in after_leave.json()["members"]
    } == {"SyncLobbyOwner", "SyncLobbyFirst"}
    repeated_lobby = await owner_client.get(f"/api/campaigns/{campaign['id']}")
    assert [member["user_id"] for member in repeated_lobby.json()["members"]] == [
        member["user_id"] for member in after_leave.json()["members"]
    ]
    assert inactive_access.status_code == 404

    rejoined = await second_client.post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"]},
    )
    assert rejoined.status_code == 200
    assert rejoined.json()["participant_count"] == 3
    assert next(
        member for member in rejoined.json()["members"] if member["username"] == "SyncLobbySecond"
    )["is_ready"] is False

    await first_client.aclose()
    await second_client.aclose()


@pytest.mark.anyio
async def test_join_accepts_new_and_legacy_codes_and_rejects_invalid_codes(
    auth_client: CampaignTestClient,
) -> None:
    owner_client, test_session = auth_client
    registered = await owner_client.post(
        "/api/auth/register",
        json={"username": "InviteOwner", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201

    new_campaign = await _create_campaign(owner_client)
    assert re.fullmatch(r"[0-9A-F]{32}", new_campaign["join_code"])
    new_player = await _new_player_client("NewCodePlayer")
    new_join = await new_player.post(
        "/api/campaigns/join",
        json={"code": new_campaign["join_code"].lower()},
    )
    assert new_join.status_code == 201

    legacy_campaign = await _create_campaign(owner_client)
    async with test_session() as session:
        stored_campaign = await session.get(Campaign, UUID(legacy_campaign["id"]))
        assert stored_campaign is not None
        stored_campaign.join_code = "RZ-48291"
        await session.commit()

    legacy_player = await _new_player_client("LegacyCodePlayer")
    legacy_join = await legacy_player.post(
        "/api/campaigns/join",
        json={"code": "rz-48291"},
    )
    invalid_format = await legacy_player.post(
        "/api/campaigns/join",
        json={"code": "not-a-code"},
    )
    invalid_code = await legacy_player.post(
        "/api/campaigns/join",
        json={"code": "RZ-00000"},
    )

    assert legacy_join.status_code == 201
    assert invalid_format.status_code == 422
    assert invalid_code.status_code == 404

    await new_player.aclose()
    await legacy_player.aclose()


@pytest.mark.anyio
async def test_invalid_campaign_codes_remain_rate_limited(
    auth_client: CampaignTestClient,
) -> None:
    owner_client, _ = auth_client
    registered = await owner_client.post(
        "/api/auth/register",
        json={"username": "JoinLimitOwner", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    player_client = await _new_player_client(
        "JoinLimitPlayer",
        client_host="192.0.2.1",
    )

    responses = [
        await player_client.post(
            "/api/campaigns/join",
            json={"code": "RZ-00000"},
        )
        for _ in range(5)
    ]
    blocked = await player_client.post(
        "/api/campaigns/join",
        json={"code": "RZ-00000"},
    )

    assert all(response.status_code == 404 for response in responses)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    await player_client.aclose()


@pytest.mark.anyio
async def test_campaign_creation_rejects_disallowed_origin_without_creating_campaign(
    auth_client: CampaignTestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = auth_client
    registered = await client.post(
        "/api/auth/register",
        json={"username": "OriginCampaignOwner", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    monkeypatch.setattr(
        api_dependencies,
        "get_settings",
        lambda: SimpleNamespace(frontend_origins=["https://trusted.example"]),
    )

    response = await client.post(
        "/api/campaigns",
        json={"title": "Origem não autorizada", "max_players": 3},
        headers={"Origin": "https://untrusted.example"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Origem da solicitação não autorizada."}
    assert (await client.get("/api/campaigns")).json() == []


@pytest.mark.anyio
@pytest.mark.postgres
async def test_join_code_invalid_duplicate_and_full_room(
    auth_client: CampaignTestClient,
) -> None:
    owner_client, _ = auth_client
    await owner_client.post(
        "/api/auth/register",
        json={"username": "RoomOwner", "password": "strong-player-password-2026"},
    )
    campaign = await _create_campaign(owner_client, max_players=3)

    player_client = await _new_player_client("RoomPlayer")
    joined = await player_client.post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"].lower()},
    )
    repeated = await player_client.post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"]},
    )
    invalid = await player_client.post(
        "/api/campaigns/join",
        json={"code": "RZ-00000"},
    )
    third_client = await _new_player_client("RoomPlayerThree")
    third_join = await third_client.post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"]},
    )
    full_client = await _new_player_client("RoomPlayerFour")
    full = await full_client.post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"]},
    )

    assert joined.status_code == 201
    assert joined.json()["participant_count"] == 2
    assert joined.json()["members"][1]["character_id"] is not None
    assert repeated.status_code == 409
    assert "já participa" in repeated.json()["detail"]
    assert invalid.status_code == 404
    assert "Código inválido" in invalid.json()["detail"]
    assert third_join.status_code == 201
    assert full.status_code == 409
    assert "cheia" in full.json()["detail"]

    await owner_client.post(f"/api/campaigns/{campaign['id']}/leave")
    owner_seat_reserved = await full_client.post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"]},
    )
    owner_return = await owner_client.post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"]},
    )
    assert owner_seat_reserved.status_code == 409
    assert owner_return.status_code == 200
    assert owner_return.json()["participant_count"] == 3

    await player_client.aclose()
    await third_client.aclose()
    await full_client.aclose()


@pytest.mark.anyio
@pytest.mark.postgres
async def test_campaign_access_requires_active_membership_and_player_role(
    auth_client: CampaignTestClient,
) -> None:
    owner_client, _ = auth_client
    await owner_client.post(
        "/api/auth/register",
        json={"username": "PrivateRoomOwner", "password": "strong-player-password-2026"},
    )
    campaign = await _create_campaign(owner_client)
    unauthorized = await _new_player_client("OutsidePlayer")

    private_campaign = await unauthorized.get(f"/api/campaigns/{campaign['id']}")
    private_members = await unauthorized.get(f"/api/campaigns/{campaign['id']}/members")
    private_ready = await unauthorized.post(
        f"/api/campaigns/{campaign['id']}/ready",
        json={"is_ready": True},
    )
    private_character = await unauthorized.post(
        f"/api/campaigns/{campaign['id']}/character",
        json={"name": "Unauthorized"},
    )
    anonymous = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )
    unauthenticated = await anonymous.get(f"/api/campaigns/{campaign['id']}")
    unauthenticated_create = await anonymous.post(
        "/api/campaigns",
        json={"title": "Anonymous campaign"},
    )
    owner_leave = await owner_client.post(f"/api/campaigns/{campaign['id']}/leave")
    owner_private = await owner_client.get(f"/api/campaigns/{campaign['id']}")

    assert private_campaign.status_code == 404
    assert private_members.status_code == 404
    assert private_ready.status_code == 404
    assert private_character.status_code == 404
    assert unauthenticated.status_code == 401
    assert unauthenticated_create.status_code == 401
    assert owner_leave.status_code == 204
    assert owner_private.status_code == 404

    await anonymous.aclose()
    await unauthorized.aclose()


@pytest.mark.anyio
async def test_leaving_and_rejoining_preserves_code_and_character(
    auth_client: CampaignTestClient,
) -> None:
    client, test_session = auth_client
    await client.post(
        "/api/auth/register",
        json={"username": "ReturningOwner", "password": "strong-player-password-2026"},
    )
    campaign = await _create_campaign(client)
    character_update = await client.post(
        f"/api/campaigns/{campaign['id']}/character",
        json={"name": "Elarion"},
    )
    left = await client.post(f"/api/campaigns/{campaign['id']}/leave")
    inaccessible = await client.get(f"/api/campaigns/{campaign['id']}")
    left_campaigns = await client.get("/api/campaigns")
    returned = await client.post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"]},
    )

    assert character_update.status_code == 200
    assert left.status_code == 204
    assert inaccessible.status_code == 404
    assert left_campaigns.json()[0]["membership_status"] == "left"
    assert left_campaigns.json()[0]["join_code"] == campaign["join_code"]
    assert returned.status_code == 200
    assert returned.json()["id"] == campaign["id"]
    assert returned.json()["join_code"] == campaign["join_code"]
    assert returned.json()["members"][0]["character_name"] == "Elarion"

    async with test_session() as session:
        character = await session.scalar(
            select(Character).where(
                Character.campaign_id == UUID(campaign["id"]),
                Character.name == "Elarion",
            )
        )
        assert character is not None
        member = await session.scalar(
            select(CampaignMember).where(
                CampaignMember.campaign_id == UUID(campaign["id"]),
                CampaignMember.user_id == character.owner_id,
            )
        )
        assert member is not None
        assert member.status == "active"
        assert member.character_id == character.id


@pytest.mark.anyio
@pytest.mark.postgres
async def test_lobby_readiness_and_presence_are_shared_with_participants(
    auth_client: CampaignTestClient,
) -> None:
    owner_client, _ = auth_client
    await owner_client.post(
        "/api/auth/register",
        json={"username": "PresenceOwner", "password": "strong-player-password-2026"},
    )
    campaign = await _create_campaign(owner_client)
    player_client = await _new_player_client("PresencePlayer")
    await player_client.post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"]},
    )

    ready = await player_client.post(
        f"/api/campaigns/{campaign['id']}/ready",
        json={"is_ready": True},
    )
    presence = await player_client.post(
        f"/api/campaigns/{campaign['id']}/presence",
        json={},
    )
    lobby = await owner_client.get(f"/api/campaigns/{campaign['id']}")

    assert ready.status_code == 200
    assert presence.status_code == 204
    player = next(
        member for member in lobby.json()["members"] if member["username"] == "PresencePlayer"
    )
    assert player["is_ready"] is True
    assert player["is_connected"] is True
    await player_client.aclose()


@pytest.mark.anyio
@pytest.mark.postgres
async def test_campaign_start_checks_owner_and_minimum_then_persists_session_event(
    auth_client: CampaignTestClient,
) -> None:
    owner_client, test_session = auth_client
    await owner_client.post(
        "/api/auth/register",
        json={"username": "StartOwner", "password": "strong-player-password-2026"},
    )
    campaign = await _create_campaign(owner_client, max_players=3)
    async with test_session() as session:
        chapter = Chapter(
            campaign_id=None,
            title="Capítulo inicial",
            summary="",
            narrative="",
            position=0,
            status="published",
            is_active=True,
        )
        session.add(chapter)
        await session.flush()
        scene = StoryNode(
            chapter_id=chapter.id,
            title="Cena inicial",
            narrative="",
            position=0,
            data={},
            is_active=True,
        )
        session.add(scene)
        await session.flush()
        session.add(
            StoryChoice(
                node_id=scene.id,
                label="Seguir em frente",
                position=0,
                conditions={},
                consequences={},
            )
        )
        await session.commit()
    too_few = await owner_client.post(f"/api/campaigns/{campaign['id']}/start")

    player_client = await _new_player_client("StartPlayer")
    await player_client.post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"]},
    )
    unauthorized_start = await player_client.post(
        f"/api/campaigns/{campaign['id']}/start",
    )
    another_client = await _new_player_client("StartPlayerThree")
    await another_client.post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"]},
    )
    started = await owner_client.post(f"/api/campaigns/{campaign['id']}/start")

    assert too_few.status_code == 409
    assert unauthorized_start.status_code == 403
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"
    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        assert game_session.status == "running"
        event = await session.scalar(
            select(GameEvent).where(GameEvent.session_id == game_session.id)
        )
        assert event is not None
        assert event.event_type == "campaign_started"

    await player_client.aclose()
    await another_client.aclose()


@pytest.mark.anyio
async def test_campaign_create_rejects_participant_limits_above_seven(
    auth_client: CampaignTestClient,
) -> None:
    client, _ = auth_client
    await client.post(
        "/api/auth/register",
        json={"username": "LimitOwner", "password": "strong-player-password-2026"},
    )
    invalid_limit = await client.post(
        "/api/campaigns",
        json={"title": "Invalid", "max_players": 8},
    )

    assert invalid_limit.status_code == 422


@pytest.mark.anyio
async def test_closed_campaign_does_not_accept_new_players(
    auth_client: CampaignTestClient,
) -> None:
    owner_client, test_session = auth_client
    await owner_client.post(
        "/api/auth/register",
        json={"username": "ClosedRoomOwner", "password": "strong-player-password-2026"},
    )
    campaign = await _create_campaign(owner_client)
    async with test_session() as session:
        stored = await session.get(Campaign, UUID(campaign["id"]))
        assert stored is not None
        stored.status = "closed"
        await session.commit()

    player_client = await _new_player_client("ClosedRoomPlayer")
    response = await player_client.post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"]},
    )

    assert response.status_code == 409
    assert "encerrada" in response.json()["detail"]
    await player_client.aclose()


@pytest.mark.anyio
@pytest.mark.postgres
async def test_postgres_concurrent_joins_preserve_seven_player_limit(
    auth_client: CampaignTestClient,
) -> None:
    owner_client, _ = auth_client
    registered = await owner_client.post(
        "/api/auth/register",
        json={"username": "ConcurrentRoomOwner", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    campaign = await _create_campaign(owner_client, max_players=7)
    clients = [
        await _new_player_client(
            f"ConcurrentJoin{index}",
            client_host=f"192.0.2.{index + 1}",
        )
        for index in range(7)
    ]

    responses = await asyncio.gather(
        *(
            client.post(
                "/api/campaigns/join",
                json={"code": campaign["join_code"]},
            )
            for client in clients
        )
    )

    assert [response.status_code for response in responses].count(201) == 6
    assert [response.status_code for response in responses].count(409) == 1
    lobby = await owner_client.get(f"/api/campaigns/{campaign['id']}")
    assert lobby.status_code == 200
    assert lobby.json()["participant_count"] == 7
    members = lobby.json()["members"]
    assert len({member["user_id"] for member in members}) == 7
    character_ids = [member["character_id"] for member in members]
    assert all(character_ids)
    assert len(set(character_ids)) == 7

    ordered_campaign = await _create_campaign(owner_client, max_players=7)
    for client in clients[:6]:
        joined = await client.post(
            "/api/campaigns/join",
            json={"code": ordered_campaign["join_code"]},
        )
        assert joined.status_code == 201
    eighth_participant = await clients[6].post(
        "/api/campaigns/join",
        json={"code": ordered_campaign["join_code"]},
    )
    assert eighth_participant.status_code == 409
    await asyncio.gather(*(client.aclose() for client in clients))
