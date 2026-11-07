from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import admin_assets
from app.api import admin_animations
from app.core.security import hash_password
from app.main import app
from app.models import Asset, Character, User
from app.services.asset_storage import LocalAssetStorage

AnimationTestClient = tuple[object, async_sessionmaker[AsyncSession]]


@pytest.fixture
def animation_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalAssetStorage:
    store = LocalAssetStorage(tmp_path / "animation-assets")
    monkeypatch.setattr(admin_animations, "storage", store)
    monkeypatch.setattr(admin_assets, "storage", store)
    return store


def gif_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGBA", (3, 2), (20, 40, 60, 128)).save(output, format="GIF")
    return output.getvalue()


def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGBA", (3, 2), (20, 40, 60, 128)).save(output, format="PNG")
    return output.getvalue()


async def login_animation_admin(client, test_session):
    admin_id = uuid4()
    async with test_session() as session:
        session.add(
            User(
                id=admin_id,
                username="AnimationAdmin",
                username_key="animationadmin",
                email=None,
                password_hash=hash_password("a-long-animation-admin-password"),
                display_name="Animation Admin",
                is_admin=True,
                status="active",
            )
        )
        await session.commit()
    response = await client.post(
        "/api/auth/admin/login",
        json={"username": "AnimationAdmin", "password": "a-long-animation-admin-password"},
    )
    assert response.status_code == 200
    return admin_id


async def create_gif_asset(
    test_session: async_sessionmaker[AsyncSession],
    storage: LocalAssetStorage,
    *,
    file_exists: bool = True,
) -> Asset:
    raw = gif_bytes()
    key = storage.store(raw, ".gif") if file_exists else f"{uuid4().hex}.gif"
    asset = Asset(
        name="GIF privado de teste",
        description="",
        category="visual_effects",
        original_filename="effect.gif",
        content_type="image/gif",
        extension=".gif",
        width=3,
        height=2,
        size_bytes=len(raw),
        storage_key=key,
        analysis_metadata={"gif": {"frame_count": 1}},
        is_public=False,
    )
    async with test_session() as session:
        session.add(asset)
        await session.commit()
        await session.refresh(asset)
    return asset


def config_payload(asset_id: str, **overrides) -> dict:
    payload = {
        "name": "Bola arcana",
        "description": "Prévia isolada",
        "asset_id": asset_id,
        "impact_asset_id": None,
        "animation_type": "projectile",
        "trajectory": "right_to_center",
        "movement": "linear",
        "origin": {"x": 0.95, "y": 0.5},
        "target": {"x": 0.5, "y": 0.5},
        "scale": 1,
        "rotation": 0,
        "gif_playback_rate": 1.5,
        "travel_duration_ms": 850,
        "travel_speed": 0.75,
        "impact_time_ms": 120,
        "render_layer": 10,
        "direction": "auto",
        "extra": {},
        "associations": [],
    }
    payload.update(overrides)
    return payload


@pytest.mark.anyio
async def test_animation_configuration_crud_and_reload(
    auth_client: AnimationTestClient,
    animation_storage: LocalAssetStorage,
) -> None:
    client, test_session = auth_client
    await login_animation_admin(client, test_session)
    asset = await create_gif_asset(test_session, animation_storage)

    created = await client.post(
        "/api/admin/animations",
        json=config_payload(str(asset.id)),
    )
    assert created.status_code == 201, created.text
    saved = created.json()
    assert saved["gif_playback_rate"] == 1.5
    assert saved["travel_duration_ms"] == 850
    assert saved["travel_speed"] == 0.75
    assert saved["impact_time_ms"] == 120
    asset_listing = await client.get("/api/admin/assets")
    assert asset_listing.status_code == 200
    assert next(item for item in asset_listing.json() if item["id"] == str(asset.id))[
        "is_in_use"
    ] is True
    replacement = await client.put(
        f"/api/admin/assets/{asset.id}/file",
        files={"file": ("replacement.png", png_bytes(), "image/png")},
    )
    assert replacement.status_code == 409
    assert (
        await client.get(f"/api/admin/assets/{asset.id}/file")
    ).content == gif_bytes()
    protected_delete = await client.delete(
        f"/api/admin/assets/{asset.id}?confirm=true",
    )
    assert protected_delete.status_code == 409

    updated_payload = config_payload(
        str(asset.id),
        name="Bola arcana revisada",
        trajectory="origin_to_target",
        origin={"x": 0.8, "y": 0.2},
        target={"x": 0.3, "y": 0.7},
    )
    updated = await client.put(
        f"/api/admin/animations/{saved['id']}",
        json=updated_payload,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Bola arcana revisada"

    reloaded = await client.get("/api/admin/animations")
    assert reloaded.status_code == 200
    assert reloaded.json()[0]["id"] == saved["id"]
    assert reloaded.json()[0]["origin"] == {"x": 0.8, "y": 0.2}

    deleted = await client.delete(f"/api/admin/animations/{saved['id']}")
    assert deleted.status_code == 204
    assert (await client.get("/api/admin/animations")).json() == []
    refreshed_assets = (await client.get("/api/admin/assets")).json()
    assert next(item for item in refreshed_assets if item["id"] == str(asset.id))[
        "is_in_use"
    ] is False


@pytest.mark.anyio
async def test_animation_validation_associations_and_delete_protection(
    auth_client: AnimationTestClient,
    animation_storage: LocalAssetStorage,
) -> None:
    client, test_session = auth_client
    admin_id = await login_animation_admin(client, test_session)
    asset = await create_gif_asset(test_session, animation_storage)

    invalid_coordinates = await client.post(
        "/api/admin/animations",
        json=config_payload(
            str(asset.id),
            trajectory="right_to_center",
            origin={"x": 1.2, "y": 0.5},
        ),
    )
    assert invalid_coordinates.status_code == 422

    missing_asset = await client.post(
        "/api/admin/animations",
        json=config_payload(str(uuid4())),
    )
    assert missing_asset.status_code == 422
    invalid_speed = await client.post(
        "/api/admin/animations",
        json=config_payload(str(asset.id), travel_speed=0),
    )
    assert invalid_speed.status_code == 422
    invalid_association = await client.post(
        "/api/admin/animations",
        json=config_payload(
            str(asset.id),
            associations=[{"entity_type": "skill", "entity_id": str(uuid4())}],
        ),
    )
    assert invalid_association.status_code == 422

    async with test_session() as session:
        character = Character(owner_id=admin_id, name="Personagem associado")
        session.add(character)
        await session.commit()
        character_id = character.id
    payload = config_payload(
        str(asset.id),
        associations=[{"entity_type": "character", "entity_id": str(character_id)}],
    )
    created = await client.post("/api/admin/animations", json=payload)
    assert created.status_code == 201, created.text
    animation_id = created.json()["id"]
    assert created.json()["is_in_use"] is True

    blocked = await client.delete(f"/api/admin/animations/{animation_id}")
    assert blocked.status_code == 409

    detached = await client.put(
        f"/api/admin/animations/{animation_id}",
        json={**payload, "associations": []},
    )
    assert detached.status_code == 200
    assert detached.json()["is_in_use"] is False
    assert (await client.delete(f"/api/admin/animations/{animation_id}")).status_code == 204


@pytest.mark.anyio
async def test_animation_requires_admin_and_rejects_unavailable_asset(
    auth_client: AnimationTestClient,
    animation_storage: LocalAssetStorage,
) -> None:
    client, test_session = auth_client
    anonymous_response = await client.get("/api/admin/animations")
    assert anonymous_response.status_code in {401, 403}

    async with test_session() as session:
        session.add(
            User(
                username="AnimationPlayer",
                username_key="animationplayer",
                email=None,
                password_hash=hash_password("a-long-animation-player-password"),
                display_name="Animation Player",
                is_admin=False,
                status="active",
            )
        )
        await session.commit()
    player_login = await client.post(
        "/api/auth/login",
        json={"username": "AnimationPlayer", "password": "a-long-animation-player-password"},
    )
    assert player_login.status_code == 200
    player_response = await client.get("/api/admin/animations")
    assert player_response.status_code in {401, 403}

    await login_animation_admin(client, test_session)
    missing_file_asset = await create_gif_asset(
        test_session,
        animation_storage,
        file_exists=False,
    )
    unavailable = await client.post(
        "/api/admin/animations",
        json=config_payload(str(missing_file_asset.id)),
    )
    assert unavailable.status_code == 409

    non_gif = Asset(
        name="PNG",
        description="",
        category="visual_effects",
        original_filename="image.png",
        content_type="image/png",
        extension=".png",
        width=3,
        height=2,
        size_bytes=16,
        storage_key=f"{uuid4().hex}.png",
        analysis_metadata={},
        is_public=False,
    )
    async with test_session() as session:
        session.add(non_gif)
        await session.commit()
        await session.refresh(non_gif)
    rejected = await client.post(
        "/api/admin/animations",
        json=config_payload(str(non_gif.id)),
    )
    assert rejected.status_code == 422
