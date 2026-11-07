import struct
import zlib
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import dependencies as api_dependencies
from app.core.security import hash_password
from app.models import (
    Campaign,
    CampaignMember,
    CharacterQuest,
    Character,
    CharacterItem,
    Chapter,
    Enemy,
    GameSession,
    Item,
    NpcDialogue,
    Quest,
    Skill,
    StoryChoice,
    StoryNode,
    StoryVote,
    WalletTransaction,
    WorldSetting,
    User,
)

AdminTestClient = tuple[AsyncClient, async_sessionmaker[AsyncSession]]


async def login_admin(
    client: AsyncClient,
    test_session: async_sessionmaker[AsyncSession],
) -> UUID:
    admin_id = uuid4()
    async with test_session() as session:
        session.add(
            User(
                id=admin_id,
                username="ContentAdmin",
                username_key="contentadmin",
                email=None,
                password_hash=hash_password("a-long-admin-password-2026"),
                display_name="Content Admin",
                is_admin=True,
                status="active",
            )
        )
        await session.commit()
    response = await client.post(
        "/api/auth/admin/login",
        json={"username": "ContentAdmin", "password": "a-long-admin-password-2026"},
    )
    assert response.status_code == 200
    return admin_id


def _png_chunk(kind: bytes, body: bytes) -> bytes:
    return (
        struct.pack(">I", len(body))
        + kind
        + body
        + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    )


def one_pixel_png() -> bytes:
    header = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(b"\x00\x00"))
        + _png_chunk(b"IEND", b"")
    )


def chapter_payload(chapter: dict, scenes: list[dict] | None = None) -> dict:
    return {
        key: chapter[key]
        for key in ("title", "summary", "narrative", "position", "status", "is_active", "npc_ids", "enemy_ids")
    } | {"scenes": scenes if scenes is not None else chapter["scenes"]}


@pytest.mark.anyio
async def test_story_crud_ordering_and_choice_data_are_persisted(
    auth_client: AdminTestClient,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    chapter_id = uuid4()
    scene_one_id, scene_two_id = uuid4(), uuid4()
    choice_id = uuid4()
    create = await client.post(
        "/api/admin/content/chapters",
        json={
            "title": "A travessia",
            "summary": "Resumo",
            "narrative": "Texto do capítulo",
            "position": 0,
            "status": "published",
            "is_active": True,
            "npc_ids": [],
            "enemy_ids": [],
            "scenes": [
                {
                    "id": str(scene_one_id),
                    "title": "A ponte",
                    "narrative": "A névoa cobre o rio.",
                    "position": 0,
                    "dialogues": [{"speaker": "Guarda", "line": "Quem vem lá?"}],
                    "choices": [
                        {
                            "id": str(choice_id),
                            "label": "Atravessar",
                            "next_node_id": str(scene_two_id),
                            "position": 0,
                            "conditions": {"reputation": ">= 1"},
                            "consequences": {"flag": "river_crossed"},
                        }
                    ],
                    "npc_ids": [],
                    "enemy_ids": [],
                    "conditions": {},
                },
                {
                    "id": str(scene_two_id),
                    "title": "A outra margem",
                    "position": 1,
                    "dialogues": [],
                    "choices": [],
                    "npc_ids": [],
                    "enemy_ids": [],
                    "conditions": {},
                },
            ],
        },
    )
    assert create.status_code == 201, create.text
    chapter_id = UUID(create.json()["id"])
    assert [scene["title"] for scene in create.json()["scenes"]] == [
        "A ponte",
        "A outra margem",
    ]
    assert create.json()["scenes"][0]["choices"][0]["id"] == str(choice_id)

    updated = await client.put(
        f"/api/admin/content/chapters/{chapter_id}",
        json={
            **chapter_payload(create.json(), [
                {
                    **create.json()["scenes"][1],
                    "position": 0,
                },
                {
                    **create.json()["scenes"][0],
                    "position": 1,
                },
            ]),
        },
    )
    assert updated.status_code == 200, updated.text
    assert [scene["title"] for scene in updated.json()["scenes"]] == [
        "A outra margem",
        "A ponte",
    ]
    assert updated.json()["scenes"][1]["choices"][0]["conditions"] == {
        "reputation": ">= 1"
    }

    async with test_session() as session:
        chapter = await session.get(Chapter, chapter_id)
        nodes = list(
            (
                await session.scalars(
                    select(StoryNode).where(StoryNode.chapter_id == chapter_id)
                )
            ).all()
        )
        stored_choice = await session.get(StoryChoice, choice_id)
        assert chapter is not None and chapter.campaign_id is None
        assert sorted(node.position for node in nodes) == [0, 1]
        assert stored_choice is not None
        assert stored_choice.consequences == {"flag": "river_crossed"}


@pytest.mark.anyio
async def test_admin_auth_blocks_players_and_unauthenticated_requests(
    auth_client: AdminTestClient,
) -> None:
    client, test_session = auth_client
    assert (await client.get("/api/admin/content/chapters")).status_code == 401
    await client.post(
        "/api/auth/register",
        json={"username": "RegularPlayer", "password": "strong-player-password-2026"},
    )
    assert (await client.get("/api/admin/content/chapters")).status_code == 401
    assert (
        await client.post(
            "/api/admin/content/items",
            json={"name": "Espada", "category": "weapon"},
        )
    ).status_code == 401

    await client.post("/api/auth/logout")
    assert (await login_admin(client, test_session)) is not None
    forbidden_player_login = await client.post(
        "/api/auth/admin/login",
        json={"username": "RegularPlayer", "password": "not-an-admin-password"},
    )
    assert forbidden_player_login.status_code == 401
    assert (await client.get("/api/admin/content/chapters")).status_code == 200
    assert (await client.get("/api/admin/content/quests")).status_code == 200


@pytest.mark.anyio
async def test_admin_manages_publishes_and_assigns_campaign_quests(
    auth_client: AdminTestClient,
) -> None:
    client, test_session = auth_client
    admin_id = await login_admin(client, test_session)
    owner_id = uuid4()
    second_owner_id = uuid4()
    outsider_owner_id = uuid4()
    character_ids = [uuid4(), uuid4()]
    outsider_character_id = uuid4()
    item_id = uuid4()
    skill_id = uuid4()
    async with test_session() as session:
        owner = User(
            id=owner_id,
            username="QuestOwner",
            username_key="questowner",
            email=None,
            password_hash=hash_password("strong-owner-password-2026"),
            display_name="Quest Owner",
            is_admin=False,
            status="active",
        )
        second_owner = User(
            id=second_owner_id,
            username="QuestPlayerTwo",
            username_key="questplayertwo",
            email=None,
            password_hash=hash_password("strong-owner-password-2026"),
            display_name="Quest Player Two",
            is_admin=False,
            status="active",
        )
        outsider_owner = User(
            id=outsider_owner_id,
            username="QuestOutsider",
            username_key="questoutsider",
            email=None,
            password_hash=hash_password("strong-owner-password-2026"),
            display_name="Quest Outsider",
            is_admin=False,
            status="active",
        )
        campaign = Campaign(
            owner_id=owner_id,
            title="Campanha da missão",
            description="",
            status="waiting",
            visibility="private",
            min_players=3,
            max_players=5,
            join_code="RZ-12345",
        )
        other_campaign = Campaign(
            owner_id=outsider_owner_id,
            title="Outra campanha",
            description="",
            status="waiting",
            visibility="private",
            min_players=3,
            max_players=5,
            join_code="RZ-54321",
        )
        session.add_all([owner, second_owner, outsider_owner, campaign, other_campaign])
        await session.flush()
        for index, character_id in enumerate(character_ids):
            character_owner_id = owner_id if index == 0 else second_owner_id
            character = Character(
                id=character_id,
                owner_id=character_owner_id,
                campaign_id=campaign.id,
                name=f"Personagem {index + 1}",
                status="active",
            )
            session.add(character)
            session.add(
                CampaignMember(
                    campaign_id=campaign.id,
                    user_id=character_owner_id,
                    character_id=character_id,
                    role="player",
                    status="active",
                )
            )
        await session.flush()
        outsider_character = Character(
            id=outsider_character_id,
            owner_id=outsider_owner_id,
            campaign_id=other_campaign.id,
            name="Personagem de outra campanha",
            status="active",
        )
        session.add(outsider_character)
        session.add(
            CampaignMember(
                campaign_id=other_campaign.id,
                user_id=outsider_owner_id,
                character_id=outsider_character_id,
                role="player",
                status="active",
            )
        )
        item = Item(
            id=item_id,
            name="Poção de teste",
            category="consumable",
            is_active=True,
        )
        skill = Skill(
            id=skill_id,
            name="Escudo de teste",
            category="suporte",
            is_active=True,
            status="published",
        )
        session.add_all([item, skill])
        await session.commit()
        campaign_id = campaign.id

    payload = {
        "campaign_id": str(campaign_id),
        "title": "Resgatar o cartógrafo",
        "description": "Encontre a torre.",
        "status": "draft",
        "conditions": {
            "objectives": [
                {
                    "id": "find-tower",
                    "title": "Encontrar a torre",
                    "description": "Siga as pistas.",
                    "target": 2,
                }
            ],
            "require_all_objectives": True,
        },
        "rewards": {
            "xp": 80,
            "gold": 12,
            "items": [{"item_id": str(item_id), "quantity": 1}],
            "skill_ids": [str(skill_id)],
        },
    }
    await client.post("/api/auth/admin/logout")
    unauthorized = await client.post("/api/admin/content/quests", json=payload)
    assert unauthorized.status_code == 401
    admin_login = await client.post(
        "/api/auth/admin/login",
        json={"username": "ContentAdmin", "password": "a-long-admin-password-2026"},
    )
    assert admin_login.status_code == 200
    created = await client.post("/api/admin/content/quests", json=payload)
    assert created.status_code == 201, created.text
    quest_id = created.json()["id"]
    assert created.json()["status"] == "draft"

    published = await client.put(
        f"/api/admin/content/quests/{quest_id}",
        json={**payload, "status": "published", "title": "Resgatar o cartógrafo revisada"},
    )
    assert published.status_code == 200, published.text
    assert published.json()["title"] == "Resgatar o cartógrafo revisada"
    targets = await client.get(
        "/api/admin/content/quests/targets",
        params={"campaign_id": str(campaign_id)},
    )
    assert targets.status_code == 200
    assert {target["id"] for target in targets.json()} == {
        str(character_id) for character_id in character_ids
    }
    assigned = await client.post(
        f"/api/admin/content/quests/{quest_id}/assign",
        json={"character_ids": [str(character_id) for character_id in character_ids]},
    )
    assert assigned.status_code == 200, assigned.text
    assert {entry["character_id"] for entry in assigned.json()["assignments"]} == {
        str(character_id) for character_id in character_ids
    }
    assert all(entry["status"] == "available" for entry in assigned.json()["assignments"])
    cross_campaign = await client.post(
        f"/api/admin/content/quests/{quest_id}/assign",
        json={"character_ids": [str(character_ids[0]), str(outsider_character_id)]},
    )
    assert cross_campaign.status_code == 422
    repeated = await client.post(
        f"/api/admin/content/quests/{quest_id}/assign",
        json={"character_ids": [str(character_id) for character_id in character_ids]},
    )
    assert repeated.status_code == 200
    unpublished = await client.put(
        f"/api/admin/content/quests/{quest_id}",
        json={**payload, "status": "inactive", "title": "Resgatar o cartógrafo revisada"},
    )
    assert unpublished.status_code == 200, unpublished.text
    assert unpublished.json()["status"] == "inactive"
    assert len(unpublished.json()["assignments"]) == 2
    async with test_session() as session:
        assignments = list(
            (
                await session.scalars(
                    select(CharacterQuest).where(CharacterQuest.quest_id == UUID(quest_id))
                )
            ).all()
        )
        mission = await session.get(Quest, UUID(quest_id))
        assert len(assignments) == 2
        assert mission is not None and mission.status == "inactive"
        assert all(
            assignment.progress["reward_snapshot"]["xp"] == 80
            and assignment.progress["conditions_snapshot"]["objectives"][0]["id"]
            == "find-tower"
            for assignment in assignments
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    [
        "/api/content/chapters",
        "/api/content/items",
        "/api/content/monsters",
        "/api/content/skills",
        "/api/content/npcs",
    ],
)
async def test_published_content_requires_a_player_session(
    auth_client: AdminTestClient,
    path: str,
) -> None:
    client, _ = auth_client

    unauthenticated = await client.get(path)
    registered = await client.post(
        "/api/auth/register",
        json={"username": "PublishedContentPlayer", "password": "strong-player-password-2026"},
    )
    published = await client.get(path)

    assert unauthenticated.status_code == 401
    assert unauthenticated.json() == {"detail": "Autenticação necessária."}
    assert registered.status_code == 201
    assert published.status_code == 200
    assert published.json() == []


@pytest.mark.anyio
async def test_admin_chapter_creation_rejects_disallowed_origin_without_writing(
    auth_client: AdminTestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    monkeypatch.setattr(
        api_dependencies,
        "get_settings",
        lambda: SimpleNamespace(frontend_origins=["https://trusted.example"]),
    )

    response = await client.post(
        "/api/admin/content/chapters",
        json={"title": "Origem não autorizada", "position": 0},
        headers={"Origin": "https://untrusted.example"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Origem da solicitação não autorizada."}
    assert (await client.get("/api/admin/content/chapters")).json() == []


@pytest.mark.anyio
async def test_admin_can_delete_an_unreferenced_chapter(
    auth_client: AdminTestClient,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    created = await client.post(
        "/api/admin/content/chapters",
        json={
            "title": "Capítulo removível",
            "position": 0,
            "scenes": [],
        },
    )
    assert created.status_code == 201, created.text
    chapter_id = created.json()["id"]

    deleted = await client.delete(f"/api/admin/content/chapters/{chapter_id}")

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert all(
        chapter["id"] != chapter_id
        for chapter in (await client.get("/api/admin/content/chapters")).json()
    )


@pytest.mark.anyio
async def test_admin_items_monsters_drops_and_png_upload(
    auth_client: AdminTestClient,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    item = await client.post(
        "/api/admin/content/items",
        json={
            "name": "Lâmina de teste",
            "description": "Uma espada.",
            "category": "arma",
            "is_career": True,
            "rarity": "raro",
            "price": 120,
            "weight": 4,
            "attributes": {"attack": 3},
            "requirements": {"level": 2},
            "stock": 5,
            "usage": "Equipável",
            "effects": {},
        },
    )
    assert item.status_code == 201, item.text
    assert item.json()["category"] == "arma"
    assert item.json()["is_career"] is True
    assert item.json()["requirements"] == {"level": 2, "is_career": True}
    item_id = UUID(item.json()["id"])
    changed = await client.put(
        f"/api/admin/content/items/{item_id}",
        json={
            key: value
            for key, value in {
                **item.json(),
                "name": "Espada testada",
                "price": 150,
            }.items()
            if key != "id"
        },
    )
    assert changed.status_code == 200
    assert changed.json()["name"] == "Espada testada"
    assert changed.json()["price"] == 150

    image = await client.post(
        "/api/admin/content/monsters/images",
        content=one_pixel_png(),
        headers={"Content-Type": "image/png"},
    )
    assert image.status_code == 200, image.text
    assert image.json()["content_type"] == "image/png"
    image_name = image.json()["url"].rsplit("/", maxsplit=1)[-1]
    image_file = Path(__file__).resolve().parents[1] / "uploads" / "monsters" / image_name
    try:
        assert image_file.is_file()
        image_read = await client.get(image.json()["url"])
        assert image_read.status_code == 200
        assert image_read.content == one_pixel_png()
    finally:
        image_file.unlink(missing_ok=True)

    invalid_image = await client.post(
        "/api/admin/content/monsters/images",
        content=b"not a png",
        headers={"Content-Type": "image/png"},
    )
    assert invalid_image.status_code == 422
    wrong_type = await client.post(
        "/api/admin/content/monsters/images",
        content=one_pixel_png(),
        headers={"Content-Type": "image/jpeg"},
    )
    assert wrong_type.status_code == 415

    monster = await client.post(
        "/api/admin/content/monsters",
        json={
            "name": "Lobo de teste",
            "hp": 30,
            "image_url": image.json()["url"],
            "abilities": ["Mordida"],
            "resistances": ["frio"],
            "weaknesses": ["fogo"],
            "difficulty": "easy",
            "appearance_chance": 5000,
            "xp_reward": 20,
        },
    )
    assert monster.status_code == 201, monster.text
    monster_id = UUID(monster.json()["id"])
    drop = await client.post(
        "/api/admin/content/drops",
        json={
            "enemy_id": str(monster_id),
            "item_id": str(item_id),
            "chance_basis_points": 2500,
            "min_quantity": 1,
            "max_quantity": 3,
        },
    )
    assert drop.status_code == 201, drop.text
    assert drop.json()["chance"] == 25
    assert drop.json()["max_quantity"] == 3
    updated_drop = await client.put(
        f"/api/admin/content/drops/{drop.json()['id']}",
        json={
            "enemy_id": str(monster_id),
            "item_id": str(item_id),
            "chance_basis_points": 5000,
            "min_quantity": 2,
            "max_quantity": 4,
        },
    )
    assert updated_drop.status_code == 200
    assert updated_drop.json()["chance"] == 50
    assert updated_drop.json()["min_quantity"] == 2
    assert updated_drop.json()["max_quantity"] == 4

    async with test_session() as session:
        assert await session.get(Item, item_id) is not None
        assert await session.get(Enemy, monster_id) is not None


@pytest.mark.anyio
async def test_npc_skill_settings_rewards_and_transactions_are_persisted(
    auth_client: AdminTestClient,
) -> None:
    client, test_session = auth_client
    admin_id = await login_admin(client, test_session)

    npc_payload = {
        "name": "A cartógrafa",
        "description": "Conhece as rotas do norte.",
        "personality": "Pragmática",
        "story_role": "Informante",
        "status": "published",
        "player_relations": [{"player_id": str(admin_id), "relationship": "Aliada"}],
        "dialogues": [{"speaker": "Cartógrafa", "line": "A estrada mudou."}],
    }
    npc = await client.post("/api/admin/content/npcs", json=npc_payload)
    assert npc.status_code == 201, npc.text
    npc_id = UUID(npc.json()["id"])
    assert npc.json()["dialogues"][0]["line"] == "A estrada mudou."
    updated_npc = await client.put(
        f"/api/admin/content/npcs/{npc_id}",
        json={**npc_payload, "name": "A velha cartógrafa"},
    )
    assert updated_npc.status_code == 200
    assert updated_npc.json()["name"] == "A velha cartógrafa"

    skill = await client.post(
        "/api/admin/content/skills",
        json={
            "name": "Barreira de vento",
            "category": "vento",
            "description": "Protege um aliado.",
            "mana_cost": 4,
            "effects": {"armor": 2},
            "target": "aliado",
            "requirements": {"level": 2},
            "cooldown_seconds": 1,
            "status": "published",
            "is_career": True,
        },
    )
    assert skill.status_code == 201, skill.text
    assert skill.json()["category"] == "vento"
    assert skill.json()["is_career"] is True
    assert skill.json()["requirements"] == {"level": 2, "is_career": True}
    updated_skill = await client.put(
        f"/api/admin/content/skills/{skill.json()['id']}",
        json={
            "name": "Barreira de vento",
            "category": "vento",
            "description": "Protege dois aliados.",
            "mana_cost": 5,
            "effects": {"armor": 3},
            "target": "area",
            "requirements": {"level": 3},
            "cooldown_seconds": 2,
            "status": "published",
            "is_career": True,
        },
    )
    assert updated_skill.status_code == 200
    assert updated_skill.json()["mana_cost"] == 5
    assert updated_skill.json()["is_career"] is True

    economy = {"coins": ["ouro", "prata"], "purchase_markup_percent": 10}
    saved_economy = await client.put(
        "/api/admin/content/economy/config", json={"value": economy}
    )
    assert saved_economy.status_code == 200
    assert (await client.get("/api/admin/content/economy/config")).json() == economy
    await client.put(
        "/api/admin/content/settings/universe",
        json={"value": {"name": "As Marcas", "calendar": {"days_per_month": 28}}},
    )
    assert (
        await client.get("/api/admin/content/settings/universe")
    ).json()["name"] == "As Marcas"

    reward = await client.post(
        "/api/admin/content/rewards",
        json={"title": "Resgate", "gold": 25, "xp": 10, "item_ids": []},
    )
    assert reward.status_code == 201, reward.text
    changed_reward = await client.put(
        f"/api/admin/content/rewards/{reward.json()['id']}",
        json={
            "title": "Resgate atualizado",
            "description": "Recompensa de teste.",
            "gold": 30,
            "xp": 15,
            "item_ids": [],
            "is_active": True,
        },
    )
    assert changed_reward.status_code == 200
    assert changed_reward.json()["gold"] == 30

    async with test_session() as session:
        session.add(Character(owner_id=admin_id, name="Personagem de teste"))
        await session.commit()
        character_id = await session.scalar(
            select(Character.id).where(Character.owner_id == admin_id)
        )
    assert character_id is not None
    transaction = await client.post(
        "/api/admin/content/transactions",
        json={
            "character_id": str(character_id),
            "kind": "reward",
            "description": "Bônus de missão",
            "amount": 20,
        },
    )
    assert transaction.status_code == 201, transaction.text
    async with test_session() as session:
        stored_transaction = await session.get(WalletTransaction, UUID(transaction.json()["id"]))
        assert stored_transaction is not None
        assert stored_transaction.amount == 20
        stored_economy = await session.get(WorldSetting, "economy")
        assert stored_economy is not None
        assert stored_economy.value == economy
        dialogue = await session.scalar(
            select(NpcDialogue).where(NpcDialogue.npc_id == npc_id)
        )
        assert dialogue is not None


@pytest.mark.anyio
async def test_editing_an_owned_item_creates_a_new_version(
    auth_client: AdminTestClient,
) -> None:
    client, test_session = auth_client
    admin_id = await login_admin(client, test_session)
    created = await client.post(
        "/api/admin/content/items",
        json={"name": "Elixir histórico", "category": "consumivel", "price": 5},
    )
    assert created.status_code == 201, created.text
    old_item_id = UUID(created.json()["id"])
    async with test_session() as session:
        character = Character(owner_id=admin_id, name="Guardião")
        session.add(character)
        await session.flush()
        session.add(CharacterItem(character_id=character.id, item_id=old_item_id, quantity=1))
        await session.commit()

    payload = {key: value for key, value in created.json().items() if key != "id"}
    payload.update({"name": "Elixir renovado", "price": 8})
    changed = await client.put(f"/api/admin/content/items/{old_item_id}", json=payload)
    assert changed.status_code == 200, changed.text
    new_item_id = UUID(changed.json()["id"])
    assert new_item_id != old_item_id

    async with test_session() as session:
        old_item = await session.get(Item, old_item_id)
        new_item = await session.get(Item, new_item_id)
        owned_item = await session.scalar(
            select(CharacterItem).where(CharacterItem.character_id == character.id)
        )
        assert old_item is not None and old_item.is_active is False
        assert new_item is not None and new_item.previous_version_id == old_item_id
        assert owned_item is not None and owned_item.item_id == old_item_id


@pytest.mark.anyio
async def test_editing_choice_with_recorded_vote_and_deleting_progressed_chapter_are_blocked(
    auth_client: AdminTestClient,
) -> None:
    client, test_session = auth_client
    admin_id = await login_admin(client, test_session)
    scene_id, destination_id, choice_id = uuid4(), uuid4(), uuid4()
    chapter_response = await client.post(
        "/api/admin/content/chapters",
        json={
            "title": "Capítulo com decisões",
            "position": 0,
            "scenes": [
                {
                    "id": str(scene_id),
                    "title": "Bifurcação",
                    "position": 0,
                    "choices": [
                        {
                            "id": str(choice_id),
                            "label": "Escolha original",
                            "next_node_id": str(destination_id),
                            "position": 0,
                        }
                    ],
                },
                {
                    "id": str(destination_id),
                    "title": "Destino",
                    "position": 1,
                },
            ],
        },
    )
    assert chapter_response.status_code == 201, chapter_response.text
    chapter_id = UUID(chapter_response.json()["id"])

    async with test_session() as session:
        campaign = Campaign(
            owner_id=admin_id,
            title="Campanha existente",
            description="",
            status="active",
            visibility="private",
            min_players=3,
            max_players=5,
            join_code="RZ-10001",
            current_chapter_id=chapter_id,
            current_node_id=scene_id,
            settings={},
        )
        session.add(campaign)
        await session.flush()
        game_session = GameSession(
            campaign_id=campaign.id,
            current_node_id=scene_id,
            status="active",
            state={},
        )
        session.add(game_session)
        await session.flush()
        session.add(
            StoryVote(
                session_id=game_session.id,
                node_id=scene_id,
                choice_id=choice_id,
                user_id=admin_id,
                round_number=1,
            )
        )
        await session.commit()

    original = chapter_response.json()
    altered_scene = {
        **original["scenes"][0],
        "choices": [{**original["scenes"][0]["choices"][0], "label": "Escolha alterada"}],
    }
    edit = await client.put(
        f"/api/admin/content/chapters/{chapter_id}",
        json=chapter_payload(original, [altered_scene, original["scenes"][1]]),
    )
    assert edit.status_code == 409
    delete_chapter = await client.delete(f"/api/admin/content/chapters/{chapter_id}")
    assert delete_chapter.status_code == 409

    async with test_session() as session:
        stored = await session.get(StoryChoice, choice_id)
        assert stored is not None and stored.label == "Escolha original"


@pytest.mark.anyio
async def test_admin_can_delete_unreferenced_content_and_deactivate_rewards(
    auth_client: AdminTestClient,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    npc = await client.post(
        "/api/admin/content/npcs",
        json={"name": "NPC removível"},
    )
    item = await client.post(
        "/api/admin/content/items",
        json={"name": "Item removível", "category": "weapon"},
    )
    monster = await client.post(
        "/api/admin/content/monsters",
        json={"name": "Monstro removível", "hp": 10},
    )
    skill = await client.post(
        "/api/admin/content/skills",
        json={"name": "Habilidade removível", "category": "vento"},
    )
    reward = await client.post(
        "/api/admin/content/rewards",
        json={"title": "Recompensa removível"},
    )
    assert npc.status_code == 201, npc.text
    assert item.status_code == 201, item.text
    assert monster.status_code == 201, monster.text
    assert skill.status_code == 201, skill.text
    assert reward.status_code == 201, reward.text

    drop = await client.post(
        "/api/admin/content/drops",
        json={
            "enemy_id": monster.json()["id"],
            "item_id": item.json()["id"],
            "chance_basis_points": 1000,
        },
    )
    assert drop.status_code == 201, drop.text

    results = [
        await client.delete(f"/api/admin/content/npcs/{npc.json()['id']}"),
        await client.delete(f"/api/admin/content/drops/{drop.json()['id']}"),
        await client.delete(f"/api/admin/content/items/{item.json()['id']}"),
        await client.delete(f"/api/admin/content/monsters/{monster.json()['id']}"),
        await client.delete(f"/api/admin/content/skills/{skill.json()['id']}"),
        await client.delete(f"/api/admin/content/rewards/{reward.json()['id']}"),
    ]

    assert [response.status_code for response in results] == [204] * 6
    assert all(
        response.content == b""
        for response in results
    )
    assert (await client.get("/api/admin/content/npcs")).json() == []
    assert (await client.get("/api/admin/content/drops")).json() == []
    assert (await client.get("/api/admin/content/items")).json() == []
    assert (await client.get("/api/admin/content/monsters")).json() == []
    assert (await client.get("/api/admin/content/skills")).json() == []
    rewards = (await client.get("/api/admin/content/rewards")).json()
    assert len(rewards) == 1
    assert rewards[0]["id"] == reward.json()["id"]
    assert rewards[0]["is_active"] is False
