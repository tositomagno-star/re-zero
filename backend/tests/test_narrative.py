import asyncio
from copy import deepcopy
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import hash_password
from app.main import app
from app.models import (
    Campaign,
    CampaignMember,
    Character,
    CharacterItem,
    CharacterQuest,
    CharacterRewardGrant,
    Chapter,
    GameEvent,
    GameSession,
    Item,
    Quest,
    StoryChoice,
    StoryNode,
    StoryVote,
    User,
    WalletTransaction,
    WorldReward,
)
from app.services.narrative import (
    _published_story_snapshot,
    _resolve_vote_result,
    _validate_story_snapshot,
    _vote_event_idempotency_key,
)

NarrativeTestClient = tuple[AsyncClient, async_sessionmaker[AsyncSession]]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("chapter_count", "scenes_per_chapter", "choices_per_scene"),
    [
        (0, 0, 0),
        (1, 1, 1),
        (3, 1, 1),
        (3, 4, 1),
        (3, 4, 5),
    ],
)
async def test_published_snapshot_query_count_baseline(
    auth_client: NarrativeTestClient,
    chapter_count: int,
    scenes_per_chapter: int,
    choices_per_scene: int,
) -> None:
    _, test_session = auth_client
    async with test_session() as session:
        for chapter_index in range(chapter_count):
            chapter = Chapter(
                campaign_id=None,
                title=f"Snapshot chapter {chapter_index}",
                summary="",
                narrative="",
                position=chapter_index,
                status="published",
                is_active=True,
            )
            session.add(chapter)
            await session.flush()
            for scene_index in range(scenes_per_chapter):
                scene = StoryNode(
                    chapter_id=chapter.id,
                    title=f"Snapshot scene {scene_index}",
                    narrative="",
                    position=scene_index,
                    data={},
                    is_active=True,
                )
                session.add(scene)
                await session.flush()
                session.add_all(
                    [
                        StoryChoice(
                            node_id=scene.id,
                            label=f"Choice {choice_index}",
                            position=choice_index,
                            conditions={},
                            consequences={},
                        )
                        for choice_index in range(choices_per_scene)
                    ]
                )
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
            snapshot = await _published_story_snapshot(session)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", count_query)

    assert len(snapshot) == chapter_count
    assert sum(len(chapter["scenes"]) for chapter in snapshot) == (
        chapter_count * scenes_per_chapter
    )
    assert sum(
        len(scene["choices"])
        for chapter in snapshot
        for scene in chapter["scenes"]
    ) == chapter_count * scenes_per_chapter * choices_per_scene
    assert query_count == 1 + chapter_count + chapter_count * scenes_per_chapter


def test_vote_event_idempotency_key_fits_database_column() -> None:
    key = _vote_event_idempotency_key(
        "vote_changed",
        uuid4(),
        uuid4(),
        1,
        uuid4(),
        1,
    )

    assert len(key) <= 120


def test_snapshot_validation_rejects_choices_to_unavailable_scenes() -> None:
    snapshot = [
        {
            "id": "chapter-1",
            "scenes": [
                {
                    "id": "scene-1",
                    "choices": [{"next_node_id": "inactive-scene"}],
                }
            ],
        }
    ]

    with pytest.raises(HTTPException) as error:
        _validate_story_snapshot(snapshot)

    assert error.value.status_code == 409
    assert error.value.detail == (
        "Uma escolha de capítulo publicado aponta para uma cena inativa "
        "ou indisponível."
    )


def test_vote_resolution_applies_choice_order_tiebreaker() -> None:
    earlier_choice_id = uuid4()
    later_choice_id = uuid4()
    scene = {
        "choices": [
            {"id": str(later_choice_id), "label": "Depois", "position": 1},
            {"id": str(earlier_choice_id), "label": "Antes", "position": 0},
        ]
    }
    ballots = [
        StoryVote(user_id=uuid4(), choice_id=earlier_choice_id),
        StoryVote(user_id=uuid4(), choice_id=later_choice_id),
    ]
    resolved_at = datetime(2026, 11, 1, tzinfo=timezone.utc)

    result, selected_choice = _resolve_vote_result(
        scene,
        ballots,
        3,
        resolved_at,
        "choice_order",
    )

    assert selected_choice is not None
    assert selected_choice["id"] == str(earlier_choice_id)
    assert result == {
        "round_number": 3,
        "tally": [
            {"choice_id": str(later_choice_id), "label": "Depois", "votes": 1},
            {"choice_id": str(earlier_choice_id), "label": "Antes", "votes": 1},
        ],
        "resolved_at": resolved_at.isoformat(),
        "tie_breaker": "choice_order",
    }


def test_vote_resolution_preserves_unresolved_tie_and_no_vote_results() -> None:
    first_choice_id = uuid4()
    second_choice_id = uuid4()
    scene = {
        "choices": [
            {"id": str(first_choice_id), "label": "Primeira", "position": 0},
            {"id": str(second_choice_id), "label": "Segunda", "position": 1},
        ]
    }
    ballots = [
        StoryVote(user_id=uuid4(), choice_id=first_choice_id),
        StoryVote(user_id=uuid4(), choice_id=second_choice_id),
    ]
    resolved_at = datetime(2026, 11, 1, tzinfo=timezone.utc)

    tie_result, selected_choice = _resolve_vote_result(
        scene,
        ballots,
        1,
        resolved_at,
        "unresolved",
    )
    no_vote_result, no_vote_choice = _resolve_vote_result(
        scene,
        [],
        2,
        resolved_at,
        "unresolved",
    )

    assert selected_choice is None
    assert tie_result["status"] == "tied"
    assert no_vote_choice is None
    assert no_vote_result["status"] == "no_votes"


async def _new_player(
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
    assert response.status_code == 201, response.text
    return client


async def _create_story(
    test_session: async_sessionmaker[AsyncSession],
    *,
    choice_consequences: dict[str, object] | None = None,
) -> dict[str, UUID]:
    chapter_id = uuid4()
    next_chapter_id = uuid4()
    initial_id, north_id, south_id, finale_id, next_chapter_scene_id = (
        uuid4() for _ in range(5)
    )
    (
        north_choice_id,
        south_choice_id,
        north_continue_id,
        south_continue_id,
        finale_choice_id,
        next_chapter_choice_id,
    ) = (uuid4() for _ in range(6))
    async with test_session() as session:
        chapter = Chapter(
            id=chapter_id,
            campaign_id=None,
            title="A Vigília de Cinzas",
            summary="Uma história persistente.",
            narrative="O sino ecoa sobre a cidade.",
            position=0,
            status="published",
            is_active=True,
        )
        session.add(chapter)
        session.add(
            Chapter(
                id=next_chapter_id,
                campaign_id=None,
                title="O próximo capítulo",
                summary="A jornada continua.",
                narrative="Uma nova região se revela.",
                position=1,
                status="published",
                is_active=True,
            )
        )
        session.add_all(
            [
                StoryNode(
                    id=initial_id,
                    chapter_id=chapter_id,
                    title="A encruzilhada",
                    narrative="Duas trilhas se abrem.",
                    position=0,
                    data={},
                    is_active=True,
                ),
                StoryNode(
                    id=north_id,
                    chapter_id=chapter_id,
                    title="Trilha do norte",
                    narrative="Uma fogueira ilumina o caminho.",
                    position=1,
                    data={},
                    is_active=True,
                ),
                StoryNode(
                    id=south_id,
                    chapter_id=chapter_id,
                    title="Trilha do sul",
                    narrative="A estrada segue pelo rio.",
                    position=2,
                    data={},
                    is_active=True,
                ),
                StoryNode(
                    id=finale_id,
                    chapter_id=chapter_id,
                    title="O portão",
                    narrative="O portão se abre.",
                    position=3,
                    data={},
                    is_active=True,
                ),
                StoryNode(
                    id=next_chapter_scene_id,
                    chapter_id=next_chapter_id,
                    title="A nova região",
                    narrative="A jornada continua além das muralhas.",
                    position=0,
                    data={},
                    is_active=True,
                ),
            ]
        )
        session.add_all(
            [
                StoryChoice(
                    id=north_choice_id,
                    node_id=initial_id,
                    next_node_id=north_id,
                    label="Seguir ao norte",
                    position=0,
                    conditions={},
                    consequences={
                        "description": "Uma fogueira guia o grupo.",
                        **(choice_consequences or {}),
                    },
                ),
                StoryChoice(
                    id=south_choice_id,
                    node_id=initial_id,
                    next_node_id=south_id,
                    label="Seguir ao sul",
                    position=1,
                    conditions={},
                    consequences={"description": "O grupo encontra o rio."},
                ),
                StoryChoice(
                    id=north_continue_id,
                    node_id=north_id,
                    next_node_id=finale_id,
                    label="Avançar até o portão",
                    position=0,
                    conditions={},
                    consequences={},
                ),
                StoryChoice(
                    id=south_continue_id,
                    node_id=south_id,
                    next_node_id=finale_id,
                    label="Avançar até o portão",
                    position=0,
                    conditions={},
                    consequences={},
                ),
                StoryChoice(
                    id=finale_choice_id,
                    node_id=finale_id,
                    label="Atravessar o portão",
                    position=0,
                    conditions={},
                    consequences={"description": "A próxima região está aberta."},
                ),
                StoryChoice(
                    id=next_chapter_choice_id,
                    node_id=next_chapter_scene_id,
                    label="Prosseguir",
                    position=0,
                    conditions={},
                    consequences={},
                ),
            ]
        )
        await session.commit()
    return {
        "chapter_id": chapter_id,
        "next_chapter_id": next_chapter_id,
        "initial_id": initial_id,
        "north_id": north_id,
        "south_id": south_id,
        "finale_id": finale_id,
        "next_chapter_scene_id": next_chapter_scene_id,
        "north_choice_id": north_choice_id,
        "south_choice_id": south_choice_id,
        "north_continue_id": north_continue_id,
        "finale_choice_id": finale_choice_id,
        "next_chapter_choice_id": next_chapter_choice_id,
    }


async def _prepare_game(
    owner_client: AsyncClient,
    test_session: async_sessionmaker[AsyncSession],
    *,
    max_players: int = 3,
    voting_settings: dict[str, object] | None = None,
    choice_consequences: dict[str, object] | None = None,
) -> tuple[dict, list[AsyncClient], dict[str, UUID]]:
    registered = await owner_client.post(
        "/api/auth/register",
        json={
            "username": f"Owner{uuid4().hex[:8]}",
            "password": "strong-player-password-2026",
        },
    )
    assert registered.status_code == 201, registered.text
    campaign_payload: dict[str, object] = {
        "title": "A Vigília de Cinzas",
        "description": "Campanha de teste.",
        "max_players": max_players,
    }
    if voting_settings is not None:
        campaign_payload["voting_settings"] = voting_settings
    created = await owner_client.post("/api/campaigns", json=campaign_payload)
    assert created.status_code == 201, created.text
    campaign = created.json()

    clients = [owner_client]
    for index in range(1, max_players):
        player = await _new_player(f"Player{uuid4().hex[:8]}")
        joined = await player.post(
            "/api/campaigns/join",
            json={"code": campaign["join_code"]},
        )
        assert joined.status_code == 201, joined.text
        clients.append(player)

    story = await _create_story(
        test_session,
        choice_consequences=choice_consequences,
    )
    started = await owner_client.post(f"/api/campaigns/{campaign['id']}/start")
    assert started.status_code == 200, started.text
    return campaign, clients, story


async def _vote(client: AsyncClient, campaign_id: str, choice_id: UUID):
    return await client.post(
        f"/api/campaigns/{campaign_id}/game/vote",
        json={"choice_id": str(choice_id)},
    )


@pytest.mark.anyio
async def test_start_requires_published_scene_without_mutating_lobby(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    registered = await owner.post(
        "/api/auth/register",
        json={
            "username": f"NoStory{uuid4().hex[:8]}",
            "password": "strong-player-password-2026",
        },
    )
    assert registered.status_code == 201
    created = await owner.post(
        "/api/campaigns",
        json={"title": "Sem conteúdo", "max_players": 3},
    )
    assert created.status_code == 201
    campaign = created.json()
    players = [await _new_player(f"NoStoryPlayer{uuid4().hex[:8]}") for _ in range(2)]
    for player in players:
        joined = await player.post(
            "/api/campaigns/join",
            json={"code": campaign["join_code"]},
        )
        assert joined.status_code == 201

    start = await owner.post(f"/api/campaigns/{campaign['id']}/start")

    assert start.status_code == 409
    async with test_session() as session:
        stored_campaign = await session.get(Campaign, UUID(campaign["id"]))
        session_count = await session.scalar(
            select(func.count(GameSession.id)).where(
                GameSession.campaign_id == UUID(campaign["id"])
            )
        )
        assert stored_campaign is not None
        assert stored_campaign.status == "waiting"
        assert session_count == 0
    await asyncio.gather(*(player.aclose() for player in players))


@pytest.mark.anyio
async def test_legacy_session_without_snapshot_is_not_rewritten(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    registered = await owner.post(
        "/api/auth/register",
        json={
            "username": f"Legacy{uuid4().hex[:8]}",
            "password": "strong-player-password-2026",
        },
    )
    assert registered.status_code == 201
    created = await owner.post(
        "/api/campaigns",
        json={"title": "Sessão antiga", "max_players": 3},
    )
    assert created.status_code == 201
    campaign = created.json()
    async with test_session() as session:
        stored_campaign = await session.get(Campaign, UUID(campaign["id"]))
        assert stored_campaign is not None
        stored_campaign.status = "in_progress"
        legacy_session = GameSession(
            campaign_id=stored_campaign.id,
            current_node_id=None,
            status="running",
            state={},
        )
        session.add(legacy_session)
        await session.commit()

    response = await owner.get(f"/api/campaigns/{campaign['id']}/game")

    assert response.status_code == 409
    assert "snapshot narrativo" in response.json()["detail"]
    async with test_session() as session:
        stored = await session.get(GameSession, legacy_session.id)
        assert stored is not None
        assert stored.state == {}
        assert stored.status == "running"


@pytest.mark.anyio
async def test_start_loads_official_initial_scene_and_choices(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(owner, test_session)

    response = await owner.get(f"/api/campaigns/{campaign['id']}/game")

    assert response.status_code == 200, response.text
    game = response.json()
    assert game["status"] == "running"
    assert game["chapter"]["title"] == "A Vigília de Cinzas"
    assert game["scene"]["id"] == str(story["initial_id"])
    assert [choice["id"] for choice in game["scene"]["choices"]] == [
        str(story["north_choice_id"]),
        str(story["south_choice_id"]),
    ]
    assert game["vote"]["status"] == "open"
    assert game["vote"]["eligible_count"] == 3
    assert game["vote"]["deadline_at"] is None
    assert len(game["participants"]) == 3
    assert game["history"][0]["event_type"] == "campaign_started"

    async with test_session() as session:
        stored_campaign = await session.get(Campaign, UUID(campaign["id"]))
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert stored_campaign is not None
        assert stored_campaign.current_chapter_id == story["chapter_id"]
        assert stored_campaign.current_node_id == story["initial_id"]
        assert game_session is not None
        assert game_session.state["content_snapshot"][0]["title"] == "A Vigília de Cinzas"

        node = await session.get(StoryNode, story["initial_id"])
        assert node is not None
        node.title = "Título alterado no painel"
        await session.commit()

    unchanged_snapshot = await owner.get(f"/api/campaigns/{campaign['id']}/game")
    assert unchanged_snapshot.json()["scene"]["title"] == "A encruzilhada"
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
@pytest.mark.postgres
async def test_postgres_campaign_start_snapshot_is_immutable_during_content_edit(
    auth_client: NarrativeTestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, test_session = auth_client
    registered = await owner.post(
        "/api/auth/register",
        json={
            "username": f"SnapshotRaceOwner{uuid4().hex[:8]}",
            "password": "strong-player-password-2026",
        },
    )
    assert registered.status_code == 201, registered.text
    created = await owner.post(
        "/api/campaigns",
        json={"title": "Snapshot concorrente", "max_players": 3},
    )
    assert created.status_code == 201, created.text
    campaign = created.json()

    players = [owner]
    for index in range(2):
        player = await _new_player(f"SnapshotRacePlayer{index}{uuid4().hex[:8]}")
        joined = await player.post(
            "/api/campaigns/join",
            json={"code": campaign["join_code"]},
        )
        assert joined.status_code == 201, joined.text
        players.append(player)

    story = await _create_story(test_session)
    admin_name = f"SnapshotRaceAdmin{uuid4().hex[:8]}"
    admin_password = "a-long-snapshot-race-password"
    async with test_session() as session:
        session.add(
            User(
                username=admin_name,
                username_key=admin_name.lower(),
                email=None,
                password_hash=hash_password(admin_password),
                display_name="Snapshot Race Admin",
                is_admin=True,
                status="active",
            )
        )
        await session.commit()

    admin_client = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )
    login = await admin_client.post(
        "/api/auth/admin/login",
        json={"username": admin_name, "password": admin_password},
    )
    assert login.status_code == 200

    chapters_response = await admin_client.get("/api/admin/content/chapters")
    assert chapters_response.status_code == 200
    chapter = next(
        item
        for item in chapters_response.json()
        if item["id"] == str(story["chapter_id"])
    )
    update_payload = {
        key: chapter[key]
        for key in (
            "title",
            "summary",
            "narrative",
            "position",
            "status",
            "is_active",
            "npc_ids",
            "enemy_ids",
            "scenes",
        )
    }
    updated_chapter_title = "Título publicado durante o início"
    updated_scene_narrative = "Narrativa revisada após o snapshot."
    update_payload["title"] = updated_chapter_title
    update_payload["scenes"][0]["narrative"] = updated_scene_narrative

    snapshot_lock_acquired = asyncio.Event()
    allow_snapshot_to_continue = asyncio.Event()
    update_statement_started = asyncio.Event()
    original_scalars = AsyncSession.scalars

    async def pause_after_snapshot_chapter_lock(
        session: AsyncSession,
        statement,
        *args,
        **kwargs,
    ):
        result = await original_scalars(session, statement, *args, **kwargs)
        descriptions = getattr(statement, "column_descriptions", ())
        if (
            descriptions
            and descriptions[0].get("entity") is Chapter
            and getattr(statement, "_for_update_arg", None) is not None
            and not snapshot_lock_acquired.is_set()
        ):
            snapshot_lock_acquired.set()
            await allow_snapshot_to_continue.wait()
        return result

    monkeypatch.setattr(
        AsyncSession,
        "scalars",
        pause_after_snapshot_chapter_lock,
    )

    def signal_chapter_update_before_execution(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        if re.match(r"\s*UPDATE\s+chapters\b", statement, re.IGNORECASE):
            update_statement_started.set()

    engine = test_session.kw["bind"]
    event.listen(
        engine.sync_engine,
        "before_cursor_execute",
        signal_chapter_update_before_execution,
    )
    start_task = asyncio.create_task(
        owner.post(f"/api/campaigns/{campaign['id']}/start")
    )
    update_task = None
    try:
        await asyncio.wait_for(snapshot_lock_acquired.wait(), timeout=10)
        update_task = asyncio.create_task(
            admin_client.put(
                f"/api/admin/content/chapters/{story['chapter_id']}",
                json=update_payload,
            )
        )
        await asyncio.wait_for(update_statement_started.wait(), timeout=10)
        assert not update_task.done()

        allow_snapshot_to_continue.set()
        start_response, update_response = await asyncio.gather(start_task, update_task)
    finally:
        allow_snapshot_to_continue.set()
        await asyncio.gather(
            start_task,
            *( [update_task] if update_task is not None else [] ),
            return_exceptions=True,
        )
        event.remove(
            engine.sync_engine,
            "before_cursor_execute",
            signal_chapter_update_before_execution,
        )
        await admin_client.aclose()
        await asyncio.gather(*(player.aclose() for player in players[1:]))

    assert start_response.status_code == 200, start_response.text
    assert start_response.json()["status"] == "in_progress"
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["title"] == updated_chapter_title

    async with test_session() as session:
        stored_campaign = await session.get(Campaign, UUID(campaign["id"]))
        sessions = list(
            (
                await session.scalars(
                    select(GameSession).where(
                        GameSession.campaign_id == UUID(campaign["id"])
                    )
                )
            ).all()
        )
        assert stored_campaign is not None
        assert stored_campaign.status == "in_progress"
        assert len(sessions) == 1
        game_session = sessions[0]
        assert game_session.status == "running"
        assert game_session.current_node_id == story["initial_id"]
        assert game_session.state["current_chapter_id"] == str(story["chapter_id"])

        snapshot_chapter = next(
            item
            for item in game_session.state["content_snapshot"]
            if item["id"] == str(story["chapter_id"])
        )
        snapshot_scene = next(
            item
            for item in snapshot_chapter["scenes"]
            if item["id"] == str(story["initial_id"])
        )
        assert snapshot_chapter["title"] == "A Vigília de Cinzas"
        assert snapshot_scene["narrative"] == "Duas trilhas se abrem."
        assert [
            choice["label"] for choice in snapshot_scene["choices"]
        ] == ["Seguir ao norte", "Seguir ao sul"]

        stored_chapter = await session.get(Chapter, story["chapter_id"])
        stored_scene = await session.get(StoryNode, story["initial_id"])
        assert stored_chapter is not None
        assert stored_scene is not None
        assert stored_chapter.title == updated_chapter_title
        assert stored_scene.narrative == updated_scene_narrative

        events = list(
            (
                await session.scalars(
                    select(GameEvent)
                    .where(GameEvent.session_id == game_session.id)
                    .order_by(GameEvent.sequence_number)
                )
            ).all()
        )
        assert len(events) == 1
        assert events[0].sequence_number == 1
        assert events[0].event_type == "campaign_started"
        assert events[0].idempotency_key == f"campaign-start:{campaign['id']}"
        assert events[0].payload["campaign_id"] == campaign["id"]
        assert events[0].payload["chapter_id"] == str(story["chapter_id"])
        assert events[0].payload["node_id"] == str(story["initial_id"])

    resumed_game = await owner.get(f"/api/campaigns/{campaign['id']}/game")
    assert resumed_game.status_code == 200, resumed_game.text
    assert resumed_game.json()["chapter"]["title"] == "A Vigília de Cinzas"
    assert resumed_game.json()["scene"]["narrative"] == "Duas trilhas se abrem."


@pytest.mark.anyio
async def test_active_session_snapshot_blocks_admin_choice_rewrite(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(owner, test_session)
    admin_name = f"StoryAdmin{uuid4().hex[:8]}"
    admin_password = "a-long-admin-password-2026"
    async with test_session() as session:
        session.add(
            User(
                username=admin_name,
                username_key=admin_name.lower(),
                email=None,
                password_hash=hash_password(admin_password),
                display_name="Story Admin",
                is_admin=True,
                status="active",
            )
        )
        await session.commit()
    admin_client = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )
    login = await admin_client.post(
        "/api/auth/admin/login",
        json={"username": admin_name, "password": admin_password},
    )
    assert login.status_code == 200
    chapters = await admin_client.get("/api/admin/content/chapters")
    chapter = next(item for item in chapters.json() if item["id"] == str(story["chapter_id"]))
    update_payload = {
        key: chapter[key]
        for key in (
            "title",
            "summary",
            "narrative",
            "position",
            "status",
            "is_active",
            "npc_ids",
            "enemy_ids",
            "scenes",
        )
    }
    update_payload["scenes"][0]["choices"][0]["label"] = "Escolha reescrita"

    update = await admin_client.put(
        f"/api/admin/content/chapters/{story['chapter_id']}",
        json=update_payload,
    )

    assert update.status_code == 409
    current_game = await owner.get(f"/api/campaigns/{campaign['id']}/game")
    assert current_game.json()["scene"]["choices"][0]["label"] == "Seguir ao norte"
    await admin_client.aclose()
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
async def test_votes_change_once_resolve_majority_apply_consequence_and_advance(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(owner, test_session)

    invalid_choice = await _vote(owner, campaign["id"], uuid4())
    first_vote = await _vote(owner, campaign["id"], story["north_choice_id"])
    repeated_vote = await _vote(owner, campaign["id"], story["north_choice_id"])
    changed_vote = await _vote(owner, campaign["id"], story["south_choice_id"])
    second_player_vote = await _vote(clients[1], campaign["id"], story["north_choice_id"])
    final_vote = await _vote(clients[2], campaign["id"], story["north_choice_id"])

    assert invalid_choice.status_code == 422
    assert first_vote.status_code == 200
    assert first_vote.json()["vote"]["voted_count"] == 1
    assert repeated_vote.status_code == 200
    assert changed_vote.status_code == 200
    assert changed_vote.json()["vote"]["my_choice_id"] == str(story["south_choice_id"])
    assert second_player_vote.status_code == 200
    assert final_vote.status_code == 200, final_vote.text
    game = final_vote.json()
    assert game["scene"]["id"] == str(story["north_id"])
    assert game["last_result"]["choice_id"] == str(story["north_choice_id"])
    assert game["last_result"]["choice_label"] == "Seguir ao norte"
    assert game["last_result"]["consequences"]["description"] == "Uma fogueira guia o grupo."
    assert game["vote"]["status"] == "open"
    assert any(event["event_type"] == "vote_changed" for event in game["history"])
    assert sum(event["event_type"] == "decision_resolved" for event in game["history"]) == 1

    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        ballots = await session.scalar(
            select(func.count(StoryVote.id)).where(
                StoryVote.session_id == game_session.id,
                StoryVote.node_id == story["initial_id"],
                StoryVote.user_id == UUID(campaign["owner_id"]),
            )
        )
        assert ballots == 1
        decisions = await session.scalar(
            select(func.count(GameEvent.id)).where(
                GameEvent.session_id == game_session.id,
                GameEvent.event_type == "decision_resolved",
            )
        )
        assert decisions == 1
        assert len(game_session.state["applied_consequences"]) == 1
        assert game_session.state["applied_consequences"][0]["consequences"] == {
            "description": "Uma fogueira guia o grupo."
        }

    duplicate_apuration = await owner.get(f"/api/campaigns/{campaign['id']}/game")
    assert duplicate_apuration.status_code == 200
    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        decisions = await session.scalar(
            select(func.count(GameEvent.id)).where(
                GameEvent.session_id == game_session.id,
                GameEvent.event_type == "decision_resolved",
            )
        )
        assert decisions == 1
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
async def test_polling_open_vote_does_not_persist_changes(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(owner, test_session)
    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        initial_state = deepcopy(game_session.state)
        initial_events = list(
            (
                await session.scalars(
                    select(GameEvent)
                    .where(GameEvent.session_id == game_session.id)
                    .order_by(GameEvent.sequence_number)
                )
            ).all()
        )
        assert [event.event_type for event in initial_events] == ["campaign_started"]

    first_poll = await owner.get(f"/api/campaigns/{campaign['id']}/game")
    second_poll = await owner.get(f"/api/campaigns/{campaign['id']}/game")

    assert first_poll.status_code == 200
    assert second_poll.status_code == 200
    assert first_poll.json()["scene"]["id"] == str(story["initial_id"])
    assert second_poll.json()["vote"]["status"] == "open"
    assert second_poll.json()["vote"]["voted_count"] == 0
    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        assert game_session.state == initial_state
        events = list(
            (
                await session.scalars(
                    select(GameEvent)
                    .where(GameEvent.session_id == game_session.id)
                    .order_by(GameEvent.sequence_number)
                )
            ).all()
        )
        assert [(event.sequence_number, event.event_type) for event in events] == [
            (1, "campaign_started")
        ]
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
async def test_expired_vote_without_ballots_closes_once_without_advancing(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(owner, test_session)
    expired_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        state = deepcopy(game_session.state)
        state["vote"] = {**state["vote"], "deadline_at": expired_at}
        game_session.state = state
        await session.commit()

    closed = await owner.get(f"/api/campaigns/{campaign['id']}/game")
    repeated_poll = await owner.get(f"/api/campaigns/{campaign['id']}/game")

    assert closed.status_code == 200
    assert closed.json()["status"] == "running"
    assert closed.json()["scene"]["id"] == str(story["initial_id"])
    assert closed.json()["vote"]["status"] == "no_votes"
    assert closed.json()["vote"]["result"]["status"] == "no_votes"
    assert repeated_poll.status_code == 200
    assert repeated_poll.json()["vote"]["status"] == "no_votes"
    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        assert game_session.current_node_id == story["initial_id"]
        assert game_session.state["vote"]["status"] == "no_votes"
        events = list(
            (
                await session.scalars(
                    select(GameEvent)
                    .where(GameEvent.session_id == game_session.id)
                    .order_by(GameEvent.sequence_number)
                )
            ).all()
        )
        assert [event.event_type for event in events] == [
            "campaign_started",
            "vote_closed_without_votes",
        ]
        assert [event.sequence_number for event in events] == [1, 2]
        assert events[1].idempotency_key == (
            f"vote-result:{game_session.id}:{story['initial_id']}:1"
        )
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
async def test_progression_advances_to_the_next_official_chapter(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(owner, test_session)

    for client in clients:
        await _vote(client, campaign["id"], story["north_choice_id"])
    for client in clients:
        await _vote(client, campaign["id"], story["north_continue_id"])
    for client in clients:
        await _vote(client, campaign["id"], story["finale_choice_id"])

    game = (await owner.get(f"/api/campaigns/{campaign['id']}/game")).json()
    assert game["chapter"]["id"] == str(story["next_chapter_id"])
    assert game["chapter"]["title"] == "O próximo capítulo"
    assert game["scene"]["id"] == str(story["next_chapter_scene_id"])
    assert game["vote"]["status"] == "open"
    for client in clients:
        final_response = await _vote(client, campaign["id"], story["next_chapter_choice_id"])
    assert final_response.status_code == 200
    assert final_response.json()["status"] == "completed"
    assert any(event["event_type"] == "session_completed" for event in final_response.json()["history"])
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
async def test_closed_vote_rejects_changes_and_tie_can_use_choice_order(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(
        owner,
        test_session,
        max_players=4,
        voting_settings={
            "allow_vote_change": False,
            "deadline_seconds": None,
            "tie_breaker": "choice_order",
        },
    )
    first_vote = await _vote(owner, campaign["id"], story["north_choice_id"])
    rejected_change = await _vote(owner, campaign["id"], story["south_choice_id"])
    assert first_vote.status_code == 200
    assert rejected_change.status_code == 409

    await _vote(clients[1], campaign["id"], story["south_choice_id"])
    await _vote(clients[2], campaign["id"], story["north_choice_id"])
    tie_resolved = await _vote(clients[3], campaign["id"], story["south_choice_id"])

    assert tie_resolved.status_code == 200, tie_resolved.text
    game = tie_resolved.json()
    assert game["scene"]["id"] == str(story["north_id"])
    assert game["last_result"]["choice_id"] == str(story["north_choice_id"])
    assert game["last_result"]["tie_breaker"] == "choice_order"
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
async def test_tie_without_rule_is_persisted_without_advancing(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(
        owner,
        test_session,
        max_players=4,
    )
    await _vote(owner, campaign["id"], story["north_choice_id"])
    await _vote(clients[1], campaign["id"], story["north_choice_id"])
    await _vote(clients[2], campaign["id"], story["south_choice_id"])
    tied = await _vote(clients[3], campaign["id"], story["south_choice_id"])

    assert tied.status_code == 200, tied.text
    game = tied.json()
    assert game["scene"]["id"] == str(story["initial_id"])
    assert game["vote"]["status"] == "tied"
    assert game["vote"]["result"]["status"] == "tied"
    assert sorted(result["votes"] for result in game["vote"]["tally"]) == [2, 2]
    assert sum(event["event_type"] == "vote_tied" for event in game["history"]) == 1
    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        assert game_session.state["applied_consequences"] == []
        assert game_session.current_node_id == story["initial_id"]
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
async def test_timeout_persistence_reentry_and_campaign_isolation(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(
        owner,
        test_session,
        voting_settings={
            "allow_vote_change": True,
            "deadline_seconds": 3600,
            "tie_breaker": "unresolved",
        },
    )
    second_vote = await _vote(clients[1], campaign["id"], story["north_choice_id"])
    assert second_vote.status_code == 200
    left = await clients[1].post(f"/api/campaigns/{campaign['id']}/leave")
    assert left.status_code == 204
    hidden = await clients[1].get(f"/api/campaigns/{campaign['id']}/game")
    assert hidden.status_code == 404
    returned = await clients[1].post(
        "/api/campaigns/join",
        json={"code": campaign["join_code"]},
    )
    assert returned.status_code == 200
    resumed = await clients[1].get(f"/api/campaigns/{campaign['id']}/game")
    assert resumed.status_code == 200
    assert resumed.json()["vote"]["voted_count"] == 1
    assert resumed.json()["vote"]["my_choice_id"] == str(story["north_choice_id"])

    second_campaign_response = await owner.post(
        "/api/campaigns",
        json={"title": "Outra campanha", "max_players": 3},
    )
    assert second_campaign_response.status_code == 201
    second_campaign = second_campaign_response.json()
    for player in clients[1:]:
        joined = await player.post(
            "/api/campaigns/join",
            json={"code": second_campaign["join_code"]},
        )
        assert joined.status_code == 201
    second_started = await owner.post(f"/api/campaigns/{second_campaign['id']}/start")
    assert second_started.status_code == 200, second_started.text
    second_game = await owner.get(f"/api/campaigns/{second_campaign['id']}/game")
    assert second_game.status_code == 200
    assert second_game.json()["vote"]["voted_count"] == 0

    outsider = await _new_player("Outsider" + uuid4().hex[:8])
    forbidden_read = await outsider.get(f"/api/campaigns/{campaign['id']}/game")
    forbidden_vote = await _vote(outsider, campaign["id"], story["north_choice_id"])
    assert forbidden_read.status_code == 404
    assert forbidden_vote.status_code == 404

    async with test_session() as session:
        first_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        second_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(second_campaign["id"]))
        )
        assert first_session is not None and second_session is not None
        assert first_session.id != second_session.id
        first_campaign = await session.get(Campaign, UUID(campaign["id"]))
        second_stored_campaign = await session.get(Campaign, UUID(second_campaign["id"]))
        assert first_campaign is not None and second_stored_campaign is not None
        updated_settings = dict(first_campaign.settings)
        updated_settings["narrative_voting"] = {
            **updated_settings["narrative_voting"],
            "deadline_seconds": 1,
        }
        first_campaign.settings = updated_settings
        updated_state = dict(first_session.state)
        updated_state["vote"] = {
            **updated_state["vote"],
            "deadline_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        }
        first_session.state = updated_state
        await session.commit()

    timed_out = await owner.get(f"/api/campaigns/{campaign['id']}/game")
    assert timed_out.status_code == 200
    assert timed_out.json()["scene"]["id"] == str(story["north_id"])
    assert timed_out.json()["last_result"]["choice_id"] == str(story["north_choice_id"])
    second_game_after_timeout = await owner.get(f"/api/campaigns/{second_campaign['id']}/game")
    assert second_game_after_timeout.json()["vote"]["status"] == "open"
    await asyncio.gather(*(client.aclose() for client in clients[1:]))
    await outsider.aclose()


@pytest.mark.anyio
@pytest.mark.postgres
async def test_simultaneous_last_votes_create_one_final_decision(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(owner, test_session)
    await _vote(owner, campaign["id"], story["north_choice_id"])

    responses = await asyncio.gather(
        _vote(clients[1], campaign["id"], story["north_choice_id"]),
        _vote(clients[2], campaign["id"], story["north_choice_id"]),
        return_exceptions=True,
    )
    assert all(not isinstance(response, Exception) for response in responses), responses
    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        decision_count = await session.scalar(
            select(func.count(GameEvent.id)).where(
                GameEvent.session_id == game_session.id,
                GameEvent.event_type == "decision_resolved",
            )
        )
        assert decision_count == 1
        assert game_session.state["applied_consequences"] == [
            {
                "decision_key": (
                    f"decision:{game_session.id}:{story['initial_id']}:1"
                ),
                "chapter_id": str(story["chapter_id"]),
                "node_id": str(story["initial_id"]),
                "choice_id": str(story["north_choice_id"]),
                "consequences": {"description": "Uma fogueira guia o grupo."},
                "applied_at": game_session.state["applied_consequences"][0]["applied_at"],
            }
        ]
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
@pytest.mark.postgres
async def test_concurrent_vote_change_and_other_player_vote_preserve_both_ballots(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(owner, test_session)
    initial = await _vote(owner, campaign["id"], story["north_choice_id"])
    assert initial.status_code == 200

    responses = await asyncio.gather(
        _vote(owner, campaign["id"], story["south_choice_id"]),
        _vote(clients[1], campaign["id"], story["north_choice_id"]),
    )

    assert [response.status_code for response in responses] == [200, 200]
    changed_vote_user_id = (await clients[1].get("/api/auth/session")).json()["id"]
    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        ballots = list(
            (
                await session.scalars(
                    select(StoryVote).where(
                        StoryVote.session_id == game_session.id,
                        StoryVote.node_id == story["initial_id"],
                        StoryVote.round_number == 1,
                    )
                )
            ).all()
        )
        votes_by_user = {str(ballot.user_id): str(ballot.choice_id) for ballot in ballots}
        assert len(ballots) == 2
        assert votes_by_user[str(UUID(campaign["owner_id"]))] == str(story["south_choice_id"])
        assert votes_by_user[changed_vote_user_id] == str(story["north_choice_id"])
        vote_events = list(
            (
                await session.scalars(
                    select(GameEvent)
                    .where(
                        GameEvent.session_id == game_session.id,
                        GameEvent.event_type.in_(("vote_cast", "vote_changed")),
                    )
                    .order_by(GameEvent.sequence_number)
                )
            ).all()
        )
        assert [event.event_type for event in vote_events].count("vote_changed") == 1
        assert len({event.sequence_number for event in vote_events}) == len(vote_events)
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
@pytest.mark.postgres
async def test_concurrent_deadline_closure_applies_consequence_and_advances_once(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(
        owner,
        test_session,
        voting_settings={
            "allow_vote_change": True,
            "deadline_seconds": 3600,
            "tie_breaker": "unresolved",
        },
    )
    first_vote = await _vote(owner, campaign["id"], story["north_choice_id"])
    second_vote = await _vote(clients[1], campaign["id"], story["north_choice_id"])
    assert first_vote.status_code == 200
    assert second_vote.status_code == 200

    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        expired_state = dict(game_session.state)
        expired_state["vote"] = {
            **expired_state["vote"],
            "deadline_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        }
        game_session.state = expired_state
        await session.commit()

    responses = await asyncio.gather(
        owner.get(f"/api/campaigns/{campaign['id']}/game"),
        clients[1].get(f"/api/campaigns/{campaign['id']}/game"),
    )
    assert [response.status_code for response in responses] == [200, 200]
    assert {response.json()["scene"]["id"] for response in responses} == {
        str(story["north_id"])
    }

    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        stored_campaign = await session.get(Campaign, UUID(campaign["id"]))
        assert game_session is not None and stored_campaign is not None
        assert game_session.current_node_id == story["north_id"]
        assert stored_campaign.current_node_id == story["north_id"]
        decisions = list(
            (
                await session.scalars(
                    select(GameEvent).where(
                        GameEvent.session_id == game_session.id,
                        GameEvent.event_type == "decision_resolved",
                    )
                )
            ).all()
        )
        assert len(decisions) == 1
        assert len(game_session.state["applied_consequences"]) == 1
        event_sequences = list(
            (
                await session.scalars(
                    select(GameEvent.sequence_number)
                    .where(GameEvent.session_id == game_session.id)
                    .order_by(GameEvent.sequence_number)
                )
            ).all()
        )
        assert event_sequences == list(range(1, len(event_sequences) + 1))
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
@pytest.mark.postgres
async def test_expired_vote_poll_and_late_ballot_close_once(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(owner, test_session)
    expired_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        state = deepcopy(game_session.state)
        state["vote"] = {**state["vote"], "deadline_at": expired_at}
        game_session.state = state
        await session.commit()

    read_response, vote_response = await asyncio.gather(
        owner.get(f"/api/campaigns/{campaign['id']}/game"),
        _vote(clients[1], campaign["id"], story["north_choice_id"]),
    )

    assert read_response.status_code == 200
    assert read_response.json()["vote"]["status"] == "no_votes"
    assert vote_response.status_code == 409
    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        assert game_session.status == "running"
        assert game_session.current_node_id == story["initial_id"]
        assert game_session.state["vote"]["status"] == "no_votes"
        assert game_session.state["applied_consequences"] == []
        ballots = await session.scalar(
            select(func.count(StoryVote.id)).where(
                StoryVote.session_id == game_session.id,
                StoryVote.node_id == story["initial_id"],
                StoryVote.round_number == 1,
            )
        )
        assert ballots == 0
        events = list(
            (
                await session.scalars(
                    select(GameEvent)
                    .where(GameEvent.session_id == game_session.id)
                    .order_by(GameEvent.sequence_number)
                )
            ).all()
        )
        assert [event.sequence_number for event in events] == [1, 2]
        assert [event.event_type for event in events] == [
            "campaign_started",
            "vote_closed_without_votes",
        ]
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
@pytest.mark.postgres
async def test_duplicate_simultaneous_vote_creates_one_ballot_and_event(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(owner, test_session)
    responses = await asyncio.gather(
        _vote(clients[1], campaign["id"], story["north_choice_id"]),
        _vote(clients[1], campaign["id"], story["north_choice_id"]),
    )
    assert [response.status_code for response in responses] == [200, 200]
    voter_id = (await clients[1].get("/api/auth/session")).json()["id"]

    async with test_session() as session:
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        ballot_count = await session.scalar(
            select(func.count(StoryVote.id)).where(
                StoryVote.session_id == game_session.id,
                StoryVote.node_id == story["initial_id"],
                StoryVote.user_id == UUID(voter_id),
                StoryVote.round_number == 1,
            )
        )
        vote_event_count = await session.scalar(
            select(func.count(GameEvent.id)).where(
                GameEvent.session_id == game_session.id,
                GameEvent.event_type == "vote_cast",
                GameEvent.actor_user_id == UUID(voter_id),
            )
        )
        assert ballot_count == 1
        assert vote_event_count == 1
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
async def test_narrative_choice_grants_world_reward_to_active_characters_once(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    async with test_session() as session:
        item = Item(
            name="Poção da Vigília",
            category="consumable",
            rarity="common",
            is_active=True,
        )
        session.add(item)
        await session.flush()
        reward = WorldReward(
            title="Recompensa da Vigília",
            description="Concedida ao escolher a trilha.",
            xp=100,
            gold=25,
            item_ids=[str(item.id)],
            is_active=True,
        )
        session.add(reward)
        await session.commit()
        reward_id = reward.id
        item_id = item.id

    campaign, clients, story = await _prepare_game(
        owner,
        test_session,
        choice_consequences={"world_reward_ids": [str(reward_id)]},
    )
    responses = [
        await _vote(client, campaign["id"], story["north_choice_id"])
        for client in clients
    ]
    assert all(response.status_code == 200 for response in responses)

    game = await owner.get(f"/api/campaigns/{campaign['id']}/game")
    assert game.status_code == 200
    reward_events = [
        entry for entry in game.json()["history"] if entry["event_type"] == "rewards_granted"
    ]
    assert len(reward_events) == 1
    assert len(reward_events[0]["payload"]["rewards"]) == 3
    assert game.json()["last_result"]["rewards"][0]["xp"] == 100

    async with test_session() as session:
        characters = list(
            (
                await session.scalars(
                    select(Character).where(
                        Character.campaign_id == UUID(campaign["id"])
                    )
                )
            ).all()
        )
        assert len(characters) == 3
        assert all((character.level, character.xp, character.gold) == (2, 0, 25) for character in characters)
        grants = list(
            (
                await session.scalars(
                    select(CharacterRewardGrant).where(
                        CharacterRewardGrant.campaign_id == UUID(campaign["id"])
                    )
                )
            ).all()
        )
        assert len(grants) == 3
        assert all(grant.source_type == "narrative" for grant in grants)
        inventory = list(
            (
                await session.scalars(
                    select(CharacterItem).where(CharacterItem.item_id == item_id)
                )
            ).all()
        )
        assert len(inventory) == 3
        assert all(item.quantity == 1 for item in inventory)
        wallet_count = await session.scalar(
            select(func.count(WalletTransaction.id)).where(
                WalletTransaction.source_type == "narrative"
            )
        )
        assert wallet_count == 3
        reward_event_count = await session.scalar(
            select(func.count(GameEvent.id)).where(
                GameEvent.session_id == UUID(game.json()["session_id"]),
                GameEvent.event_type == "rewards_granted",
            )
        )
        assert reward_event_count == 1

    sheet = await owner.get(f"/api/campaigns/{campaign['id']}/character")
    history = sheet.json()["progression_history"]
    assert history[0]["source_type"] == "narrative"
    assert history[0]["source_id"] == str(reward_id)
    assert history[0]["source_name"] == "Recompensa da Vigília"
    assert history[0]["items"] == [
        {"item_id": str(item_id), "name": "Poção da Vigília", "quantity": 1}
    ]
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
async def test_narrative_reward_failure_rolls_back_the_whole_decision(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    async with test_session() as session:
        valid_reward = WorldReward(
            title="Recompensa válida",
            xp=40,
            is_active=True,
        )
        invalid_reward = WorldReward(
            title="Recompensa com item ausente",
            xp=60,
            item_ids=[str(uuid4())],
            is_active=True,
        )
        session.add_all([valid_reward, invalid_reward])
        await session.commit()
        reward_ids = [str(valid_reward.id), str(invalid_reward.id)]

    campaign, clients, story = await _prepare_game(
        owner,
        test_session,
        choice_consequences={"world_reward_ids": reward_ids},
    )
    await _vote(clients[0], campaign["id"], story["north_choice_id"])
    await _vote(clients[1], campaign["id"], story["north_choice_id"])
    failed_vote = await _vote(clients[2], campaign["id"], story["north_choice_id"])
    assert failed_vote.status_code == 422

    async with test_session() as session:
        characters = list(
            (
                await session.scalars(
                    select(Character).where(
                        Character.campaign_id == UUID(campaign["id"])
                    )
                )
            ).all()
        )
        assert all((character.level, character.xp) == (1, 0) for character in characters)
        assert await session.scalar(
            select(func.count(CharacterRewardGrant.id)).where(
                CharacterRewardGrant.campaign_id == UUID(campaign["id"])
            )
        ) == 0
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        assert game_session.state["vote"]["status"] == "open"
        assert await session.scalar(
            select(func.count(StoryVote.id)).where(
                StoryVote.session_id == game_session.id,
                StoryVote.round_number == 1,
            )
        ) == 2
        assert await session.scalar(
            select(func.count(GameEvent.id)).where(
                GameEvent.session_id == game_session.id,
                GameEvent.event_type == "decision_resolved",
            )
        ) == 0
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
async def test_simultaneous_final_votes_grant_one_reward_per_character(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    async with test_session() as session:
        reward = WorldReward(
            title="Recompensa simultânea",
            xp=50,
            gold=10,
            is_active=True,
        )
        session.add(reward)
        await session.commit()
        reward_id = reward.id

    campaign, clients, story = await _prepare_game(
        owner,
        test_session,
        choice_consequences={"world_reward_ids": [str(reward_id)]},
    )
    first_vote = await _vote(clients[0], campaign["id"], story["north_choice_id"])
    assert first_vote.status_code == 200
    responses = await asyncio.gather(
        _vote(clients[1], campaign["id"], story["north_choice_id"]),
        _vote(clients[2], campaign["id"], story["north_choice_id"]),
        return_exceptions=True,
    )
    assert all(not isinstance(response, Exception) for response in responses), responses

    async with test_session() as session:
        assert await session.scalar(
            select(func.count(CharacterRewardGrant.id)).where(
                CharacterRewardGrant.campaign_id == UUID(campaign["id"])
            )
        ) == 3
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        assert await session.scalar(
            select(func.count(GameEvent.id)).where(
                GameEvent.session_id == game_session.id,
                GameEvent.event_type == "decision_resolved",
            )
        ) == 1
        assert await session.scalar(
            select(func.count(GameEvent.id)).where(
                GameEvent.session_id == game_session.id,
                GameEvent.event_type == "rewards_granted",
            )
        ) == 1
        characters = list(
            (
                await session.scalars(
                    select(Character).where(
                        Character.campaign_id == UUID(campaign["id"])
                    )
                )
            ).all()
        )
        assert all((character.xp, character.gold) == (50, 10) for character in characters)
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
async def test_narrative_completes_only_assigned_campaign_quest_and_records_reward(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    async with test_session() as session:
        item = Item(
            name="Relíquia da missão",
            category="quest",
            rarity="rare",
            is_active=True,
        )
        session.add(item)
        await session.commit()
        item_id = item.id

    campaign, clients, story = await _prepare_game(owner, test_session)
    owner_character_id = UUID(campaign["members"][0]["character_id"])
    quest_id = uuid4()
    async with test_session() as session:
        quest = Quest(
            id=quest_id,
            campaign_id=UUID(campaign["id"]),
            title="Encontrar a relíquia",
            description="Conclua a escolha narrativa vinculada.",
            status="published",
            rewards={
                "xp": 100,
                "gold": 20,
                "items": [{"item_id": str(item_id), "quantity": 2}],
            },
        )
        session.add(quest)
        session.add(
            CharacterQuest(
                character_id=owner_character_id,
                quest_id=quest_id,
                status="in_progress",
                progress={"clues_found": 2},
            )
        )
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        state = deepcopy(game_session.state)
        scene = state["content_snapshot"][0]["scenes"][0]
        choice = next(
            entry
            for entry in scene["choices"]
            if entry["id"] == str(story["north_choice_id"])
        )
        choice["consequences"]["complete_quest_ids"] = [str(quest_id)]
        game_session.state = state
        await session.commit()

    for client in clients:
        response = await _vote(client, campaign["id"], story["north_choice_id"])
        assert response.status_code == 200, response.text

    async with test_session() as session:
        character_quest = await session.scalar(
            select(CharacterQuest).where(
                CharacterQuest.character_id == owner_character_id,
                CharacterQuest.quest_id == quest_id,
            )
        )
        assert character_quest is not None
        assert character_quest.status == "completed"
        assert character_quest.progress["clues_found"] == 2
        assert character_quest.progress["completion_idempotency_key"].startswith("quest:")
        assert await session.scalar(
            select(func.count(CharacterRewardGrant.id)).where(
                CharacterRewardGrant.campaign_id == UUID(campaign["id"])
            )
        ) == 1
        other_character_grants = await session.scalar(
            select(func.count(CharacterRewardGrant.id))
            .join(Character, Character.id == CharacterRewardGrant.character_id)
            .where(
                CharacterRewardGrant.campaign_id == UUID(campaign["id"]),
                Character.id != owner_character_id,
            )
        )
        assert other_character_grants == 0
        inventory = await session.scalar(
            select(CharacterItem).where(
                CharacterItem.character_id == owner_character_id,
                CharacterItem.item_id == item_id,
            )
        )
        assert inventory is not None
        assert inventory.quantity == 2

    game = await owner.get(f"/api/campaigns/{campaign['id']}/game")
    granted_event = next(
        event
        for event in game.json()["history"]
        if event["event_type"] == "rewards_granted"
    )
    assert granted_event["payload"]["rewards"][0]["source_type"] == "quest"
    assert granted_event["payload"]["rewards"][0]["items"] == [
        {"name": "Relíquia da missão", "quantity": 2}
    ]
    sheet = await owner.get(f"/api/campaigns/{campaign['id']}/character")
    assert sheet.json()["progression_history"][0]["source_type"] == "quest"
    assert sheet.json()["progression_history"][0]["source_id"] == str(quest_id)
    assert sheet.json()["progression_history"][0]["source_name"] == "Encontrar a relíquia"
    assert sheet.json()["progression_history"][0]["items"][0]["quantity"] == 2
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
async def test_narrative_objective_progress_is_server_recorded_and_required_for_completion(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(owner, test_session)
    owner_character_id = UUID(campaign["members"][0]["character_id"])
    quest_id = uuid4()
    async with test_session() as session:
        session.add(
            Quest(
                id=quest_id,
                campaign_id=UUID(campaign["id"]),
                title="Mapear a passagem",
                description="Registre os marcos da caverna.",
                status="published",
                conditions={
                    "objectives": [
                        {
                            "id": "map-markers",
                            "title": "Mapear marcos",
                            "description": "Marque dois pontos.",
                            "target": 2,
                        }
                    ],
                    "require_all_objectives": True,
                },
                rewards={"xp": 40, "gold": 0, "items": [], "skill_ids": []},
            )
        )
        session.add(
            CharacterQuest(
                character_id=owner_character_id,
                quest_id=quest_id,
                status="in_progress",
                progress={"objectives": {}},
            )
        )
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        state = deepcopy(game_session.state)
        scene = state["content_snapshot"][0]["scenes"][0]
        choice = next(
            entry
            for entry in scene["choices"]
            if entry["id"] == str(story["north_choice_id"])
        )
        choice["consequences"]["quest_objective_updates"] = [
            {"quest_id": str(quest_id), "objective_id": "map-markers", "amount": 2}
        ]
        choice["consequences"]["complete_quest_ids"] = [str(quest_id)]
        game_session.state = state
        await session.commit()

    for client in clients:
        response = await _vote(client, campaign["id"], story["north_choice_id"])
        assert response.status_code == 200, response.text

    async with test_session() as session:
        assignment = await session.scalar(
            select(CharacterQuest).where(
                CharacterQuest.character_id == owner_character_id,
                CharacterQuest.quest_id == quest_id,
            )
        )
        assert assignment is not None
        assert assignment.status == "completed"
        assert assignment.progress["objectives"]["map-markers"] == 2
        assert assignment.progress["completion_idempotency_key"].startswith("quest:")
        grants = list(
            (
                await session.scalars(
                    select(CharacterRewardGrant).where(
                        CharacterRewardGrant.character_id == owner_character_id
                    )
                )
            ).all()
        )
        assert len(grants) == 1
        assert grants[0].reward_payload["source_id"] == str(quest_id)

    sheet = await owner.get(f"/api/campaigns/{campaign['id']}/character")
    mission = sheet.json()["quests"][0]
    assert mission["status"] == "completed"
    assert mission["progress"]["objectives"]["map-markers"] == 2
    assert mission["objectives"][0]["target"] == 2
    assert sheet.json()["progression_history"][0]["xp_awarded"] == 40
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
async def test_narrative_cannot_complete_quest_before_required_objectives(
    auth_client: NarrativeTestClient,
) -> None:
    owner, test_session = auth_client
    campaign, clients, story = await _prepare_game(owner, test_session)
    owner_character_id = UUID(campaign["members"][0]["character_id"])
    quest_id = uuid4()
    async with test_session() as session:
        session.add(
            Quest(
                id=quest_id,
                campaign_id=UUID(campaign["id"]),
                title="Descobrir o selo",
                description="Encontre dois símbolos.",
                status="published",
                conditions={
                    "objectives": [
                        {
                            "id": "symbols",
                            "title": "Encontrar símbolos",
                            "description": "",
                            "target": 2,
                        }
                    ],
                    "require_all_objectives": True,
                },
                rewards={"xp": 50, "gold": 0, "items": [], "skill_ids": []},
            )
        )
        session.add(
            CharacterQuest(
                character_id=owner_character_id,
                quest_id=quest_id,
                status="in_progress",
                progress={"objectives": {"symbols": 1}},
            )
        )
        game_session = await session.scalar(
            select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
        )
        assert game_session is not None
        state = deepcopy(game_session.state)
        scene = state["content_snapshot"][0]["scenes"][0]
        choice = next(
            entry
            for entry in scene["choices"]
            if entry["id"] == str(story["north_choice_id"])
        )
        choice["consequences"]["complete_quest_ids"] = [str(quest_id)]
        game_session.state = state
        await session.commit()

    responses = []
    for client in clients:
        responses.append(await _vote(client, campaign["id"], story["north_choice_id"]))
    assert responses[-1].status_code == 409

    async with test_session() as session:
        assignment = await session.scalar(
            select(CharacterQuest).where(
                CharacterQuest.character_id == owner_character_id,
                CharacterQuest.quest_id == quest_id,
            )
        )
        assert assignment is not None
        assert assignment.status == "in_progress"
        assert assignment.progress["objectives"]["symbols"] == 1
        assert await session.scalar(
            select(func.count(CharacterRewardGrant.id)).where(
                CharacterRewardGrant.character_id == owner_character_id
            )
        ) == 0
    await asyncio.gather(*(client.aclose() for client in clients[1:]))


@pytest.mark.anyio
@pytest.mark.postgres
async def test_postgres_full_multiplayer_narrative_flow_and_campaign_isolation(
        auth_client: NarrativeTestClient,
) -> None:
        owner, test_session = auth_client
        campaign, clients, story = await _prepare_game(
            owner,
            test_session,
            max_players=5,
        )
        assert re.fullmatch(r"[0-9A-F]{32}", campaign["join_code"])
        non_owner_start = await clients[1].post(f"/api/campaigns/{campaign['id']}/start")
        assert non_owner_start.status_code == 403
        participant_responses = await asyncio.gather(
            *(client.get(f"/api/campaigns/{campaign['id']}/game") for client in clients)
        )
        assert all(response.status_code == 200 for response in participant_responses)
        games = [response.json() for response in participant_responses]
        assert len({game["session_id"] for game in games}) == 1
        assert all(game["scene"]["id"] == str(story["initial_id"]) for game in games)
        assert all(len(game["participants"]) == 5 for game in games)

        owner_id = (await owner.get("/api/auth/session")).json()["id"]
        lobby = await owner.get(f"/api/campaigns/{campaign['id']}")
        assert lobby.status_code == 200
        member_ids = {member["user_id"] for member in lobby.json()["members"]}
        assert owner_id in member_ids
        character_ids = [member["character_id"] for member in lobby.json()["members"]]
        assert all(character_ids)
        assert len(set(character_ids)) == 5

        returning_client = clients[1]
        before_leave = await returning_client.get(f"/api/campaigns/{campaign['id']}")
        returning_user_id = (await returning_client.get("/api/auth/session")).json()["id"]
        returning_member = next(
            member
            for member in before_leave.json()["members"]
            if member["user_id"] == returning_user_id
        )
        left = await returning_client.post(f"/api/campaigns/{campaign['id']}/leave")
        assert left.status_code == 204
        assert (await returning_client.get(f"/api/campaigns/{campaign['id']}")).status_code == 404
        rejoined = await returning_client.post(
            "/api/campaigns/join",
            json={"code": campaign["join_code"]},
        )
        assert rejoined.status_code == 200
        rejoined_member = next(
            member
            for member in rejoined.json()["members"]
            if member["user_id"] == returning_member["user_id"]
        )
        assert rejoined_member["character_id"] == returning_member["character_id"]

        second_campaign_response = await owner.post(
            "/api/campaigns",
            json={"title": "Campanha isolada", "max_players": 3},
        )
        assert second_campaign_response.status_code == 201
        second_campaign = second_campaign_response.json()
        for client in clients[1:3]:
            joined = await client.post(
                "/api/campaigns/join",
                json={"code": second_campaign["join_code"]},
            )
            assert joined.status_code == 201
        second_start = await owner.post(f"/api/campaigns/{second_campaign['id']}/start")
        assert second_start.status_code == 200
        second_game = await owner.get(f"/api/campaigns/{second_campaign['id']}/game")
        assert second_game.status_code == 200
        assert second_game.json()["session_id"] != games[0]["session_id"]
        assert second_game.json()["scene"]["id"] == str(story["initial_id"])
        assert second_game.json()["vote"]["voted_count"] == 0

        votes = [
            (clients[index], story["north_choice_id"] if index < 3 else story["south_choice_id"])
            for index in range(5)
        ]
        vote_responses = [
            await _vote(client, campaign["id"], choice_id)
            for client, choice_id in votes
        ]
        assert all(response.status_code == 200 for response in vote_responses)
        resolved_game = vote_responses[-1].json()
        assert resolved_game["scene"]["id"] == str(story["north_id"])
        assert resolved_game["last_result"]["choice_id"] == str(story["north_choice_id"])
        assert sum(
            event["event_type"] == "decision_resolved"
            for event in resolved_game["history"]
        ) == 1

        async with test_session() as session:
            game_session = await session.scalar(
                select(GameSession).where(GameSession.campaign_id == UUID(campaign["id"]))
            )
            isolated_session = await session.scalar(
                select(GameSession).where(
                    GameSession.campaign_id == UUID(second_campaign["id"])
                )
            )
            assert game_session is not None and isolated_session is not None
            assert game_session.id != isolated_session.id
            assert game_session.current_node_id == story["north_id"]
            assert isolated_session.current_node_id == story["initial_id"]
            assert len(game_session.state["applied_consequences"]) == 1
            decision_count = await session.scalar(
                select(func.count(GameEvent.id)).where(
                    GameEvent.session_id == game_session.id,
                    GameEvent.event_type == "decision_resolved",
                )
            )
            assert decision_count == 1
            active_members = list(
                (
                    await session.scalars(
                        select(CampaignMember).where(
                            CampaignMember.campaign_id == UUID(campaign["id"]),
                            CampaignMember.status == "active",
                        )
                    )
                ).all()
            )
            assert len(active_members) == 5

        outsider = await _new_player("NarrativeOutsider", client_host="192.0.2.100")
        assert (
            await outsider.get(f"/api/campaigns/{campaign['id']}/game")
        ).status_code == 404
        await outsider.aclose()
        await asyncio.gather(*(client.aclose() for client in clients[1:]))
