import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Campaign, CampaignMember, Character, User
from app.schemas.campaigns import (
    CampaignMemberResponse,
    CampaignResponse,
    CampaignSummaryResponse,
)

__all__ = [
    "_PRESENCE_TIMEOUT",
    "_active_member",
    "_aware",
    "_campaign_response",
    "_campaign_summaries",
    "_default_character_name",
    "_member_responses",
    "_new_join_code",
    "_now",
    "_summary_response",
]

_PRESENCE_TIMEOUT = timedelta(seconds=45)


def _new_join_code() -> str:
    return secrets.token_hex(16).upper()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _default_character_name(display_name: str) -> str:
    return f"Personagem de {display_name}"[:100]


async def _active_member(
    db: AsyncSession,
    campaign_id: UUID,
    user_id: UUID,
) -> CampaignMember:
    campaign = await db.get(Campaign, campaign_id)
    member = await db.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == user_id,
            CampaignMember.status == "active",
        )
    )
    if campaign is None or member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campanha não encontrada.",
        )
    return member


async def _member_responses(
    db: AsyncSession,
    campaign_id: UUID,
) -> list[CampaignMemberResponse]:
    result = await db.execute(
        select(CampaignMember, User, Character)
        .join(User, User.id == CampaignMember.user_id)
        .outerjoin(
            Character,
            (Character.id == CampaignMember.character_id)
            & (Character.owner_id == CampaignMember.user_id)
            & (Character.campaign_id == CampaignMember.campaign_id),
        )
        .where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.status == "active",
        )
        .order_by(CampaignMember.created_at, CampaignMember.id)
    )
    now = _now()
    members: list[CampaignMemberResponse] = []
    for member, user, character in result.all():
        last_seen = _aware(member.last_seen_at) if member.last_seen_at is not None else None
        connected = (
            last_seen is not None
            and now - last_seen <= _PRESENCE_TIMEOUT
        )
        members.append(
            CampaignMemberResponse(
                user_id=user.id,
                username=user.username,
                display_name=user.display_name,
                role=member.role,
                is_ready=member.is_ready,
                is_connected=connected,
                character_id=character.id if character is not None else None,
                character_name=character.name if character is not None else None,
                level=character.level if character is not None else None,
                hp=character.hp if character is not None else None,
                max_hp=character.max_hp if character is not None else None,
                mana=character.mana if character is not None else None,
                max_mana=character.max_mana if character is not None else None,
            )
        )
    return members


async def _summary_response(
    db: AsyncSession,
    campaign: Campaign,
    user: User,
    membership_status: str,
) -> CampaignSummaryResponse:
    owner = await db.get(User, campaign.owner_id)
    if owner is None:
        raise RuntimeError("Campaign owner record is missing.")
    participant_count = await db.scalar(
        select(func.count(CampaignMember.id)).where(
            CampaignMember.campaign_id == campaign.id,
            CampaignMember.status == "active",
        )
    )
    owner_active = await db.scalar(
        select(CampaignMember.id).where(
            CampaignMember.campaign_id == campaign.id,
            CampaignMember.user_id == campaign.owner_id,
            CampaignMember.status == "active",
        )
    )
    return _campaign_summary_response(
        campaign,
        user,
        membership_status,
        owner.display_name,
        participant_count,
        owner_active is not None,
    )


def _campaign_summary_response(
    campaign: Campaign,
    user: User,
    membership_status: str,
    owner_display_name: str,
    participant_count: int | None,
    owner_active: bool,
) -> CampaignSummaryResponse:
    active_participant_count = participant_count or 0
    reserved_owner_seat = int(not owner_active)
    available_slots = max(
        campaign.max_players - active_participant_count - reserved_owner_seat,
        0,
    )
    return CampaignSummaryResponse(
        id=campaign.id,
        title=campaign.title,
        description=campaign.description,
        join_code=campaign.join_code,
        status=campaign.status,
        owner_id=campaign.owner_id,
        owner_display_name=owner_display_name,
        min_players=campaign.min_players,
        max_players=campaign.max_players,
        participant_count=active_participant_count,
        available_slots=available_slots,
        current_chapter_id=campaign.current_chapter_id,
        current_node_id=campaign.current_node_id,
        last_activity_at=campaign.last_activity_at,
        membership_status=membership_status,
        is_owner=campaign.owner_id == user.id,
        solo=(campaign.settings or {}).get("game_mode") == "solo",
    )


async def _campaign_summaries(
    db: AsyncSession,
    user: User,
) -> list[CampaignSummaryResponse]:
    result = await db.execute(
        select(Campaign, CampaignMember.status, User.display_name)
        .outerjoin(
            CampaignMember,
            (CampaignMember.campaign_id == Campaign.id)
            & (CampaignMember.user_id == user.id),
        )
        .outerjoin(User, User.id == Campaign.owner_id)
        .where(or_(Campaign.owner_id == user.id, CampaignMember.user_id == user.id))
        .order_by(Campaign.last_activity_at.desc(), Campaign.created_at.desc())
    )
    campaigns = result.all()
    if not campaigns:
        return []

    campaign_ids = [campaign.id for campaign, _, _ in campaigns]
    aggregates = await db.execute(
        select(
            CampaignMember.campaign_id,
            func.count(CampaignMember.id).label("participant_count"),
            func.max(
                case(
                    (CampaignMember.user_id == Campaign.owner_id, 1),
                    else_=0,
                )
            ).label("owner_active"),
        )
        .join(Campaign, Campaign.id == CampaignMember.campaign_id)
        .where(
            CampaignMember.campaign_id.in_(campaign_ids),
            CampaignMember.status == "active",
        )
        .group_by(CampaignMember.campaign_id)
    )
    aggregate_by_campaign = {
        campaign_id: (participant_count, bool(owner_active))
        for campaign_id, participant_count, owner_active in aggregates.all()
    }

    summaries: list[CampaignSummaryResponse] = []
    for campaign, membership_status, owner_display_name in campaigns:
        if owner_display_name is None:
            raise RuntimeError("Campaign owner record is missing.")
        participant_count, owner_active = aggregate_by_campaign.get(
            campaign.id,
            (0, False),
        )
        summaries.append(
            _campaign_summary_response(
                campaign,
                user,
                membership_status or "left",
                owner_display_name,
                participant_count,
                owner_active,
            )
        )
    return summaries


async def _campaign_response(
    db: AsyncSession,
    campaign: Campaign,
    user: User,
    member: CampaignMember,
) -> CampaignResponse:
    summary = await _summary_response(db, campaign, user, member.status)
    return CampaignResponse(
        **summary.model_dump(),
        members=await _member_responses(db, campaign.id),
    )
