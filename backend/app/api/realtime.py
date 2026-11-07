from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.security import hash_session_token
from app.db.session import SessionLocal
from app.models import AuthSession, User

router = APIRouter(tags=["realtime"])
connections: dict[str, set[WebSocket]] = defaultdict(set)


@router.websocket("/api/ws/campaigns/{campaign_id}")
async def campaign_realtime(websocket: WebSocket, campaign_id: str) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return
    async with SessionLocal() as db:
        user = (
            await db.execute(
                select(User)
                .join(AuthSession, AuthSession.user_id == User.id)
                .where(
                    AuthSession.token_hash == hash_session_token(token),
                    AuthSession.audience == "player",
                    AuthSession.expires_at > datetime.now(timezone.utc),
                    User.status == "active",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
    if user is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    connections[campaign_id].add(websocket)
    try:
        await websocket.send_json({"type": "connected", "campaign_id": campaign_id})
        while True:
            await websocket.receive_json()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        connections[campaign_id].discard(websocket)
