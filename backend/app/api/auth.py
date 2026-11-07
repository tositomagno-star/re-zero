from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    ADMIN_COOKIE,
    PLAYER_COOKIE,
    current_admin,
    current_player,
    require_same_origin,
)
from app.core.config import get_settings
from app.core.rate_limit import (
    clear_attempts,
    consume_attempts,
    login_bucket_keys,
    registration_bucket_key,
)
from app.core.security import (
    create_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.db.session import get_db
from app.models import AuthSession, User
from app.schemas.auth import (
    AdminLoginRequest,
    PlayerLoginRequest,
    RegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
_DUMMY_PASSWORD_HASH = hash_password("000000")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _username_key(username: str) -> str:
    return username.casefold()


def _set_session_cookie(
    response: Response,
    *,
    audience: str,
    token: str,
    expires_at: datetime,
    max_age: int,
) -> None:
    settings = get_settings()
    cookie_name = ADMIN_COOKIE if audience == "admin" else PLAYER_COOKIE
    response.set_cookie(
        key=cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=max_age,
        expires=expires_at,
    )


async def _create_session(
    db: AsyncSession,
    response: Response,
    *,
    user_id: UUID,
    audience: str,
) -> None:
    settings = get_settings()
    ttl_hours = settings.admin_session_hours if audience == "admin" else settings.player_session_hours
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    token, token_hash = create_session_token()
    db.add(
        AuthSession(
            user_id=user_id,
            token_hash=token_hash,
            audience=audience,
            expires_at=expires_at,
        )
    )
    await db.commit()
    _set_session_cookie(
        response,
        audience=audience,
        token=token,
        expires_at=expires_at,
        max_age=ttl_hours * 60 * 60,
    )


def _user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, username=user.username, display_name=user.display_name)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    _: None = Depends(require_same_origin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    await consume_attempts(db, [registration_bucket_key(_client_ip(request))])
    username = payload.username.strip()
    username_key = _username_key(username)
    existing = await db.scalar(select(User.id).where(User.username_key == username_key))
    if existing is not None:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este nome de usuário já está em uso.",
        )

    user = User(
        username=username,
        username_key=username_key,
        email=None,
        password_hash=hash_password(payload.password.get_secret_value()),
        display_name=username,
        is_admin=False,
        status="active",
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este nome de usuário já está em uso.",
        ) from None

    await _create_session(db, response, user_id=user.id, audience="player")
    return _user_response(user)


async def _login(
    *,
    username: str,
    password: str,
    ip_address: str,
    audience: str,
    response: Response,
    db: AsyncSession,
) -> UserResponse:
    username_key = _username_key(username.strip())
    await consume_attempts(db, login_bucket_keys(ip_address, username_key))
    user = await db.scalar(select(User).where(User.username_key == username_key))
    encoded_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    response_user = _user_response(user) if user is not None else None
    user_id = user.id if user is not None else None
    valid_password = verify_password(password, encoded_hash)
    active_user = user is not None and user.status == "active"
    authorized = user is not None and (audience != "admin" or user.is_admin)
    await db.rollback()

    if not valid_password or not active_user or not authorized or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos.",
        )

    await clear_attempts(db, login_bucket_keys(ip_address, username_key))
    if user_id is None:
        raise RuntimeError("Authenticated user identifier was not captured.")
    await _create_session(db, response, user_id=user_id, audience=audience)
    if response_user is None:
        raise RuntimeError("Authenticated user response was not created.")
    return response_user


@router.post("/login", response_model=UserResponse)
async def player_login(
    payload: PlayerLoginRequest,
    request: Request,
    response: Response,
    _: None = Depends(require_same_origin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return await _login(
        username=payload.username,
        password=payload.password.get_secret_value(),
        ip_address=_client_ip(request),
        audience="player",
        response=response,
        db=db,
    )


@router.post("/admin/login", response_model=UserResponse)
async def admin_login(
    payload: AdminLoginRequest,
    request: Request,
    response: Response,
    _: None = Depends(require_same_origin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return await _login(
        username=payload.username,
        password=payload.password.get_secret_value(),
        ip_address=_client_ip(request),
        audience="admin",
        response=response,
        db=db,
    )


@router.get("/session", response_model=UserResponse)
async def player_session(user: User = Depends(current_player)) -> UserResponse:
    return _user_response(user)


@router.get("/admin/session", response_model=UserResponse)
async def admin_session(user: User = Depends(current_admin)) -> UserResponse:
    return _user_response(user)


async def _logout(
    *,
    request: Request,
    response: Response,
    audience: str,
    db: AsyncSession,
) -> None:
    cookie_name = ADMIN_COOKIE if audience == "admin" else PLAYER_COOKIE
    token = request.cookies.get(cookie_name)
    if token is not None:
        token_hash = hash_session_token(token)
        await db.execute(
            delete(AuthSession).where(
                AuthSession.token_hash == token_hash,
                AuthSession.audience == audience,
            )
        )
        await db.commit()
    response.delete_cookie(
        key=cookie_name,
        path="/",
        secure=get_settings().cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def player_logout(
    request: Request,
    response: Response,
    _: None = Depends(require_same_origin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _logout(request=request, response=response, audience="player", db=db)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/admin/logout", status_code=status.HTTP_204_NO_CONTENT)
async def admin_logout(
    request: Request,
    response: Response,
    _: None = Depends(require_same_origin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _logout(request=request, response=response, audience="admin", db=db)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
