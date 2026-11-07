import asyncio
import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID
from weakref import WeakValueDictionary

from fastapi import HTTPException, status
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CampaignMember,
    Character,
    CharacterItem,
    CharacterRewardGrant,
    CharacterSkill,
    Item,
    CharacterQuest,
    Quest,
    Skill,
    WalletTransaction,
    WorldReward,
)
from app.schemas.progression import CharacterRewardSpec

BASE_XP_PER_LEVEL = 100
MAX_CHARACTER_LEVEL = 10_000
HP_PER_LEVEL = 5
MANA_PER_LEVEL = 2
ATTRIBUTE_POINTS_PER_LEVEL = 1
MAX_CHARACTER_VALUE = 2_000_000_000
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9:_-]{1,160}\Z")
_PROGRESSION_LOCKS: WeakValueDictionary[tuple[int, UUID], asyncio.Lock] = (
    WeakValueDictionary()
)


def _progression_lock(
    db: AsyncSession,
    character_id: UUID,
) -> tuple[tuple[int, UUID], asyncio.Lock]:
    key = (id(db.get_bind().pool), character_id)
    lock = _PROGRESSION_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _PROGRESSION_LOCKS[key] = lock
    return key, lock


def _release_progression_locks(sync_session, transaction) -> None:
    if transaction.parent is not None:
        return
    locks = sync_session.info.pop("progression_pending_locks", {})
    sync_session.info.pop("progression_lock_keys", None)
    for lock in locks.values():
        lock.release()


def _release_lock_after_transaction(
    db: AsyncSession,
    key: tuple[int, UUID],
    lock: asyncio.Lock,
) -> None:
    sync_session = db.sync_session
    sync_session.info.setdefault("progression_pending_locks", {})[key] = lock
    if not sync_session.info.get("progression_lock_listener"):
        event.listen(
            sync_session,
            "after_transaction_end",
            _release_progression_locks,
        )
        sync_session.info["progression_lock_listener"] = True


def xp_required_for_next_level(level: int) -> int | None:
    if level == MAX_CHARACTER_LEVEL:
        return None
    if level < 1 or level > MAX_CHARACTER_LEVEL:
        raise ValueError("O nível do personagem está fora dos limites permitidos.")
    return level * BASE_XP_PER_LEVEL


def xp_progress_percent(xp: int, level: int) -> int:
    requirement = xp_required_for_next_level(level)
    if requirement is None:
        return 100
    return min(100, (xp * 100) // requirement)


@dataclass(frozen=True)
class ProgressionResult:
    grant_id: UUID
    character_id: UUID
    xp_awarded: int
    xp_before: int
    xp_after: int
    level_before: int
    level_after: int
    gold_awarded: int
    attribute_points_awarded: int
    already_applied: bool


def _result_from_grant(
    grant: CharacterRewardGrant,
    *,
    already_applied: bool,
) -> ProgressionResult:
    return ProgressionResult(
        grant_id=grant.id,
        character_id=grant.character_id,
        xp_awarded=grant.xp_awarded,
        xp_before=grant.xp_before,
        xp_after=grant.xp_after,
        level_before=grant.level_before,
        level_after=grant.level_after,
        gold_awarded=grant.gold_awarded,
        attribute_points_awarded=(
            grant.attribute_points_after - grant.attribute_points_before
        ),
        already_applied=already_applied,
    )


async def apply_character_reward(
    db: AsyncSession,
    *,
    campaign_id: UUID,
    character_id: UUID,
    idempotency_key: str,
    reward: CharacterRewardSpec,
    source_id: UUID | None = None,
    source_name: str | None = None,
) -> ProgressionResult:
    if _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A chave de recompensa é inválida.",
        )

    key, lock = _progression_lock(db, character_id)
    held_keys = db.sync_session.info.setdefault("progression_lock_keys", set())
    if key in held_keys:
        return await _apply_character_reward_locked(
            db,
            campaign_id=campaign_id,
            character_id=character_id,
            idempotency_key=idempotency_key,
            reward=reward,
            source_id=source_id,
            source_name=source_name,
        )
    await lock.acquire()
    held_keys.add(key)
    try:
        result = await _apply_character_reward_locked(
            db,
            campaign_id=campaign_id,
            character_id=character_id,
            idempotency_key=idempotency_key,
            reward=reward,
            source_id=source_id,
            source_name=source_name,
        )
    except BaseException:
        if db.in_transaction():
            _release_lock_after_transaction(db, key, lock)
        else:
            held_keys.discard(key)
            lock.release()
        raise
    if db.in_transaction():
        _release_lock_after_transaction(db, key, lock)
    else:
        held_keys.discard(key)
        lock.release()
    return result


async def _apply_character_reward_locked(
    db: AsyncSession,
    *,
    campaign_id: UUID,
    character_id: UUID,
    idempotency_key: str,
    reward: CharacterRewardSpec,
    source_id: UUID | None = None,
    source_name: str | None = None,
) -> ProgressionResult:
    """Apply a server-authorized reward in the caller's current transaction.

    Callers must commit or roll back the transaction containing this operation.
    No player-facing route accepts reward amounts or idempotency keys.
    """
    if _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A chave de recompensa é inválida.",
        )

    character = await db.scalar(
        select(Character)
        .where(
            Character.id == character_id,
            Character.campaign_id == campaign_id,
        )
        .with_for_update()
    )
    if character is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personagem não encontrado nesta campanha.",
        )
    member_exists = await db.scalar(
        select(CampaignMember.id).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.character_id == character.id,
            CampaignMember.user_id == character.owner_id,
        )
    )
    if member_exists is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O personagem não está vinculado a um participante desta campanha.",
        )

    normalized_reward = reward.model_dump(mode="json")
    if source_id is not None:
        normalized_reward["source_id"] = str(source_id)
    if source_name is not None:
        normalized_reward["source_name"] = source_name
    existing = await db.scalar(
        select(CharacterRewardGrant).where(
            CharacterRewardGrant.character_id == character.id,
            CharacterRewardGrant.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.reward_payload != normalized_reward:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A chave desta recompensa já foi usada com outro conteúdo.",
            )
        return _result_from_grant(existing, already_applied=True)

    if character.xp + reward.xp > MAX_CHARACTER_VALUE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A experiência excede o limite permitido.",
        )
    if character.gold + reward.gold > MAX_CHARACTER_VALUE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="O ouro excede o limite permitido.",
        )

    requested_item_ids = [item.item_id for item in reward.items]
    items = list(
        (
            await db.scalars(
                select(Item)
                .where(Item.id.in_(requested_item_ids), Item.is_active.is_(True))
                .with_for_update()
            )
        ).all()
    ) if requested_item_ids else []
    items_by_id = {item.id: item for item in items}
    if set(items_by_id) != set(requested_item_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A recompensa contém um item indisponível.",
        )
    for item_reward in reward.items:
        item = items_by_id[item_reward.item_id]
        if not item.is_stackable and item_reward.quantity != 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="A quantidade excede o limite do item.",
            )
    existing_character_items = list(
        (
            await db.scalars(
                select(CharacterItem)
                .where(
                    CharacterItem.character_id == character.id,
                    CharacterItem.item_id.in_(requested_item_ids),
                )
                .with_for_update()
            )
        ).all()
    ) if requested_item_ids else []
    character_items_by_item_id = {
        character_item.item_id: character_item
        for character_item in existing_character_items
    }
    for item_reward in reward.items:
        existing_item = character_items_by_item_id.get(item_reward.item_id)
        if (
            existing_item is not None
            and existing_item.quantity + item_reward.quantity > MAX_CHARACTER_VALUE
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="A quantidade do item excede o limite permitido.",
            )

    requested_skill_ids = reward.skill_ids
    skills = list(
        (
            await db.scalars(
                select(Skill)
                .where(
                    Skill.id.in_(requested_skill_ids),
                    Skill.is_active.is_(True),
                    Skill.status.in_(("published", "publicado")),
                )
                .with_for_update()
            )
        ).all()
    ) if requested_skill_ids else []
    if {skill.id for skill in skills} != set(requested_skill_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A recompensa contém uma habilidade indisponível.",
        )
    learned_skill_ids = set(
        (
            await db.scalars(
                select(CharacterSkill.skill_id)
                .where(
                    CharacterSkill.character_id == character.id,
                    CharacterSkill.skill_id.in_(requested_skill_ids),
                )
                .with_for_update()
            )
        ).all()
    ) if requested_skill_ids else set()

    old = {
        "xp": character.xp,
        "level": character.level,
        "gold": character.gold,
        "hp": character.hp,
        "max_hp": character.max_hp,
        "mana": character.mana,
        "max_mana": character.max_mana,
        "attribute_points": character.attribute_points,
    }
    new_xp = old["xp"] + reward.xp
    new_level = old["level"]
    levels_gained = 0
    while new_level < MAX_CHARACTER_LEVEL:
        required = xp_required_for_next_level(new_level)
        if required is None or new_xp < required:
            break
        new_xp -= required
        new_level += 1
        levels_gained += 1

    max_hp_gain = levels_gained * HP_PER_LEVEL
    max_mana_gain = levels_gained * MANA_PER_LEVEL
    points_gain = levels_gained * ATTRIBUTE_POINTS_PER_LEVEL
    if (
        old["max_hp"] + max_hp_gain > MAX_CHARACTER_VALUE
        or old["max_mana"] + max_mana_gain > MAX_CHARACTER_VALUE
        or old["attribute_points"] + points_gain > MAX_CHARACTER_VALUE
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A evolução excede o limite de atributos permitido.",
        )

    grant = CharacterRewardGrant(
        character_id=character.id,
        campaign_id=campaign_id,
        idempotency_key=idempotency_key,
        source_type=reward.source_type,
        xp_awarded=reward.xp,
        xp_before=old["xp"],
        xp_after=character.xp,
        level_before=old["level"],
        level_after=character.level,
        gold_awarded=reward.gold,
        gold_before=old["gold"],
        gold_after=character.gold,
        hp_before=old["hp"],
        hp_after=character.hp,
        max_hp_before=old["max_hp"],
        max_hp_after=character.max_hp,
        mana_before=old["mana"],
        mana_after=character.mana,
        max_mana_before=old["max_mana"],
        max_mana_after=character.max_mana,
        attribute_points_before=old["attribute_points"],
        attribute_points_after=old["attribute_points"] + points_gain,
        reward_payload=normalized_reward,
    )
    grant.xp_after = new_xp
    grant.level_after = new_level
    grant.gold_after = old["gold"] + reward.gold
    grant.hp_after = min(old["max_hp"] + max_hp_gain, old["hp"] + max_hp_gain)
    grant.max_hp_after = old["max_hp"] + max_hp_gain
    grant.mana_after = min(old["max_mana"] + max_mana_gain, old["mana"] + max_mana_gain)
    grant.max_mana_after = old["max_mana"] + max_mana_gain

    try:
        async with db.begin_nested():
            db.add(grant)
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(
            select(CharacterRewardGrant).where(
                CharacterRewardGrant.character_id == character.id,
                CharacterRewardGrant.idempotency_key == idempotency_key,
            )
        )
        if existing is None:
            raise
        if existing.reward_payload != normalized_reward:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A chave desta recompensa já foi usada com outro conteúdo.",
            )
        return _result_from_grant(existing, already_applied=True)

    character.xp = new_xp
    character.level = new_level
    character.gold = old["gold"] + reward.gold
    character.max_hp = old["max_hp"] + max_hp_gain
    character.hp = grant.hp_after
    character.max_mana = old["max_mana"] + max_mana_gain
    character.mana = grant.mana_after
    character.attribute_points = old["attribute_points"] + points_gain

    for item_reward in reward.items:
        character_item = character_items_by_item_id.get(item_reward.item_id)
        if character_item is None:
            db.add(
                CharacterItem(
                    character_id=character.id,
                    item_id=item_reward.item_id,
                    quantity=item_reward.quantity,
                )
            )
        else:
            character_item.quantity += item_reward.quantity

    db.add_all(
        [
            CharacterSkill(character_id=character.id, skill_id=skill.id)
            for skill in skills
            if skill.id not in learned_skill_ids
        ]
    )

    if reward.gold:
        db.add(
            WalletTransaction(
                character_id=character.id,
                amount=reward.gold,
                transaction_type="reward",
                reason=f"Recompensa: {reward.source_type}",
                source_type=reward.source_type,
                source_id=grant.id,
            )
        )
        await db.flush()

    return _result_from_grant(grant, already_applied=False)


async def apply_world_reward(
    db: AsyncSession,
    *,
    campaign_id: UUID,
    character_id: UUID,
    idempotency_key: str,
    reward_id: UUID,
    source_type: Literal["world_reward", "narrative"] = "world_reward",
) -> ProgressionResult:
    reward = await db.scalar(
        select(WorldReward).where(WorldReward.id == reward_id).with_for_update()
    )
    if reward is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recompensa não encontrada.",
        )
    if not reward.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Esta recompensa não está ativa.",
        )
    try:
        item_ids = [UUID(item_id) for item_id in reward.item_ids]
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A definição desta recompensa contém um item inválido.",
        ) from error
    if len(item_ids) != len(set(item_ids)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A definição desta recompensa não pode repetir itens.",
        )
    if not (reward.xp or reward.gold or item_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A definição desta recompensa não contém benefícios.",
        )
    spec = CharacterRewardSpec(
        source_type=source_type,
        xp=reward.xp,
        gold=reward.gold,
        items=[{"item_id": item_id} for item_id in item_ids],
    )
    return await apply_character_reward(
        db,
        campaign_id=campaign_id,
        character_id=character_id,
        idempotency_key=idempotency_key,
        reward=spec,
        source_id=reward.id,
        source_name=reward.title,
    )


async def complete_character_quest(
    db: AsyncSession,
    *,
    campaign_id: UUID,
    character_id: UUID,
    quest_id: UUID,
    idempotency_key: str,
) -> ProgressionResult | None:
    quest = await db.scalar(
        select(Quest)
        .where(
            Quest.id == quest_id,
            Quest.campaign_id == campaign_id,
        )
        .with_for_update()
    )
    if quest is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A missão da consequência não existe nesta campanha.",
        )
    character_quest = await db.scalar(
        select(CharacterQuest)
        .where(
            CharacterQuest.character_id == character_id,
            CharacterQuest.quest_id == quest.id,
        )
        .with_for_update()
    )
    if character_quest is None:
        return None

    progress = dict(character_quest.progress or {})
    already_completed_by_this_event = (
        character_quest.status == "completed"
        and progress.get("completion_idempotency_key") == idempotency_key
    )
    if character_quest.status != "in_progress" and not already_completed_by_this_event:
        return None

    conditions = progress.get("conditions_snapshot", quest.conditions)
    if not isinstance(conditions, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="As condições de conclusão da missão estão inválidas.",
        )
    objectives = conditions.get("objectives", [])
    objective_progress = progress.get("objectives", {})
    if not isinstance(objectives, list) or not isinstance(objective_progress, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O progresso dos objetivos da missão está inválido.",
        )
    completed_objectives: list[bool] = []
    for objective in objectives:
        if (
            not isinstance(objective, dict)
            or not isinstance(objective.get("id"), str)
            or not isinstance(objective.get("title"), str)
            or not isinstance(objective.get("target"), int)
            or isinstance(objective.get("target"), bool)
            or objective["target"] < 1
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A definição de objetivos da missão está inválida.",
            )
        objective_value = objective_progress.get(objective["id"], 0)
        if (
            not isinstance(objective_value, int)
            or isinstance(objective_value, bool)
            or objective_value < 0
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O progresso numérico de um objetivo está inválido.",
            )
        completed_objectives.append(objective_value >= objective["target"])
    require_all = conditions.get("require_all_objectives", True)
    if not isinstance(require_all, bool):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A condição de conclusão da missão está inválida.",
        )
    objectives_satisfied = (
        all(completed_objectives) if require_all else any(completed_objectives)
    )
    if objectives and not objectives_satisfied:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Os objetivos necessários para concluir a missão ainda não foram cumpridos.",
        )

    raw_reward = progress.get("reward_snapshot", quest.rewards)
    if not isinstance(raw_reward, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A definição de recompensa da missão está inválida.",
        )
    try:
        reward = (
            CharacterRewardSpec(source_type="quest", **raw_reward)
            if raw_reward.get("xp", 0)
            or raw_reward.get("gold", 0)
            or raw_reward.get("items")
            or raw_reward.get("skill_ids")
            else None
        )
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A definição de recompensa da missão está inválida.",
        ) from error
    source_name = progress.get("title_snapshot", quest.title)
    if not isinstance(source_name, str):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A origem registrada da missão está inválida.",
        )

    result = (
        await apply_character_reward(
            db,
            campaign_id=campaign_id,
            character_id=character_id,
            idempotency_key=idempotency_key,
            reward=reward,
            source_id=quest.id,
            source_name=source_name,
        )
        if reward is not None
        else None
    )
    if not already_completed_by_this_event:
        progress["completion_idempotency_key"] = idempotency_key
        character_quest.progress = progress
        character_quest.status = "completed"
    return result
