from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_player
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Campaign, CampaignMember, DiscordChannelMapping, DiscordGuild, ExternalIdentity, User

router = APIRouter(prefix="/api/discord", tags=["discord"])


def _signature(payload: str) -> str:
    return hmac.new(
        get_settings().app_secret_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def _state_cookie(user_id: str) -> str:
    nonce = secrets.token_urlsafe(24)
    payload = f"{int(time.time())}:{user_id}:{nonce}"
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{encoded}.{_signature(encoded)}"


def _read_state(value: str, user_id: str) -> None:
    try:
        encoded, signature = value.rsplit(".", 1)
        if not hmac.compare_digest(signature, _signature(encoded)):
            raise ValueError
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        issued, state_user_id, nonce = payload.split(":", 2)
        if state_user_id != user_id or not nonce or int(time.time()) - int(issued) > 600:
            raise ValueError
    except (ValueError, UnicodeError):
        raise HTTPException(status_code=400, detail="Estado OAuth inválido ou expirado.")


@router.get("/login")
async def discord_login(response: Response, user: User = Depends(current_player)) -> dict:
    settings = get_settings()
    if not settings.discord_client_id or not settings.discord_redirect_uri:
        raise HTTPException(status_code=503, detail="OAuth Discord não configurado.")
    state = _state_cookie(str(user.id))
    response.set_cookie(
        "discord_oauth_state", state, httponly=True, secure=settings.cookie_secure,
        samesite="lax", max_age=600, path="/api/discord",
    )
    query = urlencode({
        "client_id": settings.discord_client_id,
        "redirect_uri": settings.discord_redirect_uri,
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
    })
    return {"authorization_url": f"https://discord.com/oauth2/authorize?{query}"}


@router.get("/status")
async def discord_status(
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> dict:
    identity = await db.scalar(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == "discord",
            ExternalIdentity.user_id == user.id,
        )
    )
    return {"linked": identity is not None, "discord_id": identity.subject if identity else None}


@router.get("/callback")
async def discord_callback(
    code: str,
    state: str,
    response: Response,
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = get_settings()
    if not settings.discord_client_id or not settings.discord_client_secret or not settings.discord_redirect_uri:
        raise HTTPException(status_code=503, detail="OAuth Discord não configurado.")
    _read_state(state, str(user.id))
    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": settings.discord_client_id,
                "client_secret": settings.discord_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.discord_redirect_uri,
            },
        )
        if token_response.status_code >= 400:
            raise HTTPException(status_code=502, detail="Discord rejeitou a autorização.")
        access_token = token_response.json()["access_token"]
        identity_response = await client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if identity_response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Não foi possível consultar o Discord.")
    discord_id = str(identity_response.json()["id"])
    existing = await db.scalar(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == "discord",
            ExternalIdentity.subject == discord_id,
        )
    )
    if existing is not None and existing.user_id != user.id:
        raise HTTPException(status_code=409, detail="Conta Discord já vinculada a outro usuário.")
    if existing is None:
        db.add(ExternalIdentity(user_id=user.id, provider="discord", subject=discord_id))
    await db.commit()
    response.delete_cookie("discord_oauth_state", path="/api/discord")
    return {"linked": True, "discord_id": discord_id}


@router.post("/campaigns/{campaign_id}/sync")
async def sync_discord_campaign(
    campaign_id: str,
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = get_settings()
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")
    member = await db.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign.id,
            CampaignMember.user_id == user.id,
        )
    )
    if campaign.owner_id != user.id and member is None:
        raise HTTPException(status_code=403, detail="Acesso à campanha negado.")
    mappings = (await db.scalars(
        select(DiscordChannelMapping).join(
            DiscordGuild, DiscordGuild.id == DiscordChannelMapping.guild_id
        ).where(DiscordChannelMapping.campaign_id == campaign.id)
    )).all()
    if not settings.discord_bot_token:
        return {"synced": False, "reason": "bot_not_configured", "channels": len(mappings)}
    async with httpx.AsyncClient(
        timeout=15,
        headers={"Authorization": f"Bot {settings.discord_bot_token}"},
    ) as client:
        for mapping in mappings:
            await client.post(
                f"https://discord.com/api/channels/{mapping.external_channel_id}/messages",
                json={"content": f"Campanha “{campaign.title}” atualizada."},
            )
    return {"synced": True, "channels": len(mappings)}
