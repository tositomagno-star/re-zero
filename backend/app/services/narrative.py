import asyncio
import hashlib
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import UUID
from weakref import WeakValueDictionary

from fastapi import HTTPException, status
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Campaign,
    CampaignMember,
    Character,
    CharacterQuest,
    CharacterRewardGrant,
    Chapter,
    GameEvent,
    GameSession,
    Item,
    Quest,
    StoryChoice,
    StoryNode,
    StoryVote,
    User,
    WorldReward,
)
from app.schemas.campaigns import NarrativeGameResponse
from app.services.campaigns import _aware, _member_responses
from app.services.progression import apply_world_reward, complete_character_quest

__all__ = [
    "acquire_narrative_campaign_lock",
    "_append_game_event",
    "_close_vote_if_ready",
    "_narrative_response",
    "_next_story_scene",
    "_open_vote",
    "_published_story_snapshot",
    "_resolve_vote_result",
    "_scene_in_snapshot",
    "_session_voting_settings",
    "_validate_story_snapshot",
    "_vote_event_idempotency_key",
]

_NARRATIVE_CAMPAIGN_LOCKS: WeakValueDictionary[tuple[int, UUID], asyncio.Lock] = (
    WeakValueDictionary()
)


def _release_narrative_campaign_locks(sync_session, transaction) -> None:
    if transaction.parent is not None:
        return
    locks = sync_session.info.pop("narrative_pending_locks", {})
    sync_session.info.pop("narrative_lock_keys", None)
    for lock in locks.values():
        lock.release()


async def acquire_narrative_campaign_lock(
    db: AsyncSession,
    campaign_id: UUID,
) -> None:
    key = (id(db.get_bind().pool), campaign_id)
    lock = _NARRATIVE_CAMPAIGN_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _NARRATIVE_CAMPAIGN_LOCKS[key] = lock

    sync_session = db.sync_session
    held_keys = sync_session.info.setdefault("narrative_lock_keys", set())
    if key in held_keys:
        return
    await lock.acquire()
    held_keys.add(key)
    sync_session.info.setdefault("narrative_pending_locks", {})[key] = lock
    if not sync_session.info.get("narrative_lock_listener"):
        event.listen(
            sync_session,
            "after_transaction_end",
            _release_narrative_campaign_locks,
        )
        sync_session.info["narrative_lock_listener"] = True


def _vote_event_idempotency_key(
    event_type: str,
    session_id: UUID,
    node_id: UUID,
    round_number: int,
    user_id: UUID,
    event_number: int,
) -> str:
    identity = (
        f"{session_id}:{node_id}:{round_number}:{user_id}:{event_number}".encode()
    )
    digest = hashlib.sha256(identity).hexdigest()
    return f"{event_type}:{digest}"


def _consequence_ids(
    consequences: object,
    field: str,
) -> list[UUID]:
    if not isinstance(consequences, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="As consequências da escolha estão inválidas.",
        )
    raw_ids = consequences.get(field, [])
    if (
        not isinstance(raw_ids, list)
        or len(raw_ids) > 100
        or any(not isinstance(value, str) for value in raw_ids)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A lista {field} da consequência está inválida.",
        )
    try:
        identifiers = [UUID(value) for value in raw_ids]
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A lista {field} contém um identificador inválido.",
        ) from error
    if len(identifiers) != len(set(identifiers)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A lista {field} não pode repetir identificadores.",
        )
    return identifiers


def _consequence_objective_updates(consequences: object) -> list[dict[str, object]]:
    if not isinstance(consequences, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="As consequências da escolha estão inválidas.",
        )
    raw_updates = consequences.get("quest_objective_updates", [])
    if not isinstance(raw_updates, list) or len(raw_updates) > 100:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A lista de atualizações de objetivos está inválida.",
        )
    updates: list[dict[str, object]] = []
    seen: set[tuple[UUID, str]] = set()
    for update in raw_updates:
        if not isinstance(update, dict):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Uma atualização de objetivo está inválida.",
            )
        try:
            quest_id = UUID(update["quest_id"])
            objective_id = update["objective_id"]
            amount = update.get("amount", 1)
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Uma atualização de objetivo está inválida.",
            ) from error
        if (
            not isinstance(objective_id, str)
            or not objective_id
            or len(objective_id) > 64
            or not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount < 1
            or amount > 1_000_000
            or (quest_id, objective_id) in seen
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Uma atualização de objetivo contém valores inválidos ou duplicados.",
            )
        seen.add((quest_id, objective_id))
        updates.append(
            {"quest_id": quest_id, "objective_id": objective_id, "amount": amount}
        )
    return updates


async def _apply_choice_rewards(
    db: AsyncSession,
    campaign: Campaign,
    game_session: GameSession,
    *,
    choice: dict[str, object],
    decision_key: str,
    eligible_user_ids: list[str],
    actor_user_id: UUID | None,
) -> list[dict[str, object]]:
    consequences = choice.get("consequences", {})
    world_reward_ids = _consequence_ids(consequences, "world_reward_ids")
    quest_ids = _consequence_ids(consequences, "complete_quest_ids")
    objective_updates = _consequence_objective_updates(consequences)
    if not world_reward_ids and not quest_ids and not objective_updates:
        return []

    eligible_ids = [UUID(user_id) for user_id in eligible_user_ids]
    participants = list(
        (
            await db.execute(
                select(CampaignMember, Character)
                .outerjoin(
                    Character,
                    (Character.id == CampaignMember.character_id)
                    & (Character.campaign_id == CampaignMember.campaign_id)
                    & (Character.owner_id == CampaignMember.user_id),
                )
                .where(
                    CampaignMember.campaign_id == campaign.id,
                    CampaignMember.status == "active",
                    CampaignMember.user_id.in_(eligible_ids),
                )
                .order_by(CampaignMember.joined_at, CampaignMember.id)
                .with_for_update()
            )
        ).all()
    )
    if not participants:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não há personagens participantes ativos para receber a recompensa.",
        )
    if any(character is None for _, character in participants):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Todos os participantes ativos precisam de um personagem vinculado corretamente.",
        )
    participants = [
        (member, character)
        for member, character in participants
        if character is not None
    ]

    reward_records: list[WorldReward] = []
    if world_reward_ids:
        reward_records = list(
            (
                await db.scalars(
                    select(WorldReward)
                    .where(WorldReward.id.in_(world_reward_ids))
                    .order_by(WorldReward.id)
                    .with_for_update()
                )
            ).all()
        )
        rewards_by_id = {reward.id: reward for reward in reward_records}
        if set(rewards_by_id) != set(world_reward_ids):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Uma recompensa narrativa não existe mais.",
            )
        if any(not reward.is_active for reward in reward_records):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Uma recompensa narrativa está inativa.",
            )
        reward_records = [rewards_by_id[reward_id] for reward_id in world_reward_ids]
    referenced_quest_ids = list(
        dict.fromkeys(
            quest_ids
            + [update["quest_id"] for update in objective_updates]
        )
    )
    quest_records: list[Quest] = []
    if referenced_quest_ids:
        quest_records = list(
            (
                await db.scalars(
                    select(Quest)
                    .where(
                        Quest.id.in_(referenced_quest_ids),
                        Quest.campaign_id == campaign.id,
                    )
                    .with_for_update()
                )
            ).all()
        )
        if {quest.id for quest in quest_records} != set(referenced_quest_ids):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Uma missão da consequência não existe nesta campanha.",
            )
        quests_by_id = {quest.id: quest for quest in quest_records}
        quest_records = [
            quests_by_id[quest_id] for quest_id in referenced_quest_ids
        ]

    item_ids: set[UUID] = set()
    for reward in reward_records:
        try:
            parsed_item_ids = [UUID(item_id) for item_id in reward.item_ids]
        except (TypeError, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Uma recompensa narrativa contém um item inválido.",
            ) from error
        if len(parsed_item_ids) != len(set(parsed_item_ids)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Uma recompensa narrativa não pode repetir itens.",
            )
        item_ids.update(parsed_item_ids)
    for quest in quest_records:
        if not isinstance(quest.rewards, dict):
            continue
        raw_items = quest.rewards.get("items", [])
        if not isinstance(raw_items, list):
            continue
        for raw_item in raw_items:
            if isinstance(raw_item, dict) and isinstance(raw_item.get("item_id"), str):
                try:
                    item_ids.add(UUID(raw_item["item_id"]))
                except ValueError:
                    continue
    reward_items = (
        {
            item.id: item
            for item in (
                await db.scalars(select(Item).where(Item.id.in_(item_ids)))
            ).all()
        }
        if item_ids
        else {}
    )

    granted: list[dict[str, object]] = []
    updated_objectives: list[dict[str, object]] = []
    for member, character in participants:
        for reward in reward_records:
            result = await apply_world_reward(
                db,
                campaign_id=campaign.id,
                character_id=character.id,
                idempotency_key=(
                    f"narrative:{hashlib.sha256(f'{decision_key}:{reward.id}'.encode()).hexdigest()}"
                ),
                reward_id=reward.id,
                source_type="narrative",
            )
            if not result.already_applied:
                granted.append(
                    {
                        "character_name": character.name,
                        "source_type": "narrative",
                        "title": reward.title,
                        "xp": result.xp_awarded,
                        "gold": result.gold_awarded,
                        "level_before": result.level_before,
                        "level_after": result.level_after,
                        "items": [
                            {
                                "name": reward_items[UUID(item_id)].name,
                                "quantity": 1,
                            }
                            for item_id in reward.item_ids
                            if UUID(item_id) in reward_items
                        ],
                    }
                )
        for update in objective_updates:
            quest_id = update["quest_id"]
            quest = next((item for item in quest_records if item.id == quest_id), None)
            if quest is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A missão de um objetivo não está disponível.",
                )
            assignment = await db.scalar(
                select(CharacterQuest)
                .where(
                    CharacterQuest.character_id == character.id,
                    CharacterQuest.quest_id == quest.id,
                )
                .with_for_update()
            )
            if assignment is None or assignment.status != "in_progress":
                continue
            progress = dict(assignment.progress or {})
            raw_conditions = progress.get("conditions_snapshot", quest.conditions)
            conditions = raw_conditions if isinstance(raw_conditions, dict) else {}
            objectives = conditions.get("objectives", [])
            objective = next(
                (
                    item
                    for item in objectives
                    if isinstance(item, dict)
                    and item.get("id") == update["objective_id"]
                ),
                None,
            ) if isinstance(objectives, list) else None
            if (
                objective is None
                or not isinstance(objective.get("target"), int)
                or isinstance(objective.get("target"), bool)
                or not isinstance(objective.get("title"), str)
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="O objetivo referenciado pela escolha não existe nesta missão.",
                )
            objective_progress = progress.get("objectives", {})
            if not isinstance(objective_progress, dict):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="O progresso dos objetivos da missão está inválido.",
                )
            objective_events = progress.get("objective_events", {})
            if not isinstance(objective_events, dict):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="O histórico de objetivos da missão está inválido.",
                )
            marker = hashlib.sha256(
                f"{decision_key}:{quest.id}:{update['objective_id']}".encode()
            ).hexdigest()
            if marker in objective_events:
                continue
            old_count = objective_progress.get(update["objective_id"], 0)
            if not isinstance(old_count, int) or isinstance(old_count, bool) or old_count < 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="O progresso numérico de um objetivo está inválido.",
                )
            new_count = min(
                objective["target"],
                old_count + update["amount"],
            )
            objective_progress[update["objective_id"]] = new_count
            objective_events[marker] = True
            progress["objectives"] = objective_progress
            progress["objective_events"] = objective_events
            assignment.progress = progress
            updated_objectives.append(
                {
                    "character_name": character.name,
                    "quest_title": quest.title,
                    "objective_id": update["objective_id"],
                    "objective_title": objective["title"],
                    "progress": new_count,
                    "target": objective["target"],
                }
            )

        for quest in [item for item in quest_records if item.id in quest_ids]:
            quest_id = quest.id
            reward_key = (
                f"quest:{hashlib.sha256(f'{decision_key}:{quest_id}'.encode()).hexdigest()}"
            )
            result = await complete_character_quest(
                db,
                campaign_id=campaign.id,
                character_id=character.id,
                quest_id=quest_id,
                idempotency_key=reward_key,
            )
            if result is None or result.already_applied:
                continue
            grant = await db.get(CharacterRewardGrant, result.grant_id)
            if grant is None or not isinstance(grant.reward_payload, dict):
                raise RuntimeError("The mission reward grant is missing its audit payload.")
            raw_grant_items = grant.reward_payload.get("items", [])
            if not isinstance(raw_grant_items, list):
                raise RuntimeError("The mission reward grant contains invalid items.")
            awarded_items: list[dict[str, object]] = []
            for raw_item in raw_grant_items:
                if not isinstance(raw_item, dict):
                    raise RuntimeError("The mission reward grant contains an invalid item.")
                try:
                    item_id = UUID(str(raw_item["item_id"]))
                    quantity = int(raw_item["quantity"])
                except (KeyError, TypeError, ValueError) as error:
                    raise RuntimeError(
                        "The mission reward grant contains an invalid item."
                    ) from error
                item = reward_items.get(item_id)
                if item is None:
                    item = await db.get(Item, item_id)
                if item is not None:
                    awarded_items.append({"name": item.name, "quantity": quantity})
            granted.append(
                {
                    "character_name": character.name,
                    "source_type": "quest",
                    "title": grant.reward_payload.get("source_name", quest.title),
                    "xp": result.xp_awarded,
                    "gold": result.gold_awarded,
                    "level_before": result.level_before,
                    "level_after": result.level_after,
                    "items": awarded_items,
                }
            )

    if granted or updated_objectives:
        await _append_game_event(
            db,
            game_session,
            event_type="quest_progress_updated" if updated_objectives and not granted else "rewards_granted",
            payload={
                "chapter_id": str(game_session.state.get("current_chapter_id", "")),
                "node_id": str(game_session.state.get("current_node_id", "")),
                "choice_id": str(choice.get("id", "")),
                "rewards": granted,
                "objective_updates": updated_objectives,
            },
            idempotency_key=(
                f"rewards:{hashlib.sha256(decision_key.encode()).hexdigest()}"
            ),
            actor_user_id=actor_user_id,
        )
    return granted


async def _published_story_snapshot(db: AsyncSession) -> list[dict[str, object]]:
    chapters = list(
        (
            await db.scalars(
                select(Chapter)
                .where(
                    Chapter.campaign_id.is_(None),
                    Chapter.status.in_(("published", "publicado")),
                    Chapter.is_active.is_(True),
                )
                .order_by(Chapter.position, Chapter.id)
                .with_for_update()
            )
        ).all()
    )
    snapshot: list[dict[str, object]] = []
    for chapter in chapters:
        nodes = list(
            (
                await db.scalars(
                    select(StoryNode)
                    .where(StoryNode.chapter_id == chapter.id, StoryNode.is_active.is_(True))
                    .order_by(StoryNode.position, StoryNode.id)
                    .with_for_update()
                )
            ).all()
        )
        scenes: list[dict[str, object]] = []
        for node in nodes:
            choices = list(
                (
                    await db.scalars(
                        select(StoryChoice)
                        .where(StoryChoice.node_id == node.id)
                        .order_by(StoryChoice.position, StoryChoice.id)
                        .with_for_update()
                    )
                ).all()
            )
            scenes.append(
                {
                    "id": str(node.id),
                    "title": node.title,
                    "narrative": node.narrative,
                    "position": node.position,
                    "data": deepcopy(node.data or {}),
                    "choices": [
                        {
                            "id": str(choice.id),
                            "label": choice.label,
                            "position": choice.position,
                            "next_node_id": (
                                str(choice.next_node_id)
                                if choice.next_node_id is not None
                                else None
                            ),
                            "conditions": deepcopy(choice.conditions or {}),
                            "consequences": deepcopy(choice.consequences or {}),
                        }
                        for choice in choices
                    ],
                }
            )
        snapshot.append(
            {
                "id": str(chapter.id),
                "title": chapter.title,
                "summary": chapter.summary,
                "narrative": chapter.narrative,
                "position": chapter.position,
                "scenes": scenes,
            }
        )
    return snapshot


async def _append_game_event(
    db: AsyncSession,
    game_session: GameSession,
    *,
    event_type: str,
    payload: dict[str, object],
    idempotency_key: str,
    actor_user_id: UUID | None = None,
) -> GameEvent:
    last_sequence = await db.scalar(
        select(func.max(GameEvent.sequence_number)).where(
            GameEvent.session_id == game_session.id
        )
    )
    event = GameEvent(
        session_id=game_session.id,
        sequence_number=(last_sequence or 0) + 1,
        actor_user_id=actor_user_id,
        event_type=event_type,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    db.add(event)
    await db.flush()
    return event


def _session_voting_settings(campaign: Campaign) -> dict[str, object]:
    settings = campaign.settings or {}
    if not isinstance(settings, dict):
        raise RuntimeError("Campaign settings are not a valid object.")
    configured = settings.get("narrative_voting", {})
    if not isinstance(configured, dict):
        raise RuntimeError("Campaign voting settings are not a valid object.")
    allow_vote_change = configured.get("allow_vote_change", True)
    deadline_seconds = configured.get("deadline_seconds")
    tie_breaker = configured.get("tie_breaker", "unresolved")
    if (
        not isinstance(allow_vote_change, bool)
        or (
            deadline_seconds is not None
            and (
                not isinstance(deadline_seconds, int)
                or isinstance(deadline_seconds, bool)
                or deadline_seconds <= 0
            )
        )
        or not isinstance(tie_breaker, str)
        or tie_breaker not in {"unresolved", "choice_order"}
    ):
        raise RuntimeError("Campaign voting settings contain an invalid value.")
    return {
        "allow_vote_change": allow_vote_change,
        "deadline_seconds": deadline_seconds,
        "tie_breaker": tie_breaker,
    }


def _open_vote(
    state: dict[str, object],
    scene: dict[str, object],
    eligible_user_ids: list[str],
    voting_settings: dict[str, object],
    now: datetime,
) -> dict[str, object] | None:
    choices = scene.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return None
    scene_id = str(scene["id"])
    rounds = state.setdefault("round_numbers", {})
    if not isinstance(rounds, dict):
        raise RuntimeError("Narrative session round state is not a valid object.")
    round_number = int(rounds.get(scene_id, 0)) + 1
    rounds[scene_id] = round_number
    deadline_seconds = voting_settings["deadline_seconds"]
    deadline = (
        now + timedelta(seconds=deadline_seconds)
        if isinstance(deadline_seconds, int)
        else None
    )
    return {
        "status": "open",
        "round_number": round_number,
        "started_at": now.isoformat(),
        "deadline_at": deadline.isoformat() if deadline is not None else None,
        "eligible_user_ids": eligible_user_ids,
        "allow_vote_change": voting_settings["allow_vote_change"],
        "tie_breaker": voting_settings["tie_breaker"],
    }


def _resolve_vote_result(
    scene: dict[str, object],
    eligible_votes: list[StoryVote],
    round_number: int,
    now: datetime,
    tie_breaker: object,
) -> tuple[dict[str, object], dict[str, object] | None]:
    choices = scene.get("choices", [])
    if not isinstance(choices, list):
        raise RuntimeError("Narrative scene choices are invalid.")
    choice_by_id = {
        str(choice["id"]): choice
        for choice in choices
        if isinstance(choice, dict) and "id" in choice
    }
    counts = {choice_id: 0 for choice_id in choice_by_id}
    for ballot in eligible_votes:
        if str(ballot.choice_id) in counts:
            counts[str(ballot.choice_id)] += 1
    tally = [
        {
            "choice_id": choice_id,
            "label": str(choice_by_id[choice_id]["label"]),
            "votes": count,
        }
        for choice_id, count in counts.items()
    ]
    result: dict[str, object] = {
        "round_number": round_number,
        "tally": tally,
        "resolved_at": now.isoformat(),
    }
    selected_choice: dict[str, object] | None = None
    if not eligible_votes:
        result["status"] = "no_votes"
    else:
        highest_count = max(counts.values(), default=0)
        leaders = [
            choice_by_id[choice_id]
            for choice_id, count in counts.items()
            if count == highest_count
        ]
        if len(leaders) > 1 and tie_breaker == "choice_order":
            selected_choice = min(
                leaders,
                key=lambda choice: (int(choice["position"]), str(choice["id"])),
            )
            result["tie_breaker"] = "choice_order"
        elif len(leaders) > 1:
            result["status"] = "tied"
        else:
            selected_choice = leaders[0]

    if selected_choice is None and result.get("status") not in {"tied", "no_votes"}:
        raise RuntimeError("Narrative vote could not be resolved.")
    return result, selected_choice


def _scene_in_snapshot(
    snapshot: list[dict[str, object]],
    node_id: str,
) -> tuple[dict[str, object], dict[str, object]] | None:
    for chapter in snapshot:
        scenes = chapter.get("scenes", [])
        if not isinstance(scenes, list):
            continue
        for scene in scenes:
            if isinstance(scene, dict) and scene.get("id") == node_id:
                return chapter, scene
    return None


def _validate_story_snapshot(snapshot: list[dict[str, object]]) -> None:
    for chapter in snapshot:
        scenes = chapter.get("scenes", [])
        if not isinstance(scenes, list):
            raise RuntimeError("Published chapter scenes are invalid.")
        active_scene_ids = {
            str(scene["id"])
            for scene in scenes
            if isinstance(scene, dict) and "id" in scene
        }
        for scene in scenes:
            if not isinstance(scene, dict):
                raise RuntimeError("Published chapter contains an invalid scene.")
            choices = scene.get("choices", [])
            if not isinstance(choices, list):
                raise RuntimeError("Published scene choices are invalid.")
            for choice in choices:
                if not isinstance(choice, dict):
                    raise RuntimeError("Published scene contains an invalid choice.")
                next_node_id = choice.get("next_node_id")
                if next_node_id is not None and str(next_node_id) not in active_scene_ids:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Uma escolha de capítulo publicado aponta para uma cena inativa "
                            "ou indisponível."
                        ),
                    )


def _next_story_scene(
    snapshot: list[dict[str, object]],
    current_chapter_id: str,
    current_scene: dict[str, object],
    selected_choice: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]] | None:
    next_node_id = selected_choice.get("next_node_id")
    if isinstance(next_node_id, str):
        destination = _scene_in_snapshot(snapshot, next_node_id)
        if destination is None or str(destination[0]["id"]) != current_chapter_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O destino desta escolha não está disponível na sessão.",
            )
        return destination

    chapter_index = next(
        (
            index
            for index, chapter in enumerate(snapshot)
            if str(chapter["id"]) == current_chapter_id
        ),
        None,
    )
    if chapter_index is None:
        raise RuntimeError("Current chapter is missing from the narrative snapshot.")
    chapter = snapshot[chapter_index]
    scenes = chapter.get("scenes", [])
    if isinstance(scenes, list):
        scene_index = next(
            (
                index
                for index, scene in enumerate(scenes)
                if isinstance(scene, dict) and scene.get("id") == current_scene["id"]
            ),
            None,
        )
        if scene_index is not None and scene_index + 1 < len(scenes):
            next_scene = scenes[scene_index + 1]
            if isinstance(next_scene, dict):
                return chapter, next_scene
    for next_chapter in snapshot[chapter_index + 1 :]:
        next_scenes = next_chapter.get("scenes", [])
        if isinstance(next_scenes, list) and next_scenes:
            next_scene = next_scenes[0]
            if isinstance(next_scene, dict):
                return next_chapter, next_scene
    return None


async def _close_vote_if_ready(
    db: AsyncSession,
    campaign: Campaign,
    game_session: GameSession,
    *,
    now: datetime,
    actor_user_id: UUID | None = None,
    deadline_elapsed: bool = False,
) -> bool:
    state = deepcopy(game_session.state or {})
    vote = state.get("vote")
    snapshot = state.get("content_snapshot")
    if (
        not isinstance(vote, dict)
        or vote.get("status") != "open"
        or not isinstance(snapshot, list)
    ):
        return False
    scene_id = str(state.get("current_node_id", ""))
    scene_location = _scene_in_snapshot(snapshot, scene_id)
    if scene_location is None:
        raise RuntimeError("Current scene is missing from the narrative snapshot.")
    chapter, scene = scene_location
    round_number = vote.get("round_number")
    if not isinstance(round_number, int):
        raise RuntimeError("Narrative vote round number is invalid.")

    votes = list(
        (
            await db.scalars(
                select(StoryVote).where(
                    StoryVote.session_id == game_session.id,
                    StoryVote.node_id == UUID(scene_id),
                    StoryVote.round_number == round_number,
                )
            )
        ).all()
    )
    eligible_ids = vote.get("eligible_user_ids", [])
    if not isinstance(eligible_ids, list):
        raise RuntimeError("Narrative vote eligibility is invalid.")
    eligible_set = {str(user_id) for user_id in eligible_ids}
    eligible_votes = [ballot for ballot in votes if str(ballot.user_id) in eligible_set]
    all_voted = eligible_set.issubset({str(item.user_id) for item in eligible_votes})
    deadline_at = vote.get("deadline_at")
    if deadline_at is not None and isinstance(deadline_at, str):
        deadline = datetime.fromisoformat(deadline_at)
        deadline_elapsed = deadline_elapsed or _aware(deadline) <= now
    if not all_voted and not deadline_elapsed:
        return False

    result, selected_choice = _resolve_vote_result(
        scene,
        eligible_votes,
        round_number,
        now,
        vote.get("tie_breaker"),
    )
    tally = result["tally"]
    vote["status"] = "resolved" if selected_choice is not None else result["status"]
    result["status"] = vote["status"]
    vote["result"] = result
    state["last_result"] = result

    if selected_choice is None:
        event_type = "vote_tied" if result["status"] == "tied" else "vote_closed_without_votes"
        await _append_game_event(
            db,
            game_session,
            event_type=event_type,
            payload={
                "chapter_id": str(chapter["id"]),
                "node_id": scene_id,
                "round_number": round_number,
                "result": result,
            },
            idempotency_key=f"vote-result:{game_session.id}:{scene_id}:{round_number}",
            actor_user_id=actor_user_id,
        )
        game_session.state = state
        return True

    choice_id = str(selected_choice["id"])
    decision_key = f"decision:{game_session.id}:{scene_id}:{round_number}"
    result["choice_id"] = choice_id
    result["choice_label"] = str(selected_choice["label"])
    result["consequences"] = deepcopy(selected_choice.get("consequences", {}))
    state["last_result"] = result
    applied = state.setdefault("applied_consequences", [])
    if not isinstance(applied, list):
        raise RuntimeError("Applied narrative consequences are invalid.")
    if not any(
        isinstance(entry, dict) and entry.get("decision_key") == decision_key
        for entry in applied
    ):
        applied.append(
            {
                "decision_key": decision_key,
                "chapter_id": str(chapter["id"]),
                "node_id": scene_id,
                "choice_id": choice_id,
                "consequences": deepcopy(selected_choice.get("consequences", {})),
                "applied_at": now.isoformat(),
            }
        )
    await _append_game_event(
        db,
        game_session,
        event_type="decision_resolved",
        payload={
            "chapter_id": str(chapter["id"]),
            "chapter_title": str(chapter["title"]),
            "node_id": scene_id,
            "scene_title": str(scene["title"]),
            "round_number": round_number,
            "choice_id": choice_id,
            "choice_label": str(selected_choice["label"]),
            "tally": tally,
            "tie_breaker": result.get("tie_breaker"),
            "consequences": deepcopy(selected_choice.get("consequences", {})),
        },
        idempotency_key=decision_key,
        actor_user_id=actor_user_id,
    )
    granted_rewards = await _apply_choice_rewards(
        db,
        campaign,
        game_session,
        choice=selected_choice,
        decision_key=decision_key,
        eligible_user_ids=[str(user_id) for user_id in eligible_ids],
        actor_user_id=actor_user_id,
    )
    if granted_rewards:
        result["rewards"] = granted_rewards
        state["last_result"] = result

    destination = _next_story_scene(
        snapshot,
        str(chapter["id"]),
        scene,
        selected_choice,
    )
    if destination is None:
        game_session.status = "completed"
        game_session.ended_at = now
        await _append_game_event(
            db,
            game_session,
            event_type="session_completed",
            payload={"chapter_id": str(chapter["id"]), "node_id": scene_id},
            idempotency_key=f"session-completed:{game_session.id}",
            actor_user_id=actor_user_id,
        )
    else:
        next_chapter, next_scene = destination
        next_node_id = str(next_scene["id"])
        state["current_chapter_id"] = str(next_chapter["id"])
        state["current_node_id"] = next_node_id
        game_session.current_node_id = UUID(next_node_id)
        next_vote = _open_vote(
            state,
            next_scene,
            [str(user_id) for user_id in eligible_ids],
            state["voting_settings"],
            now,
        )
        state["vote"] = next_vote
        campaign.current_chapter_id = UUID(str(next_chapter["id"]))
        campaign.current_node_id = UUID(next_node_id)
        if next_vote is None:
            game_session.status = "completed"
            game_session.ended_at = now
            await _append_game_event(
                db,
                game_session,
                event_type="session_completed",
                payload={
                    "chapter_id": str(next_chapter["id"]),
                    "node_id": next_node_id,
                },
                idempotency_key=f"session-completed:{game_session.id}",
                actor_user_id=actor_user_id,
            )

    game_session.state = state
    campaign.last_activity_at = now
    await db.flush()
    return True


async def _narrative_response(
    db: AsyncSession,
    campaign: Campaign,
    game_session: GameSession,
    user: User,
) -> NarrativeGameResponse:
    state = game_session.state or {}
    snapshot = state.get("content_snapshot")
    current_node_id = str(state.get("current_node_id", ""))
    if not isinstance(snapshot, list):
        raise RuntimeError("Narrative session is missing its content snapshot.")
    location = _scene_in_snapshot(snapshot, current_node_id)
    if location is None:
        raise RuntimeError("Narrative session is pointing to a missing scene.")
    chapter, scene = location
    raw_choices = scene.get("choices", [])
    if not isinstance(raw_choices, list):
        raise RuntimeError("Narrative scene choices are invalid.")
    choices = [choice for choice in raw_choices if isinstance(choice, dict)]

    raw_vote = state.get("vote")
    vote_response = None
    if isinstance(raw_vote, dict):
        round_number = raw_vote.get("round_number")
        if not isinstance(round_number, int):
            raise RuntimeError("Narrative vote round number is invalid.")
        ballots = list(
            (
                await db.scalars(
                    select(StoryVote).where(
                        StoryVote.session_id == game_session.id,
                        StoryVote.node_id == UUID(current_node_id),
                        StoryVote.round_number == round_number,
                    )
                )
            ).all()
        )
        eligible_user_ids = raw_vote.get("eligible_user_ids", [])
        if not isinstance(eligible_user_ids, list):
            raise RuntimeError("Narrative vote eligibility is invalid.")
        eligible_set = {str(user_id) for user_id in eligible_user_ids}
        current_ballots = [
            ballot for ballot in ballots if str(ballot.user_id) in eligible_set
        ]
        tally_counts = {str(choice["id"]): 0 for choice in choices}
        for ballot in current_ballots:
            choice_key = str(ballot.choice_id)
            if choice_key in tally_counts:
                tally_counts[choice_key] += 1
        vote_response = {
            "status": str(raw_vote.get("status", "open")),
            "round_number": round_number,
            "deadline_at": raw_vote.get("deadline_at"),
            "allow_vote_change": bool(raw_vote.get("allow_vote_change", False)),
            "eligible_count": len(eligible_set),
            "voted_count": len({str(ballot.user_id) for ballot in current_ballots}),
            "my_choice_id": next(
                (
                    ballot.choice_id
                    for ballot in current_ballots
                    if ballot.user_id == user.id
                ),
                None,
            ),
            "tally": [
                {
                    "choice_id": UUID(str(choice["id"])),
                    "label": str(choice["label"]),
                    "votes": tally_counts[str(choice["id"])],
                }
                for choice in choices
            ],
            "result": raw_vote.get("result"),
        }

    event_rows = list(
        (
            await db.scalars(
                select(GameEvent)
                .where(GameEvent.session_id == game_session.id)
                .order_by(GameEvent.sequence_number.desc())
            )
        ).all()
    )
    return NarrativeGameResponse(
        session_id=game_session.id,
        status=game_session.status,
        chapter={
            "id": UUID(str(chapter["id"])),
            "title": str(chapter["title"]),
            "summary": str(chapter["summary"]),
            "narrative": str(chapter["narrative"]),
        },
        scene={
            "id": UUID(str(scene["id"])),
            "title": str(scene["title"]),
            "narrative": str(scene["narrative"]),
            "choices": choices,
        },
        participants=await _member_responses(db, campaign.id),
        vote=vote_response,
        last_result=state.get("last_result"),
        history=[
            {
                "sequence_number": event.sequence_number,
                "actor_user_id": event.actor_user_id,
                "event_type": event.event_type,
                "payload": event.payload,
                "created_at": event.created_at,
            }
            for event in reversed(event_rows)
        ],
    )
