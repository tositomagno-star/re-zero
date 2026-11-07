from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import re
import secrets
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import AdminBootstrapEvent, AdminBootstrapState, User
from app.schemas.auth import USERNAME_PATTERN

BOOTSTRAP_TTL = timedelta(minutes=15)
TARGET_ENVIRONMENT = "production"


class AdminBootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class BootstrapOperation:
    operation_id: str
    expires_at: datetime


def hash_bootstrap_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def validate_admin_credentials(username: str, password: str) -> tuple[str, str]:
    normalized_username = username.strip()
    if re.fullmatch(USERNAME_PATTERN, normalized_username) is None:
        raise AdminBootstrapError(
            "Nome de usuário deve conter de 3 a 32 letras, números ou sublinhados."
        )
    if not 12 <= len(password) <= 128:
        raise AdminBootstrapError("A senha deve conter de 12 a 128 caracteres.")
    return normalized_username, normalized_username.casefold()


async def issue_admin_bootstrap_grant(
    session: AsyncSession,
    *,
    actor: str,
    store_secret: Callable[[str], None],
    now: datetime | None = None,
) -> BootstrapOperation:
    issued_at = now or datetime.now(UTC)
    state = await session.scalar(
        select(AdminBootstrapState)
        .where(AdminBootstrapState.id == 1)
        .with_for_update()
    )
    if state is None:
        raise AdminBootstrapError(
            "A migration do bootstrap não está instalada neste ambiente."
        )
    if state.completed_at is not None:
        raise AdminBootstrapError("O bootstrap administrativo já foi concluído.")
    if await session.scalar(select(User.id).where(User.is_admin.is_(True)).limit(1)):
        raise AdminBootstrapError("Já existe uma conta administrativa.")

    current_expiry = state.expires_at
    if current_expiry is not None and current_expiry.tzinfo is None:
        current_expiry = current_expiry.replace(tzinfo=UTC)
    if (
        state.secret_hash is not None
        and state.consumed_at is None
        and current_expiry is not None
        and current_expiry > issued_at
    ):
        raise AdminBootstrapError(
            "Já existe uma autorização de bootstrap válida; aguarde sua expiração."
        )

    secret = secrets.token_urlsafe(32)
    operation_id = str(uuid4())
    expires_at = issued_at + BOOTSTRAP_TTL
    store_secret(secret)
    state.secret_hash = hash_bootstrap_secret(secret)
    state.expires_at = expires_at
    state.consumed_at = None
    state.operation_id = operation_id
    state.issued_by = actor[:128]
    state.completed_by = None
    session.add(
        AdminBootstrapEvent(
            operation_id=operation_id,
            event_type="grant_issued",
            actor=actor[:128],
            admin_user_id=None,
            target_environment=TARGET_ENVIRONMENT,
            occurred_at=issued_at,
        )
    )
    await session.flush()
    return BootstrapOperation(operation_id=operation_id, expires_at=expires_at)


async def bootstrap_first_admin(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    secret: str,
    actor: str,
    now: datetime | None = None,
) -> tuple[User, str]:
    created_at = now or datetime.now(UTC)
    normalized_username, username_key = validate_admin_credentials(username, password)
    state = await session.scalar(
        select(AdminBootstrapState)
        .where(AdminBootstrapState.id == 1)
        .with_for_update()
    )
    if state is None:
        raise AdminBootstrapError(
            "A migration do bootstrap não está instalada neste ambiente."
        )
    if state.completed_at is not None:
        raise AdminBootstrapError("O bootstrap administrativo já foi concluído.")
    if await session.scalar(select(User.id).where(User.is_admin.is_(True)).limit(1)):
        raise AdminBootstrapError("Já existe uma conta administrativa.")
    if (
        state.secret_hash is None
        or state.expires_at is None
        or not hmac.compare_digest(state.secret_hash, hash_bootstrap_secret(secret))
    ):
        raise AdminBootstrapError("A autorização de bootstrap é inválida ou expirou.")

    expires_at = state.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= created_at or state.consumed_at is not None:
        raise AdminBootstrapError("A autorização de bootstrap é inválida ou expirou.")

    operation_id = state.operation_id
    if operation_id is None:
        raise AdminBootstrapError("A autorização de bootstrap é inválida ou expirou.")
    consumed = await session.scalar(
        update(AdminBootstrapState)
        .where(
            AdminBootstrapState.id == 1,
            AdminBootstrapState.secret_hash == hash_bootstrap_secret(secret),
            AdminBootstrapState.expires_at > created_at,
            AdminBootstrapState.consumed_at.is_(None),
            AdminBootstrapState.completed_at.is_(None),
        )
        .values(consumed_at=created_at)
        .returning(AdminBootstrapState.id)
        .execution_options(synchronize_session=False)
    )
    if consumed is None:
        raise AdminBootstrapError("A autorização de bootstrap é inválida ou expirou.")

    existing_username = await session.scalar(
        select(User.id).where(User.username_key == username_key).limit(1)
    )
    if existing_username is not None:
        raise AdminBootstrapError(
            "Este nome de usuário já existe; nenhuma conta foi alterada."
        )

    user = User(
        username=normalized_username,
        username_key=username_key,
        email=None,
        password_hash=hash_password(password),
        display_name=normalized_username,
        is_admin=True,
        status="active",
    )
    session.add(user)
    await session.flush()

    state.completed_at = created_at
    state.completed_by = actor[:128]
    session.add(
        AdminBootstrapEvent(
            operation_id=operation_id,
            event_type="admin_created",
            actor=actor[:128],
            admin_user_id=user.id,
            target_environment=TARGET_ENVIRONMENT,
            occurred_at=created_at,
        )
    )
    await session.flush()
    return user, operation_id
