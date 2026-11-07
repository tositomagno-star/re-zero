from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.security import verify_password
from app.models import User
from app.services.local_admin import (
    LocalAdminError,
    create_local_admin,
    resolve_local_admin_target,
)


LOCAL_DATABASE_URL = (
    "postgresql+asyncpg://local_user:synthetic@127.0.0.1:5432/cronicas_do_reino_dev"
)


def _resolve_target(
    *,
    app_environment: str = "development",
    database_url: str = LOCAL_DATABASE_URL,
):
    return resolve_local_admin_target(
        {"APP_ENVIRONMENT": app_environment},
        database_url=database_url,
    )


def test_local_admin_target_requires_development_environment() -> None:
    with pytest.raises(LocalAdminError, match="development"):
        _resolve_target(app_environment="production")
    with pytest.raises(LocalAdminError, match="development"):
        _resolve_target(app_environment="test")


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://local_user:synthetic@127.0.0.1:5432/cronicas_do_reino_test",
        "postgresql+asyncpg://local_user:synthetic@127.0.0.1:5432/other_db",
        "postgresql+asyncpg://local_user:synthetic@db.example:5432/cronicas_do_reino_dev",
        "postgresql+asyncpg://local_user:synthetic@127.0.0.1:5433/cronicas_do_reino_dev",
        "sqlite+aiosqlite://",
    ],
)
def test_local_admin_target_rejects_unapproved_database(database_url: str) -> None:
    with pytest.raises(LocalAdminError):
        _resolve_target(database_url=database_url)


@pytest.mark.anyio
async def test_local_admin_creation_hashes_password_and_allows_admin_login(
    auth_client,
) -> None:
    client, test_session = auth_client

    async with test_session() as session:
        async with session.begin():
            admin = await create_local_admin(
                session,
                username="LocalAdmin",
                password="a-synthetic-admin-password",
            )
            admin_id = admin.id

    async with test_session() as session:
        stored_admin = await session.get(User, admin_id)
        assert stored_admin is not None
        assert stored_admin.username == "LocalAdmin"
        assert stored_admin.is_admin is True
        assert stored_admin.password_hash != "a-synthetic-admin-password"
        assert verify_password(
            "a-synthetic-admin-password",
            stored_admin.password_hash,
        )

    login = await client.post(
        "/api/auth/admin/login",
        json={
            "username": "LocalAdmin",
            "password": "a-synthetic-admin-password",
        },
    )
    admin_session = await client.get("/api/auth/admin/session")
    assert login.status_code == 200
    assert "rpg_admin_session" in login.headers["set-cookie"]
    assert admin_session.status_code == 200
    assert admin_session.json()["username"] == "LocalAdmin"


@pytest.mark.anyio
async def test_local_admin_rejects_duplicate_without_promoting_existing_player(
    auth_client,
) -> None:
    _, test_session = auth_client
    async with test_session() as session:
        player = User(
            username="ExistingPlayer",
            username_key="existingplayer",
            email=None,
            password_hash="synthetic-existing-hash",
            display_name="ExistingPlayer",
            is_admin=False,
            status="active",
        )
        session.add(player)
        await session.commit()

    async with test_session() as session:
        with pytest.raises(LocalAdminError, match="já está cadastrado"):
            async with session.begin():
                await create_local_admin(
                    session,
                    username="ExistingPlayer",
                    password="a-synthetic-admin-password",
                )

    async with test_session() as session:
        existing = await session.scalar(
            select(User).where(User.username_key == "existingplayer")
        )
        assert existing is not None
        assert existing.is_admin is False
        assert existing.password_hash == "synthetic-existing-hash"


@pytest.mark.anyio
async def test_public_registration_still_creates_non_admin_user(auth_client) -> None:
    client, test_session = auth_client
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "PublicPlayer",
            "password": "a-synthetic-player-password",
        },
    )
    assert response.status_code == 201

    async with test_session() as session:
        player = await session.scalar(
            select(User).where(User.username_key == "publicplayer")
        )
        assert player is not None
        assert player.is_admin is False
