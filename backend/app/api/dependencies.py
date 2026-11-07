from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_session_token
from app.db.session import get_db
from app.models import AuthSession, User

PLAYER_COOKIE = "rpg_player_session"
ADMIN_COOKIE = "rpg_admin_session"


def require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is not None and origin not in get_settings().frontend_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origem da solicitação não autorizada.",
        )


async def _authenticated_user(
    request: Request,
    session: AsyncSession,
    *,
    audience: str,
) -> User:
    cookie_name = ADMIN_COOKIE if audience == "admin" else PLAYER_COOKIE
    token = request.cookies.get(cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária.",
        )

    token_hash = hash_session_token(token)
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(User, AuthSession)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.token_hash == token_hash,
            AuthSession.audience == audience,
            AuthSession.expires_at > now,
            User.status == "active",
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada.",
        )

    user = row[0]
    if audience == "admin" and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso administrativo necessário.",
        )
    return user


async def current_player(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> User:
    return await _authenticated_user(request, session, audience="player")


async def current_admin(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> User:
    return await _authenticated_user(request, session, audience="admin")
