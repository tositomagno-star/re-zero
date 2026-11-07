from datetime import datetime, timedelta, timezone
from math import ceil

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_rate_limit_key
from app.models import AuthRateLimit


def login_bucket_keys(ip_address: str, username_key: str) -> list[str]:
    return [
        hash_rate_limit_key(f"ip:{ip_address}"),
        hash_rate_limit_key(f"username:{username_key}"),
    ]


def registration_bucket_key(ip_address: str) -> str:
    return hash_rate_limit_key(f"registration:{ip_address}")


def _insert_bucket(session: AsyncSession, key: str, now: datetime):
    values = {
        "bucket_key": key,
        "attempts": 0,
        "window_started_at": now,
        "locked_until": None,
    }
    dialect_name = session.bind.dialect.name
    if dialect_name == "postgresql":
        statement = pg_insert(AuthRateLimit).values(**values)
    elif dialect_name == "sqlite":
        statement = sqlite_insert(AuthRateLimit).values(**values)
    else:
        raise RuntimeError(f"Unsupported rate-limit database dialect: {dialect_name}")
    return statement.on_conflict_do_nothing(index_elements=["bucket_key"])


async def consume_attempts(session: AsyncSession, bucket_keys: list[str]) -> None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    window = timedelta(minutes=settings.auth_rate_limit_minutes)
    lockout = timedelta(minutes=settings.auth_lockout_minutes)

    await session.execute(
        delete(AuthRateLimit).where(AuthRateLimit.updated_at < now - timedelta(days=1))
    )
    for key in bucket_keys:
        await session.execute(_insert_bucket(session, key, now))
        bucket = await session.scalar(
            select(AuthRateLimit)
            .where(AuthRateLimit.bucket_key == key)
            .with_for_update()
        )
        if bucket is None:
            raise RuntimeError("Failed to initialize an authentication rate-limit bucket.")

        locked_until = bucket.locked_until
        if locked_until is not None and locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until is not None and locked_until > now:
            retry_after = max(1, ceil((locked_until - now).total_seconds()))
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas. Aguarde antes de tentar novamente.",
                headers={"Retry-After": str(retry_after)},
            )
        window_started_at = bucket.window_started_at
        if window_started_at.tzinfo is None:
            window_started_at = window_started_at.replace(tzinfo=timezone.utc)
        if window_started_at <= now - window:
            bucket.attempts = 0
            bucket.window_started_at = now
            bucket.locked_until = None

        bucket.attempts += 1
        bucket.updated_at = now
        if bucket.attempts >= settings.auth_rate_limit_attempts:
            bucket.locked_until = now + lockout
    await session.commit()


async def clear_attempts(session: AsyncSession, bucket_keys: list[str]) -> None:
    now = datetime.now(timezone.utc)
    for key in bucket_keys:
        bucket = await session.get(AuthRateLimit, key, with_for_update=True)
        if bucket is not None:
            bucket.attempts = 0
            bucket.window_started_at = now
            bucket.locked_until = None
            bucket.updated_at = now
    await session.commit()
