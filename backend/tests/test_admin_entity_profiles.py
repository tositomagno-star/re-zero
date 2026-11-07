from io import BytesIO
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import admin_entity_profiles
from app.core.security import hash_password
from app.models import Asset, Enemy, EntityContentProfile, EntityContentSkillAssociation, User
from app.schemas.entity_profiles import EnemyContentSettings, SkillContentSettings

AdminTestClient = tuple[AsyncClient, async_sessionmaker[AsyncSession]]


def test_impossible_boss_allows_multiple_attacks_and_interruptions() -> None:
    settings = EnemyContentSettings(
        category="boss",
        boss_difficulty="impossible",
        max_attacks_per_turn=2,
        can_interrupt_turns=True,
    )

    assert settings.boss_difficulty == "impossible"
    assert settings.max_attacks_per_turn == 2
    assert settings.can_interrupt_turns is True


def test_skill_profile_damage_override_is_optional() -> None:
    settings = SkillContentSettings.model_validate({"skill_type": "physical"})

    assert settings.damage_base is None


async def login_admin(
    client: AsyncClient,
    test_session: async_sessionmaker[AsyncSession],
) -> None:
    async with test_session() as session:
        session.add(
            User(
                id=uuid4(),
                username="ProfileAdmin",
                username_key="profileadmin",
                email=None,
                password_hash=hash_password("a-long-admin-password-2026"),
                display_name="Profile Admin",
                is_admin=True,
                status="active",
            )
        )
        await session.commit()
    response = await client.post(
        "/api/auth/admin/login",
        json={"username": "ProfileAdmin", "password": "a-long-admin-password-2026"},
    )
    assert response.status_code == 200


async def create_enemy(client: AsyncClient) -> str:
    response = await client.post(
        "/api/admin/content/monsters",
        json={"name": "Sentinela de teste", "hp": 80, "is_active": False},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.anyio
async def test_entity_profile_is_validated_and_persisted_after_reload(
    auth_client: AdminTestClient,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    enemy_id = await create_enemy(client)
    payload = {
        "kind": "boss",
        "availability": "draft",
        "scale": 1.4,
        "orientation": "left",
        "default_position": {"x": 0.9, "y": 0.5},
        "attributes": {"resistance": 15},
        "settings": {
            "category": "boss",
            "default_attack_speed": 1.2,
            "gold_reward": 30,
            "special_rewards": [],
            "boss_difficulty": "hard",
            "max_attacks_per_turn": 2,
            "can_interrupt_turns": True,
            "strategy": "aggressive",
            "attack_release_delay_ms": 1200,
            "attack_animation_duration_ms": 900,
        },
        "assets": [],
        "animations": [],
        "skills": [],
        "equipment_ids": [],
    }

    saved = await client.put(
        f"/api/admin/content/profiles/enemy/{enemy_id}",
        json=payload,
    )
    assert saved.status_code == 200, saved.text
    profile_id = saved.json()["id"]

    reloaded = await client.get(
        f"/api/admin/content/profiles/lookup/enemy/{enemy_id}",
    )
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["id"] == profile_id
    assert reloaded.json()["settings"]["category"] == "boss"
    assert reloaded.json()["settings"]["boss_difficulty"] == "hard"
    assert reloaded.json()["settings"]["max_attacks_per_turn"] == 2
    assert reloaded.json()["settings"]["can_interrupt_turns"] is True
    assert reloaded.json()["settings"]["strategy"] == "aggressive"
    assert reloaded.json()["settings"]["attack_release_delay_ms"] == 1200
    assert reloaded.json()["settings"]["attack_animation_duration_ms"] == 900
    assert reloaded.json()["attributes"] == {"resistance": 15.0}
    assert reloaded.json()["default_position"] == {"x": 0.9, "y": 0.5}

    async with test_session() as session:
        stored_profile = await session.get(EntityContentProfile, UUID(profile_id))
        assert stored_profile is not None
        assert stored_profile.availability == "draft"


@pytest.mark.anyio
async def test_enemy_profile_validates_availability_and_attack_overrides(
    auth_client: AdminTestClient,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    enemy_id = await create_enemy(client)
    skill_response = await client.post(
        "/api/admin/content/skills",
        json={
            "name": "Golpe de teste",
            "category": "especial",
            "status": "published",
            "is_active": True,
        },
    )
    assert skill_response.status_code == 201, skill_response.text
    skill_id = skill_response.json()["id"]
    profile_payload = {
        "kind": "enemy",
        "availability": "available",
        "scale": 1,
        "orientation": "auto",
        "default_position": {"x": 0.5, "y": 0.5},
        "attributes": {},
        "settings": {
            "category": "miniboss",
            "default_attack_speed": 2,
            "gold_reward": 0,
            "special_rewards": [],
        },
        "assets": [{"role": "sprite", "asset_id": str(uuid4())}],
        "animations": [],
        "skills": [{"skill_id": skill_id, "attack_speed_override": 0.45}],
        "equipment_ids": [],
    }
    missing_asset = await client.put(
        f"/api/admin/content/profiles/enemy/{enemy_id}",
        json=profile_payload,
    )
    assert missing_asset.status_code == 422
    assert "asset visual" in missing_asset.text.lower()

    profile_payload["availability"] = "draft"
    profile_payload["assets"] = []
    saved = await client.put(
        f"/api/admin/content/profiles/enemy/{enemy_id}",
        json=profile_payload,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["skills"] == [
        {"skill_id": skill_id, "attack_speed_override": 0.45}
    ]

    async with test_session() as session:
        association = await session.scalar(
            select(EntityContentSkillAssociation).where(
                EntityContentSkillAssociation.skill_id == UUID(skill_id)
            )
        )
        assert association is not None
        assert association.attack_speed_override == 0.45


@pytest.mark.anyio
async def test_profile_rejects_invalid_coordinates_and_trajectory(
    auth_client: AdminTestClient,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    enemy_id = await create_enemy(client)
    payload = {
        "availability": "draft",
        "scale": 1,
        "orientation": "auto",
        "default_position": {"x": 1.01, "y": 0.5},
        "attributes": {},
        "settings": {
            "category": "common",
            "default_attack_speed": 1,
            "gold_reward": 0,
            "special_rewards": [],
        },
    }
    invalid_position = await client.put(
        f"/api/admin/content/profiles/enemy/{enemy_id}",
        json=payload,
    )
    assert invalid_position.status_code == 422

    payload["default_position"] = {"x": 0.5, "y": 0.5}
    payload["settings"]["trajectory"] = "teleport"
    invalid_trajectory = await client.put(
        f"/api/admin/content/profiles/enemy/{enemy_id}",
        json=payload,
    )
    assert invalid_trajectory.status_code == 422


@pytest.mark.anyio
async def test_entity_profile_requires_admin_authorization(
    auth_client: AdminTestClient,
) -> None:
    client, _ = auth_client
    response = await client.get("/api/admin/content/profiles/enemy")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_profile_accepts_private_asset_but_rejects_unavailable_file(
    auth_client: AdminTestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    enemy_id = await create_enemy(client)
    asset_id, unavailable_asset_id = uuid4(), uuid4()
    async with test_session() as session:
        session.add_all(
            [
                Asset(
                    id=asset_id,
                    name="Sprite privado",
                    category="monsters",
                    original_filename="sprite.png",
                    content_type="image/png",
                    extension=".png",
                    width=1,
                    height=1,
                    size_bytes=68,
                    storage_key="a" * 64,
                    is_public=False,
                ),
                Asset(
                    id=unavailable_asset_id,
                    name="Sprite ausente",
                    category="monsters",
                    original_filename="missing.png",
                    content_type="image/png",
                    extension=".png",
                    width=1,
                    height=1,
                    size_bytes=68,
                    storage_key="b" * 64,
                    is_public=False,
                ),
            ]
        )
        await session.commit()
    monkeypatch.setattr(admin_entity_profiles.storage, "open", lambda _: BytesIO(b"private"))
    profile_payload = {
        "kind": "enemy",
        "availability": "available",
        "scale": 1,
        "orientation": "auto",
        "default_position": {"x": 0.5, "y": 0.5},
        "attributes": {},
        "settings": {
            "category": "common",
            "default_attack_speed": 1,
            "gold_reward": 0,
            "special_rewards": [],
        },
        "assets": [{"role": "sprite", "asset_id": str(asset_id)}],
        "animations": [],
        "skills": [],
        "equipment_ids": [],
    }

    linked_private_asset = await client.put(
        f"/api/admin/content/profiles/enemy/{enemy_id}",
        json=profile_payload,
    )
    assert linked_private_asset.status_code == 200, linked_private_asset.text
    assert linked_private_asset.json()["assets"] == [
        {"role": "sprite", "asset_id": str(asset_id)}
    ]

    monkeypatch.setattr(
        admin_entity_profiles.storage,
        "open",
        lambda _: (_ for _ in ()).throw(FileNotFoundError("missing")),
    )
    profile_payload["assets"] = [
        {"role": "sprite", "asset_id": str(unavailable_asset_id)}
    ]
    unavailable = await client.put(
        f"/api/admin/content/profiles/enemy/{enemy_id}",
        json=profile_payload,
    )
    assert unavailable.status_code == 409
    assert "indisponível" in unavailable.text


@pytest.mark.anyio
async def test_profile_deletion_requires_confirmation_and_preserves_entity(
    auth_client: AdminTestClient,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    enemy_id = await create_enemy(client)
    payload = {
        "availability": "draft",
        "settings": {
            "category": "common",
            "default_attack_speed": 1,
            "gold_reward": 0,
            "special_rewards": [],
        },
    }
    saved = await client.put(
        f"/api/admin/content/profiles/enemy/{enemy_id}",
        json=payload,
    )
    assert saved.status_code == 200
    url = f"/api/admin/content/profiles/enemy/{enemy_id}"
    assert (await client.delete(url)).status_code == 400
    deleted = await client.delete(f"{url}?confirm=true")
    assert deleted.status_code == 204
    assert (await client.get(f"/api/admin/content/profiles/lookup/enemy/{enemy_id}")).json() is None

    async with test_session() as session:
        assert await session.get(Enemy, UUID(enemy_id)) is not None
