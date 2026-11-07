from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_player, require_same_origin
from app.core.rate_limit import clear_attempts, consume_attempts
from app.core.security import hash_rate_limit_key
from app.db.session import get_db
from app.models import (
    Campaign,
    CampaignMember,
    Character,
    CharacterItem,
    CharacterRewardGrant,
    CharacterQuest,
    CharacterSkill,
    GameEvent,
    GameSession,
    Item,
    Quest,
    Skill,
    StoryChoice,
    StoryVote,
    User,
    WalletTransaction,
)
from app.schemas.campaigns import (
    CampaignQuestAcceptResponse,
    CampaignQuestResponse,
    CampaignCreateRequest,
    CampaignMemberResponse,
    CampaignMemberActionRequest,
    CampaignResponse,
    CampaignSummaryResponse,
    CharacterProgressionEventResponse,
    CharacterSheetResponse,
    CharacterUpdateRequest,
    EquipmentUpdateRequest,
    ShopTransactionRequest,
    JoinCampaignRequest,
    NarrativeGameResponse,
    ReadyUpdateRequest,
    SoloCharacterCreateRequest,
    SoloCharacterResponse,
    StoryVoteRequest,
)
from app.services.campaigns import (
    _active_member,
    _aware,
    _campaign_response,
    _campaign_summaries,
    _default_character_name,
    _member_responses,
    _new_join_code,
    _now,
)
from app.services.narrative import (
    _append_game_event,
    _close_vote_if_ready,
    _narrative_response,
    _open_vote,
    _published_story_snapshot,
    _scene_in_snapshot,
    _session_voting_settings,
    _validate_story_snapshot,
    _vote_event_idempotency_key,
    acquire_narrative_campaign_lock,
)
from app.services.equipment import (
    allowed_slots,
    carry_capacity,
    equipment_requirements_error,
    normalize_slot,
)
from app.services.progression import xp_progress_percent, xp_required_for_next_level
from app.services.attribute_engine import resolve_character_attributes

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


def _quest_progress_response(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in value.items()
        if key not in {
            "completion_idempotency_key",
            "title_snapshot",
            "reward_snapshot",
            "conditions_snapshot",
            "objective_events",
        }
    }


def _is_solo_campaign(campaign: Campaign) -> bool:
    settings = campaign.settings if isinstance(campaign.settings, dict) else {}
    return settings.get("game_mode") == "solo"


def _quest_content_response(
    quest: Quest,
    progress: object = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    stored_progress = progress if isinstance(progress, dict) else {}
    raw_conditions = stored_progress.get("conditions_snapshot", quest.conditions)
    conditions = raw_conditions if isinstance(raw_conditions, dict) else {}
    raw_objectives = conditions.get("objectives", [])
    objectives = (
        [objective for objective in raw_objectives if isinstance(objective, dict)]
        if isinstance(raw_objectives, list)
        else []
    )
    raw_rewards = stored_progress.get("reward_snapshot", quest.rewards)
    rewards = raw_rewards if isinstance(raw_rewards, dict) else {}
    safe_rewards: dict[str, object] = {
        "xp": rewards.get("xp", 0),
        "gold": rewards.get("gold", 0),
        "items": rewards.get("items", []),
        "skill_ids": rewards.get("skill_ids", []),
    }
    return objectives, safe_rewards


@router.post(
    "",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign(
    payload: CampaignCreateRequest,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    now = _now()
    for _ in range(5):
        code = _new_join_code()
        if await db.scalar(select(Campaign.id).where(Campaign.join_code == code)) is not None:
            continue

        campaign = Campaign(
            owner_id=user.id,
            title=payload.title,
            description=payload.description.strip(),
            status="waiting",
            visibility="private",
            min_players=1 if payload.solo else 3,
            max_players=1 if payload.solo else payload.max_players,
            join_code=code,
            last_activity_at=now,
            settings={
                "narrative_voting": payload.voting_settings.model_dump(mode="json"),
                "game_mode": "solo" if payload.solo else "multiplayer",
                "difficulty": payload.difficulty,
            },
        )
        try:
            db.add(campaign)
            await db.flush()
            character = Character(
                owner_id=user.id,
                campaign_id=campaign.id,
                name=_default_character_name(user.display_name),
            )
            db.add(character)
            await db.flush()
            member = CampaignMember(
                campaign_id=campaign.id,
                user_id=user.id,
                character_id=character.id,
                role="owner",
                status="active",
                joined_at=now,
                is_ready=False,
                last_seen_at=now,
            )
            db.add(member)
            await db.commit()
        except IntegrityError:
            await db.rollback()
            if await db.scalar(select(Campaign.id).where(Campaign.join_code == code)) is not None:
                continue
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Não foi possível criar a campanha. Tente novamente.",
            ) from None

        return await _campaign_response(db, campaign, user, member)

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Não foi possível gerar um código de sala único. Tente novamente.",
    )


@router.get("", response_model=list[CampaignSummaryResponse])
async def list_campaigns(
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> list[CampaignSummaryResponse]:
    return await _campaign_summaries(db, user)


@router.post("/join", response_model=CampaignResponse)
async def join_campaign(
    payload: JoinCampaignRequest,
    request: Request,
    response: Response,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    campaign = await db.scalar(
        select(Campaign)
        .where(Campaign.join_code == payload.code)
        .with_for_update()
    )
    if campaign is not None and (campaign.settings or {}).get("game_mode") == "solo":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Campanhas solo não possuem participação de outros jogadores.",
        )
    if campaign is None:
        ip_address = request.client.host if request.client is not None else "unknown"
        keys = [
            hash_rate_limit_key(f"campaign-join-ip:{ip_address}"),
            hash_rate_limit_key(f"campaign-join-user:{user.id}"),
        ]
        await consume_attempts(db, keys)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Código inválido. Confira o código e tente novamente.",
        )

    if campaign.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta campanha foi encerrada e não aceita novos participantes.",
        )

    member = await db.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign.id,
            CampaignMember.user_id == user.id,
        )
    )
    if member is not None and member.status == "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Você já participa desta campanha.",
        )

    active_count = await db.scalar(
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
    reserved_owner_seat = int(owner_active is None and user.id != campaign.owner_id)
    if (active_count or 0) + reserved_owner_seat >= campaign.max_players:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A sala está cheia. Não há vagas disponíveis.",
        )

    now = _now()
    if member is None:
        character = Character(
            owner_id=user.id,
            campaign_id=campaign.id,
            name=_default_character_name(user.display_name),
        )
        db.add(character)
        await db.flush()
        member = CampaignMember(
            campaign_id=campaign.id,
            user_id=user.id,
            character_id=character.id,
            role="player",
            status="active",
            joined_at=now,
            is_ready=False,
            last_seen_at=now,
        )
        db.add(member)
        response.status_code = status.HTTP_201_CREATED
    else:
        existing_character = (
            await db.get(Character, member.character_id)
            if member.character_id is not None
            else None
        )
        if (
            existing_character is None
            or existing_character.owner_id != user.id
            or existing_character.campaign_id != campaign.id
        ):
            character = Character(
                owner_id=user.id,
                campaign_id=campaign.id,
                name=_default_character_name(user.display_name),
            )
            db.add(character)
            await db.flush()
            member.character_id = character.id
        member.status = "active"
        member.joined_at = now
        member.last_seen_at = now
        member.is_ready = False

    campaign.last_activity_at = now
    await db.commit()
    await db.refresh(campaign)
    await db.refresh(member)
    await clear_attempts(
        db,
        [
            hash_rate_limit_key(
                f"campaign-join-ip:{request.client.host if request.client else 'unknown'}"
            ),
            hash_rate_limit_key(f"campaign-join-user:{user.id}"),
        ],
    )
    return await _campaign_response(db, campaign, user, member)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: UUID,
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    member = await _active_member(db, campaign_id, user.id)
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campanha não encontrada.")
    return await _campaign_response(db, campaign, user, member)


@router.get("/{campaign_id}/quests", response_model=list[CampaignQuestResponse])
async def list_campaign_quests(
    campaign_id: UUID,
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> list[CampaignQuestResponse]:
    member = await _active_member(db, campaign_id, user.id)
    character = (
        await db.get(Character, member.character_id)
        if member.character_id is not None
        else None
    )
    if (
        character is None
        or character.owner_id != user.id
        or character.campaign_id != campaign_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personagem não encontrado.",
        )
    all_assignments = list(
        (
            await db.scalars(
                select(CharacterQuest).where(CharacterQuest.character_id == character.id)
            )
        ).all()
    )
    active_assignment_ids = [
        assignment.quest_id
        for assignment in all_assignments
        if assignment.status in {"in_progress", "completed"}
    ]
    quests = list(
        (
            await db.scalars(
                select(Quest)
                .where(
                    Quest.campaign_id == campaign_id,
                    or_(
                        Quest.status.in_(("published", "publicado")),
                        Quest.id.in_(active_assignment_ids)
                        if active_assignment_ids
                        else False,
                    ),
                )
                .order_by(Quest.created_at, Quest.id)
            )
        ).all()
    )
    assignments = {
        assignment.quest_id: assignment
        for assignment in all_assignments
        if assignment.quest_id in {quest.id for quest in quests}
    } if quests else {}
    response: list[CampaignQuestResponse] = []
    for quest in quests:
        assignment = assignments.get(quest.id)
        objectives, rewards = _quest_content_response(
            quest,
            assignment.progress if assignment is not None else None,
        )
        response.append(
            CampaignQuestResponse(
                id=quest.id,
                title=quest.title,
                description=quest.description,
                status=assignment.status if assignment is not None else "available",
                progress=(
                    _quest_progress_response(assignment.progress)
                    if assignment is not None
                    else {}
                ),
                objectives=objectives,
                rewards=rewards,
            )
        )
    return response


@router.post(
    "/{campaign_id}/quests/{quest_id}/accept",
    response_model=CampaignQuestAcceptResponse,
)
async def accept_campaign_quest(
    campaign_id: UUID,
    quest_id: UUID,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> CampaignQuestAcceptResponse:
    member = await _active_member(db, campaign_id, user.id)
    character = (
        await db.get(Character, member.character_id)
        if member.character_id is not None
        else None
    )
    if (
        character is None
        or character.owner_id != user.id
        or character.campaign_id != campaign_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personagem não encontrado.",
        )

    await acquire_narrative_campaign_lock(db, campaign_id)
    quest = await db.scalar(
        select(Quest)
        .where(
            Quest.id == quest_id,
            Quest.campaign_id == campaign_id,
            Quest.status.in_(("published", "publicado")),
        )
        .with_for_update()
    )
    if quest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Missão não encontrada.")

    assignment = await db.scalar(
        select(CharacterQuest)
        .where(
            CharacterQuest.character_id == character.id,
            CharacterQuest.quest_id == quest.id,
        )
        .with_for_update()
    )
    if assignment is None:
        assignment = CharacterQuest(
            character_id=character.id,
            quest_id=quest.id,
            status="in_progress",
            progress={
                "objectives": {},
                "title_snapshot": quest.title,
                "reward_snapshot": quest.rewards,
                "conditions_snapshot": quest.conditions,
            },
        )
        db.add(assignment)
    elif assignment.status == "available":
        progress = dict(assignment.progress or {})
        progress["objectives"] = progress.get("objectives", {})
        progress["title_snapshot"] = quest.title
        progress["reward_snapshot"] = quest.rewards
        progress["conditions_snapshot"] = quest.conditions
        assignment.progress = progress
        assignment.status = "in_progress"
    elif assignment.status not in {"in_progress", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta missão não pode ser iniciada no estado atual.",
        )
    await db.commit()
    return CampaignQuestAcceptResponse(
        quest_id=quest.id,
        status=assignment.status,
        progress=_quest_progress_response(assignment.progress),
    )


@router.get("/{campaign_id}/character", response_model=CharacterSheetResponse)
async def get_campaign_character_sheet(
    campaign_id: UUID,
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> CharacterSheetResponse:
    character = await db.scalar(
        select(Character)
        .join(
            CampaignMember,
            (CampaignMember.character_id == Character.id)
            & (CampaignMember.campaign_id == Character.campaign_id)
            & (CampaignMember.user_id == Character.owner_id),
        )
        .where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == user.id,
            CampaignMember.status == "active",
            Character.campaign_id == campaign_id,
            Character.owner_id == user.id,
        )
    )
    if character is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personagem não encontrado.",
        )

    inventory_rows = (
        await db.execute(
            select(CharacterItem, Item)
            .join(Item, Item.id == CharacterItem.item_id)
            .where(CharacterItem.character_id == character.id)
            .order_by(CharacterItem.acquired_at, CharacterItem.id)
        )
    ).all()
    skill_rows = (
        await db.execute(
            select(CharacterSkill, Skill)
            .join(CharacterSkill, CharacterSkill.skill_id == Skill.id)
            .where(CharacterSkill.character_id == character.id)
            .order_by(CharacterSkill.learned_at, CharacterSkill.id)
        )
    ).all()
    quest_rows = (
        await db.execute(
            select(CharacterQuest, Quest)
            .join(Quest, Quest.id == CharacterQuest.quest_id)
            .where(
                CharacterQuest.character_id == character.id,
                Quest.campaign_id == campaign_id,
            )
            .order_by(CharacterQuest.created_at, CharacterQuest.id)
        )
    ).all()
    progression_rows = list(
        (
            await db.scalars(
                select(CharacterRewardGrant)
                .where(CharacterRewardGrant.character_id == character.id)
                .order_by(
                    CharacterRewardGrant.created_at.desc(),
                    CharacterRewardGrant.id.desc(),
                )
                .limit(10)
            )
        ).all()
    )
    progression_items: dict[UUID, list[tuple[UUID, int]]] = {}
    progression_sources: dict[UUID, tuple[UUID | None, str | None]] = {}
    referenced_item_ids: set[UUID] = set()
    for grant in progression_rows:
        raw_source_id = grant.reward_payload.get("source_id")
        raw_source_name = grant.reward_payload.get("source_name")
        if raw_source_id is not None and not isinstance(raw_source_id, str):
            raise RuntimeError("Progression reward history contains an invalid source id.")
        if raw_source_name is not None and not isinstance(raw_source_name, str):
            raise RuntimeError("Progression reward history contains an invalid source name.")
        try:
            source_id = UUID(raw_source_id) if raw_source_id is not None else None
        except ValueError as error:
            raise RuntimeError(
                "Progression reward history contains an invalid source id."
            ) from error
        raw_items = grant.reward_payload.get("items", [])
        if not isinstance(raw_items, list):
            raise RuntimeError("Progression reward history contains invalid items.")
        grant_items: list[tuple[UUID, int]] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                raise RuntimeError("Progression reward history contains an invalid item.")
            try:
                item_id = UUID(str(raw_item["item_id"]))
                quantity = int(raw_item["quantity"])
            except (KeyError, TypeError, ValueError) as error:
                raise RuntimeError(
                    "Progression reward history contains an invalid item."
                ) from error
            grant_items.append((item_id, quantity))
            referenced_item_ids.add(item_id)
        progression_items[grant.id] = grant_items
        progression_sources[grant.id] = (source_id, raw_source_name)
    item_names = (
        {
            item.id: item.name
            for item in (
                await db.scalars(
                    select(Item).where(Item.id.in_(referenced_item_ids))
                )
            ).all()
        }
        if referenced_item_ids
        else {}
    )

    equipped_modifiers = [
        {
            "id": str(item.id),
            "settings": {},
            "attributes": item.attributes if isinstance(item.attributes, dict) else {},
            "effects": item.effects if isinstance(item.effects, dict) else {},
        }
        for character_item, item in inventory_rows
        if character_item.is_equipped
    ]
    attribute_resolution = resolve_character_attributes(
        character,
        equipped_modifiers,
    ).to_dict()

    return CharacterSheetResponse(
        name=character.name,
        description=character.description,
        character_class=character.character_class,
        ancestry=character.ancestry,
        level=character.level,
        xp=character.xp,
        xp_to_next_level=xp_required_for_next_level(character.level),
        xp_progress_percent=xp_progress_percent(character.xp, character.level),
        attribute_points=character.attribute_points,
        gold=character.gold,
        hp=character.hp,
        max_hp=character.max_hp,
        mana=character.mana,
        max_mana=character.max_mana,
        attributes=character.attributes,
        attribute_resolution=attribute_resolution,
        inventory=[
            {
                "item_id": item.id,
                "name": item.name,
                "description": item.description,
                "category": item.category,
                "is_career": (
                    item.category.lower() == "carreira"
                    or (
                        isinstance(item.requirements, dict)
                        and item.requirements.get("is_career") is True
                    )
                ),
                "rarity": item.rarity,
                "image_url": item.image_url,
                "weight": item.weight,
                "effects": item.effects,
                "quantity": character_item.quantity,
                "is_equipped": character_item.is_equipped,
                "slot": character_item.slot,
                "origin": character_item.origin,
            }
            for character_item, item in inventory_rows
        ],
        skills=[
            {
                "id": skill.id,
                "name": skill.name,
                "category": skill.category,
                "description": skill.description,
                "mana_cost": skill.mana_cost,
                "effects": skill.effects,
                "target": skill.target,
                "cooldown_seconds": skill.cooldown_seconds,
                "origin": character_skill.origin,
            }
            for character_skill, skill in skill_rows
        ],
        quests=[
            {
                "id": quest.id,
                "title": quest.title,
                "description": quest.description,
                "status": character_quest.status,
                "progress": _quest_progress_response(character_quest.progress),
                "objectives":                 _quest_content_response(quest, character_quest.progress)[0],
                "rewards": _quest_content_response(quest, character_quest.progress)[1],
            }
            for character_quest, quest in quest_rows
        ],
        progression_history=[
            CharacterProgressionEventResponse(
                id=grant.id,
                created_at=grant.created_at,
                source_type=grant.source_type,
                source_id=progression_sources[grant.id][0],
                source_name=progression_sources[grant.id][1],
                xp_awarded=grant.xp_awarded,
                xp_before=grant.xp_before,
                xp_after=grant.xp_after,
                level_before=grant.level_before,
                level_after=grant.level_after,
                gold_awarded=grant.gold_awarded,
                attribute_points_awarded=(
                    grant.attribute_points_after - grant.attribute_points_before
                ),
                max_hp_increase=grant.max_hp_after - grant.max_hp_before,
                max_mana_increase=grant.max_mana_after - grant.max_mana_before,
                items=[
                    {
                        "item_id": item_id,
                        "name": item_names.get(item_id, "Item indisponível"),
                        "quantity": quantity,
                    }
                    for item_id, quantity in progression_items[grant.id]
                ],
            )
            for grant in progression_rows
        ],
    )


@router.get("/{campaign_id}/members", response_model=list[CampaignMemberResponse])
async def list_campaign_members(
    campaign_id: UUID,
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> list[CampaignMemberResponse]:
    await _active_member(db, campaign_id, user.id)
    return await _member_responses(db, campaign_id)


@router.post("/{campaign_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_campaign(
    campaign_id: UUID,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> Response:
    campaign = await db.scalar(
        select(Campaign)
        .where(Campaign.id == campaign_id)
        .with_for_update()
    )
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campanha não encontrada.")
    member = await db.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == user.id,
            CampaignMember.status == "active",
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campanha não encontrada.",
        )
    member.status = "left"
    member.is_ready = False
    member.last_seen_at = _now()
    campaign.last_activity_at = _now()
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{campaign_id}/character/equipment/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def equip_character_item(
    campaign_id: UUID,
    item_id: UUID,
    payload: EquipmentUpdateRequest,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> Response:
    member = await _active_member(db, campaign_id, user.id)
    if member.character_id is None:
        raise HTTPException(status_code=404, detail="Personagem não encontrado.")

    slot = normalize_slot(payload.slot)
    if slot is None:
        raise HTTPException(status_code=422, detail="Slot de equipamento inválido.")

    inventory = await db.scalar(
        select(CharacterItem)
        .where(
            CharacterItem.character_id == member.character_id,
            CharacterItem.item_id == item_id,
        )
        .with_for_update()
    )
    if inventory is None or inventory.quantity < 1:
        raise HTTPException(status_code=404, detail="Item não está no inventário.")

    item = await db.get(Item, item_id)
    if item is None or not item.is_active:
        raise HTTPException(status_code=404, detail="Item não disponível.")
    item_requirements = item.requirements if isinstance(item.requirements, dict) else {}
    if item.category.lower() == "carreira" or item_requirements.get("is_career") is True:
        origin = inventory.origin if isinstance(inventory.origin, dict) else {}
        if origin.get("mode") != "solo":
            raise HTTPException(
                status_code=422,
                detail="Este item de Carreira não possui elegibilidade de origem solo.",
            )
    if slot not in allowed_slots(item):
        raise HTTPException(status_code=422, detail="O item não pode ser equipado neste slot.")
    character = await db.get(Character, member.character_id)
    requirements_error = equipment_requirements_error(character, item)
    if requirements_error:
        raise HTTPException(status_code=422, detail=requirements_error)
    inventory_rows = (
        await db.execute(
            select(CharacterItem, Item).join(
                Item,
                Item.id == CharacterItem.item_id,
            ).where(CharacterItem.character_id == member.character_id)
        )
    ).all()
    weight = sum(
        item.weight * max(0, character_item.quantity)
        for character_item, item in inventory_rows
    )
    if weight > carry_capacity(character):
        raise HTTPException(status_code=409, detail="Carga máxima excedida.")

    occupied = await db.scalars(
        select(CharacterItem)
        .where(
            CharacterItem.character_id == member.character_id,
            CharacterItem.is_equipped.is_(True),
            CharacterItem.slot == slot,
            CharacterItem.item_id != item_id,
        )
        .with_for_update()
    )
    conflict = next(iter(occupied.all()), None)
    if conflict is not None:
        conflict.is_equipped = False
        conflict.slot = None

    inventory.is_equipped = True
    inventory.slot = slot
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{campaign_id}/character/shop/purchase", status_code=status.HTTP_200_OK)
async def purchase_character_item(
    campaign_id: UUID,
    payload: ShopTransactionRequest,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    member = await _active_member(db, campaign_id, user.id)
    character = await db.scalar(
        select(Character)
        .where(Character.id == member.character_id)
        .with_for_update()
    )
    item = await db.scalar(
        select(Item).where(Item.id == payload.item_id, Item.is_active.is_(True)).with_for_update()
    )
    if character is None or item is None:
        raise HTTPException(status_code=404, detail="Personagem ou item não encontrado.")
    if item.stock < payload.quantity:
        raise HTTPException(status_code=409, detail="Estoque insuficiente.")
    total = item.price * payload.quantity
    if character.gold < total:
        raise HTTPException(status_code=409, detail="Ouro insuficiente.")

    character.gold -= total
    item.stock -= payload.quantity
    inventory = await db.scalar(
        select(CharacterItem).where(
            CharacterItem.character_id == character.id,
            CharacterItem.item_id == item.id,
        )
    )
    if inventory is None:
        inventory = CharacterItem(
            character_id=character.id,
            item_id=item.id,
            quantity=payload.quantity,
        )
        db.add(inventory)
    else:
        inventory.quantity += payload.quantity
    db.add(WalletTransaction(
        character_id=character.id,
        transaction_type="purchase",
        reason=f"Compra: {item.name}",
        amount=max(1, total),
        source_type="item",
        source_id=item.id,
    ))
    await db.commit()
    return {"gold": character.gold, "item_id": str(item.id), "quantity": payload.quantity}


@router.post("/{campaign_id}/character/shop/sell", status_code=status.HTTP_200_OK)
async def sell_character_item(
    campaign_id: UUID,
    payload: ShopTransactionRequest,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    member = await _active_member(db, campaign_id, user.id)
    character = await db.scalar(
        select(Character).where(Character.id == member.character_id).with_for_update()
    )
    item = await db.scalar(
        select(Item).where(Item.id == payload.item_id, Item.is_active.is_(True)).with_for_update()
    )
    inventory = await db.scalar(
        select(CharacterItem)
        .where(
            CharacterItem.character_id == member.character_id,
            CharacterItem.item_id == payload.item_id,
        )
        .with_for_update()
    )
    if character is None or item is None or inventory is None or inventory.quantity < payload.quantity:
        raise HTTPException(status_code=404, detail="Item insuficiente no inventário.")

    sale_value = (item.price * payload.quantity) // 2
    character.gold += sale_value
    inventory.quantity -= payload.quantity
    item.stock += payload.quantity
    if inventory.quantity == 0:
        await db.delete(inventory)
    db.add(WalletTransaction(
        character_id=character.id,
        transaction_type="sale",
        reason=f"Venda: {item.name}",
        amount=max(1, sale_value),
        source_type="item",
        source_id=item.id,
    ))
    await db.commit()
    return {"gold": character.gold, "item_id": str(item.id), "quantity": payload.quantity}


@router.delete(
    "/{campaign_id}/character/equipment/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unequip_character_item(
    campaign_id: UUID,
    item_id: UUID,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> Response:
    member = await _active_member(db, campaign_id, user.id)
    if member.character_id is None:
        raise HTTPException(status_code=404, detail="Personagem não encontrado.")

    inventory = await db.scalar(
        select(CharacterItem)
        .where(
            CharacterItem.character_id == member.character_id,
            CharacterItem.item_id == item_id,
        )
        .with_for_update()
    )
    if inventory is None or inventory.quantity < 1:
        raise HTTPException(status_code=404, detail="Item não está no inventário.")

    inventory.is_equipped = False
    inventory.slot = None
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{campaign_id}/ready", response_model=CampaignResponse)
async def update_ready_status(
    campaign_id: UUID,
    payload: ReadyUpdateRequest,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    member = await _active_member(db, campaign_id, user.id)
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campanha não encontrada.")
    if campaign.status != "waiting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A preparação só pode ser alterada enquanto a sala aguarda participantes.",
        )
    member.is_ready = payload.is_ready
    member.last_seen_at = _now()
    campaign.last_activity_at = _now()
    await db.commit()
    await db.refresh(campaign)
    await db.refresh(member)
    return await _campaign_response(db, campaign, user, member)


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: UUID,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    member = await _active_member(db, campaign_id, user.id)
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")
    if not _is_solo_campaign(campaign):
        raise HTTPException(status_code=422, detail="Este endpoint é exclusivo para campanhas solo.")
    if campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Somente o proprietário pode pausar a campanha.")
    if campaign.status != "in_progress":
        raise HTTPException(status_code=409, detail="A campanha não está em andamento.")
    campaign.status = "paused"
    campaign.last_activity_at = _now()
    await db.commit()
    await db.refresh(campaign)
    return await _campaign_response(db, campaign, user, member)


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(
    campaign_id: UUID,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    member = await _active_member(db, campaign_id, user.id)
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")
    if not _is_solo_campaign(campaign):
        raise HTTPException(status_code=422, detail="Este endpoint é exclusivo para campanhas solo.")
    if campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Somente o proprietário pode retomar a campanha.")
    if campaign.status != "paused":
        raise HTTPException(status_code=409, detail="A campanha não está pausada.")
    campaign.status = "in_progress"
    campaign.last_activity_at = _now()
    await db.commit()
    await db.refresh(campaign)
    return await _campaign_response(db, campaign, user, member)


@router.post("/{campaign_id}/presence", status_code=status.HTTP_204_NO_CONTENT)
async def update_presence(
    campaign_id: UUID,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> Response:
    member = await _active_member(db, campaign_id, user.id)
    member.last_seen_at = _now()
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{campaign_id}/character", response_model=CampaignResponse)
async def update_campaign_character(
    campaign_id: UUID,
    payload: CharacterUpdateRequest,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    member = await _active_member(db, campaign_id, user.id)
    campaign = await db.get(Campaign, campaign_id)
    character = (
        await db.get(Character, member.character_id) if member.character_id is not None else None
    )
    if (
        campaign is None
        or character is None
        or character.owner_id != user.id
        or character.campaign_id != campaign.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personagem não encontrado.",
        )
    character.name = payload.name
    member.last_seen_at = _now()
    campaign.last_activity_at = _now()
    await db.commit()
    await db.refresh(campaign)
    await db.refresh(member)
    return await _campaign_response(db, campaign, user, member)


@router.get(
    "/{campaign_id}/characters",
    response_model=list[SoloCharacterResponse],
)
async def list_solo_characters(
    campaign_id: UUID,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> list[SoloCharacterResponse]:
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None or not _is_solo_campaign(campaign):
        raise HTTPException(status_code=404, detail="Campanha solo não encontrada.")
    member = await _active_member(db, campaign_id, user.id)
    if campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Acesso à campanha solo negado.")
    rows = (
        await db.scalars(
            select(Character)
            .where(
                Character.campaign_id == campaign_id,
                Character.owner_id == user.id,
                Character.status == "active",
            )
            .order_by(Character.created_at, Character.id)
        )
    ).all()
    return [
        SoloCharacterResponse(
            id=character.id,
            name=character.name,
            character_class=character.character_class,
            ancestry=character.ancestry,
            level=character.level,
            hp=character.hp,
            max_hp=character.max_hp,
            active=character.id == member.character_id,
        )
        for character in rows
    ]


@router.post(
    "/{campaign_id}/characters",
    response_model=SoloCharacterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_solo_character(
    campaign_id: UUID,
    payload: SoloCharacterCreateRequest,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> SoloCharacterResponse:
    campaign = await db.scalar(
        select(Campaign).where(Campaign.id == campaign_id).with_for_update()
    )
    if campaign is None or not _is_solo_campaign(campaign):
        raise HTTPException(status_code=404, detail="Campanha solo não encontrada.")
    await _active_member(db, campaign_id, user.id)
    if campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Acesso à campanha solo negado.")
    if campaign.status not in {"waiting", "paused"}:
        raise HTTPException(
            status_code=409,
            detail="Crie personagens enquanto a campanha aguarda ou está pausada.",
        )
    characters = (
        await db.scalars(
            select(Character).where(
                Character.campaign_id == campaign_id,
                Character.owner_id == user.id,
                Character.status == "active",
            )
        )
    ).all()
    if len(characters) >= 5:
        raise HTTPException(status_code=409, detail="A campanha solo permite até cinco personagens.")
    character = Character(
        owner_id=user.id,
        campaign_id=campaign.id,
        name=payload.name,
    )
    db.add(character)
    await db.flush()
    if not characters:
        member = await _active_member(db, campaign_id, user.id)
        member.character_id = character.id
    await db.commit()
    return SoloCharacterResponse(
        id=character.id,
        name=character.name,
        character_class=character.character_class,
        ancestry=character.ancestry,
        level=character.level,
        hp=character.hp,
        max_hp=character.max_hp,
        active=not characters,
    )


@router.put(
    "/{campaign_id}/characters/{character_id}/active",
    response_model=SoloCharacterResponse,
)
async def select_solo_character(
    campaign_id: UUID,
    character_id: UUID,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> SoloCharacterResponse:
    campaign = await db.scalar(
        select(Campaign).where(Campaign.id == campaign_id).with_for_update()
    )
    if campaign is None or not _is_solo_campaign(campaign):
        raise HTTPException(status_code=404, detail="Campanha solo não encontrada.")
    member = await _active_member(db, campaign_id, user.id)
    if campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Acesso à campanha solo negado.")
    if campaign.status not in {"waiting", "paused"}:
        raise HTTPException(
            status_code=409,
            detail="Troque de personagem enquanto a campanha aguarda ou está pausada.",
        )
    character = await db.scalar(
        select(Character).where(
            Character.id == character_id,
            Character.campaign_id == campaign_id,
            Character.owner_id == user.id,
            Character.status == "active",
        )
    )
    if character is None:
        raise HTTPException(status_code=404, detail="Personagem não encontrado nesta campanha.")
    member.character_id = character.id
    await db.commit()
    return SoloCharacterResponse(
        id=character.id,
        name=character.name,
        character_class=character.character_class,
        ancestry=character.ancestry,
        level=character.level,
        hp=character.hp,
        max_hp=character.max_hp,
        active=True,
    )


@router.post("/{campaign_id}/members/kick")
async def kick_campaign_member(
    campaign_id: UUID,
    payload: CampaignMemberActionRequest,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> Response:
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None or campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Somente o proprietário pode expulsar participantes.")
    if payload.user_id == user.id:
        raise HTTPException(status_code=409, detail="O proprietário não pode expulsar a si mesmo.")
    member = await db.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == payload.user_id,
            CampaignMember.status == "active",
        ).with_for_update()
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Participante não encontrado.")
    member.status = "kicked"
    member.is_ready = False
    campaign.last_activity_at = _now()
    await db.commit()
    return Response(status_code=204)


@router.post("/{campaign_id}/members/transfer")
async def transfer_campaign_ownership(
    campaign_id: UUID,
    payload: CampaignMemberActionRequest,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> Response:
    campaign = await db.scalar(select(Campaign).where(Campaign.id == campaign_id).with_for_update())
    if campaign is None or campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Somente o proprietário pode transferir a campanha.")
    target = await db.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == payload.user_id,
            CampaignMember.status == "active",
        ).with_for_update()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Participante ativo não encontrado.")
    current = await db.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == user.id,
            CampaignMember.status == "active",
        ).with_for_update()
    )
    campaign.owner_id = target.user_id
    if current is not None:
        current.role = "member"
    target.role = "owner"
    await db.commit()
    return Response(status_code=204)


@router.post("/{campaign_id}/members/narrator")
async def set_campaign_narrator(
    campaign_id: UUID,
    payload: CampaignMemberActionRequest,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> Response:
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None or campaign.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Somente o proprietário pode nomear narrador.")
    member = await db.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == payload.user_id,
            CampaignMember.status == "active",
        ).with_for_update()
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Participante ativo não encontrado.")
    member.role = "narrator"
    await db.commit()
    return Response(status_code=204)


@router.post("/{campaign_id}/start", response_model=CampaignResponse)
async def start_campaign(
    campaign_id: UUID,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> CampaignResponse:
    campaign = await db.scalar(
        select(Campaign)
        .where(Campaign.id == campaign_id)
        .with_for_update()
    )
    member = await db.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == user.id,
            CampaignMember.status == "active",
        )
    )
    if campaign is None or member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campanha não encontrada.",
        )
    if campaign.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente o proprietário da sala pode iniciar a campanha.",
        )
    if campaign.status != "waiting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A campanha não está aguardando para iniciar.",
        )

    active_members = await db.scalars(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign.id,
            CampaignMember.status == "active",
        )
    )
    members = list(active_members.all())
    participant_count = len(members)
    if participant_count < campaign.min_players:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"São necessários pelo menos {campaign.min_players} participantes ativos para iniciar.",
        )
    if participant_count > campaign.max_players:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"O limite desta sala é de {campaign.max_players} participantes.",
        )
    valid_character_count = await db.scalar(
        select(func.count(Character.id))
        .join(
            CampaignMember,
            (CampaignMember.character_id == Character.id)
            & (CampaignMember.user_id == Character.owner_id)
            & (CampaignMember.campaign_id == Character.campaign_id),
        )
        .where(
            CampaignMember.campaign_id == campaign.id,
            CampaignMember.status == "active",
            Character.campaign_id == campaign.id,
        )
    )
    if valid_character_count != participant_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Todos os participantes precisam ter um personagem associado.",
        )

    snapshot = await _published_story_snapshot(db)
    _validate_story_snapshot(snapshot)
    initial_location = next(
        (
            (chapter, scene)
            for chapter in snapshot
            for scene in chapter["scenes"]
        ),
        None,
    )
    if initial_location is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Publique um capítulo ativo com ao menos uma cena antes de iniciar a campanha.",
        )
    initial_chapter, initial_scene = initial_location
    initial_node_id = UUID(str(initial_scene["id"]))
    now = _now()
    eligible_user_ids = [str(active_member.user_id) for active_member in members]
    voting_settings = _session_voting_settings(campaign)
    session_state: dict[str, object] = {
        "version": 1,
        "content_snapshot": snapshot,
        "current_chapter_id": str(initial_chapter["id"]),
        "current_node_id": str(initial_node_id),
        "voting_settings": voting_settings,
        "round_numbers": {},
        "applied_consequences": [],
    }
    initial_vote = _open_vote(
        session_state,
        initial_scene,
        eligible_user_ids,
        voting_settings,
        now,
    )
    if initial_vote is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A cena inicial precisa ter ao menos uma escolha para iniciar a campanha.",
        )
    session_state["vote"] = initial_vote
    game_session = GameSession(
        campaign_id=campaign.id,
        current_node_id=initial_node_id,
        status="running",
        state=session_state,
        started_at=now,
    )
    db.add(game_session)
    await db.flush()
    db.add(
        GameEvent(
            session_id=game_session.id,
            sequence_number=1,
            actor_user_id=user.id,
            event_type="campaign_started",
            payload={
                "campaign_id": str(campaign.id),
                "chapter_id": str(initial_chapter["id"]),
                "chapter_title": str(initial_chapter["title"]),
                "node_id": str(initial_node_id),
                "scene_title": str(initial_scene["title"]),
            },
            idempotency_key=f"campaign-start:{campaign.id}",
        )
    )
    campaign.status = "in_progress"
    campaign.current_chapter_id = UUID(str(initial_chapter["id"]))
    campaign.current_node_id = initial_node_id
    campaign.last_activity_at = now
    await db.commit()
    await db.refresh(campaign)
    await db.refresh(member)
    return await _campaign_response(db, campaign, user, member)


@router.get("/{campaign_id}/game", response_model=NarrativeGameResponse)
async def get_narrative_game(
    campaign_id: UUID,
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> NarrativeGameResponse:
    await _active_member(db, campaign_id, user.id)
    campaign = await db.get(Campaign, campaign_id)
    game_session = await db.scalar(
        select(GameSession)
        .where(GameSession.campaign_id == campaign_id)
        .order_by(GameSession.started_at.desc(), GameSession.id.desc())
        .limit(1)
    )
    if campaign is None or game_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sessão narrativa não encontrada.",
        )
    if not isinstance((game_session.state or {}).get("content_snapshot"), list):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Esta sessão foi iniciada antes do snapshot narrativo e não pode ser retomada "
                "com segurança."
            ),
        )
    raw_vote = (game_session.state or {}).get("vote")
    if (
        game_session.status == "running"
        and isinstance(raw_vote, dict)
        and raw_vote.get("status") == "open"
        and isinstance(raw_vote.get("deadline_at"), str)
        and _aware(datetime.fromisoformat(raw_vote["deadline_at"])) <= _now()
    ):
        await acquire_narrative_campaign_lock(db, campaign_id)
        game_session = await db.scalar(
            select(GameSession)
            .where(GameSession.id == game_session.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if game_session is None:
            raise RuntimeError("Narrative session disappeared during vote closure.")
        refreshed_vote = (game_session.state or {}).get("vote")
        if (
            game_session.status == "running"
            and isinstance(refreshed_vote, dict)
            and refreshed_vote.get("status") == "open"
            and isinstance(refreshed_vote.get("deadline_at"), str)
            and _aware(datetime.fromisoformat(refreshed_vote["deadline_at"])) <= _now()
        ):
            await _close_vote_if_ready(
                db,
                campaign,
                game_session,
                now=_now(),
                deadline_elapsed=True,
            )
            await db.commit()
    return await _narrative_response(db, campaign, game_session, user)


@router.post(
    "/{campaign_id}/game/vote",
    response_model=NarrativeGameResponse,
)
async def cast_narrative_vote(
    campaign_id: UUID,
    payload: StoryVoteRequest,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> NarrativeGameResponse:
    await acquire_narrative_campaign_lock(db, campaign_id)
    member = await db.scalar(
        select(CampaignMember)
        .where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == user.id,
            CampaignMember.status == "active",
        )
        .with_for_update()
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campanha não encontrada.",
        )
    campaign = await db.get(Campaign, campaign_id)
    game_session = await db.scalar(
        select(GameSession)
        .where(GameSession.campaign_id == campaign_id, GameSession.status == "running")
        .order_by(GameSession.started_at.desc(), GameSession.id.desc())
        .limit(1)
        .with_for_update()
    )
    if campaign is None or game_session is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A campanha não possui uma sessão narrativa aberta.",
        )

    state = game_session.state or {}
    raw_vote = state.get("vote")
    if not isinstance(raw_vote, dict) or raw_vote.get("status") != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não há uma votação aberta para esta cena.",
        )
    eligible_user_ids = raw_vote.get("eligible_user_ids", [])
    if not isinstance(eligible_user_ids, list) or str(user.id) not in eligible_user_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não participa desta votação.",
        )
    deadline_at = raw_vote.get("deadline_at")
    if isinstance(deadline_at, str) and _aware(datetime.fromisoformat(deadline_at)) <= _now():
        await _close_vote_if_ready(
            db,
            campaign,
            game_session,
            now=_now(),
            actor_user_id=user.id,
            deadline_elapsed=True,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O prazo desta votação terminou.",
        )

    node_id = UUID(str(state.get("current_node_id", "")))
    raw_round_number = raw_vote.get("round_number")
    if not isinstance(raw_round_number, int):
        raise RuntimeError("Narrative vote round number is invalid.")
    snapshot = state.get("content_snapshot")
    if not isinstance(snapshot, list):
        raise RuntimeError("Narrative session is missing its content snapshot.")
    location = _scene_in_snapshot(snapshot, str(node_id))
    if location is None:
        raise RuntimeError("Current scene is missing from the narrative snapshot.")
    _, scene = location
    choice_in_snapshot = next(
        (
            choice
            for choice in scene.get("choices", [])
            if isinstance(choice, dict) and choice.get("id") == str(payload.choice_id)
        ),
        None,
    )
    stored_choice = await db.scalar(
        select(StoryChoice).where(
            StoryChoice.id == payload.choice_id,
            StoryChoice.node_id == node_id,
        )
    )
    if choice_in_snapshot is None or stored_choice is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A escolha não pertence à cena atual desta sessão.",
        )

    ballot = await db.scalar(
        select(StoryVote)
        .where(
            StoryVote.session_id == game_session.id,
            StoryVote.node_id == node_id,
            StoryVote.round_number == raw_round_number,
            StoryVote.user_id == user.id,
        )
        .with_for_update()
    )
    if ballot is not None and ballot.choice_id == payload.choice_id:
        return await _narrative_response(db, campaign, game_session, user)
    if ballot is not None and not raw_vote.get("allow_vote_change", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seu voto já foi registrado e não pode ser alterado.",
        )

    event_type = "vote_cast"
    if ballot is None:
        ballot = StoryVote(
            session_id=game_session.id,
            node_id=node_id,
            choice_id=payload.choice_id,
            user_id=user.id,
            round_number=raw_round_number,
        )
        db.add(ballot)
    else:
        event_type = "vote_changed"
        ballot.choice_id = payload.choice_id
    await db.flush()
    await _append_game_event(
        db,
        game_session,
        event_type=event_type,
        payload={
            "node_id": str(node_id),
            "round_number": raw_round_number,
            "choice_id": str(payload.choice_id),
            "choice_label": str(choice_in_snapshot["label"]),
        },
        idempotency_key=_vote_event_idempotency_key(
            event_type,
            game_session.id,
            node_id,
            raw_round_number,
            user.id,
            len((state.get("vote_events") or [])) + 1,
        ),
        actor_user_id=user.id,
    )
    vote_events = state.setdefault("vote_events", [])
    if not isinstance(vote_events, list):
        raise RuntimeError("Narrative vote event state is invalid.")
    vote_events.append(
        {
            "node_id": str(node_id),
            "round_number": raw_round_number,
            "user_id": str(user.id),
            "choice_id": str(payload.choice_id),
            "event_type": event_type,
        }
    )
    game_session.state = state
    await _close_vote_if_ready(
        db,
        campaign,
        game_session,
        now=_now(),
        actor_user_id=user.id,
    )
    campaign.last_activity_at = _now()
    await db.commit()
    return await _narrative_response(db, campaign, game_session, user)
