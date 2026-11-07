from datetime import datetime, timezone
from http.cookies import SimpleCookie
from types import SimpleNamespace

import pytest
from fastapi import Response
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import auth as auth_api
from app.api.dependencies import PLAYER_COOKIE
from app.core.security import hash_password, verify_password
from app.models import User

AuthTestClient = tuple[AsyncClient, async_sessionmaker[AsyncSession]]
PLAYER_PASSWORD = "Reino#2026!!"


def test_session_cookie_keeps_security_and_lifetime_attributes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_api,
        "get_settings",
        lambda: SimpleNamespace(cookie_secure=True),
    )
    response = Response()

    auth_api._set_session_cookie(
        response,
        audience="player",
        token="opaque-session-token",
        expires_at=datetime(2026, 11, 2, tzinfo=timezone.utc),
        max_age=3600,
    )

    cookies = SimpleCookie()
    cookies.load(response.headers["set-cookie"])
    cookie = cookies[PLAYER_COOKIE]
    assert cookie.value == "opaque-session-token"
    assert cookie["httponly"]
    assert cookie["secure"]
    assert cookie["samesite"] == "lax"
    assert cookie["path"] == "/"
    assert cookie["max-age"] == "3600"
    assert cookie["expires"]


@pytest.mark.anyio
async def test_register_login_session_and_logout(auth_client: AuthTestClient) -> None:
    client, test_session = auth_client
    registered = await client.post(
        "/api/auth/register",
        json={"username": "Artemis_7", "password": PLAYER_PASSWORD},
    )

    assert registered.status_code == 201
    assert registered.json()["username"] == "Artemis_7"
    assert "HttpOnly" in registered.headers["set-cookie"]
    assert "email" not in registered.json()

    async with test_session() as session:
        user = await session.scalar(select(User).where(User.username_key == "artemis_7"))
        assert user is not None
        assert user.email is None
        assert user.is_admin is False
        assert user.password_hash != PLAYER_PASSWORD
        assert verify_password(PLAYER_PASSWORD, user.password_hash)

    current = await client.get("/api/auth/session")
    assert current.status_code == 200
    assert current.json()["username"] == "Artemis_7"

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert (await client.get("/api/auth/session")).status_code == 401

    login = await client.post(
        "/api/auth/login",
        json={"username": "artemis_7", "password": PLAYER_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["username"] == "Artemis_7"


@pytest.mark.anyio
async def test_registration_requires_twelve_characters_and_rejects_duplicate_username(
    auth_client: AuthTestClient,
) -> None:
    client, _ = auth_client
    created = await client.post(
        "/api/auth/register",
        json={"username": "UniquePlayer", "password": PLAYER_PASSWORD},
    )
    duplicate = await client.post(
        "/api/auth/register",
        json={"username": "uniqueplayer", "password": "another-valid-password"},
    )
    short_password = await client.post(
        "/api/auth/register",
        json={"username": "OtherPlayer", "password": "short-pass"},
    )

    assert created.status_code == 201
    assert duplicate.status_code == 409
    assert short_password.status_code == 422
    assert "short-pass" not in short_password.text


@pytest.mark.anyio
async def test_existing_six_digit_password_can_still_log_in(
    auth_client: AuthTestClient,
) -> None:
    client, test_session = auth_client
    async with test_session() as session:
        session.add(
            User(
                username="LegacyPlayer",
                username_key="legacyplayer",
                email=None,
                password_hash=hash_password("001234"),
                display_name="LegacyPlayer",
                is_admin=False,
                status="active",
            )
        )
        await session.commit()

    login = await client.post(
        "/api/auth/login",
        json={"username": "LegacyPlayer", "password": "001234"},
    )

    assert login.status_code == 200
    assert login.json()["username"] == "LegacyPlayer"


@pytest.mark.anyio
async def test_failed_logins_are_temporarily_rate_limited(auth_client: AuthTestClient) -> None:
    client, _ = auth_client
    await client.post(
        "/api/auth/register",
        json={"username": "RateLimited", "password": PLAYER_PASSWORD},
    )
    await client.post("/api/auth/logout")

    responses = [
        await client.post(
            "/api/auth/login",
            json={"username": "RateLimited", "password": "incorrect-old-pin"},
        )
        for _ in range(5)
    ]
    blocked = await client.post(
        "/api/auth/login",
        json={"username": "RateLimited", "password": PLAYER_PASSWORD},
    )

    assert all(response.status_code == 401 for response in responses)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0


@pytest.mark.anyio
async def test_admin_login_is_separate_and_player_cannot_access_admin(
    auth_client: AuthTestClient,
) -> None:
    client, _ = auth_client
    await client.post(
        "/api/auth/register",
        json={"username": "NormalPlayer", "password": PLAYER_PASSWORD},
    )
    denied = await client.post(
        "/api/auth/admin/login",
        json={"username": "NormalPlayer", "password": "long-password-not-for-admin"},
    )
    admin_session_without_admin_cookie = await client.get("/api/auth/admin/session")

    assert denied.status_code == 401
    assert admin_session_without_admin_cookie.status_code == 401


@pytest.mark.anyio
async def test_untrusted_origin_cannot_register(auth_client: AuthTestClient) -> None:
    client, _ = auth_client
    response = await client.post(
        "/api/auth/register",
        headers={"Origin": "https://attacker.example"},
        json={"username": "BlockedOrigin", "password": PLAYER_PASSWORD},
    )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_administrator_can_log_in_only_through_admin_session(
    auth_client: AuthTestClient,
) -> None:
    client, test_session = auth_client
    async with test_session() as session:
        session.add(
            User(
                username="WorldAdmin",
                username_key="worldadmin",
                email=None,
                password_hash=hash_password("a-long-admin-password-2026"),
                display_name="WorldAdmin",
                is_admin=True,
                status="active",
            )
        )
        await session.commit()

    login = await client.post(
        "/api/auth/admin/login",
        json={"username": "WorldAdmin", "password": "a-long-admin-password-2026"},
    )
    admin_session = await client.get("/api/auth/admin/session")
    player_session = await client.get("/api/auth/session")

    assert login.status_code == 200
    assert "rpg_admin_session" in login.headers["set-cookie"]
    assert admin_session.status_code == 200
    assert player_session.status_code == 401
