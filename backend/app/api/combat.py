from __future__ import annotations

import hashlib
import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, BinaryIO, Iterator
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_player, require_same_origin
from app.db.session import get_db
from app.models import (
    AnimationConfiguration,
    Campaign,
    CampaignMember,
    Character,
    CharacterItem,
    CharacterSkill,
    CombatActionEvent,
    Combatant,
    DropRule,
    Encounter,
    Enemy,
    EntityContentAnimationBinding,
    EntityContentAssetBinding,
    EntityContentProfile,
    EntityContentSkillAssociation,
    Item,
    Skill,
    User,
)
from app.schemas.combat import CombatActionRequest, CombatStartRequest
from app.schemas.progression import CharacterRewardSpec, ItemReward
from app.services.asset_storage import LocalAssetStorage
from app.services.combat_rules import (
    MAX_COMBAT_VALUE,
    bounded_nonnegative_int,
    calculate_damage,
    normalize_combat_attributes,
    uses_magic_power,
)
from app.services.combat_balance import (
    balance_for_party_size,
    load_combat_balance_settings,
    scale_enemy_snapshot,
)
from app.services.combat_strategies import COMBAT_STRATEGIES, candidate_sort_key
from app.services.progression import apply_character_reward
from app.services.attribute_engine import resolve_character_attributes


router = APIRouter(prefix="/api/campaigns/{campaign_id}/combat", tags=["combat"])
storage = LocalAssetStorage()
_ACTIVE_ENCOUNTER_STATUSES = {"in_progress"}
_TERMINAL_ENCOUNTER_STATUSES = {"victory", "defeat"}
_MAX_ATTRIBUTE = MAX_COMBAT_VALUE


def _http_error(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _career_skill_origin_is_eligible(origin: Any) -> bool:
    return isinstance(origin, dict) and origin.get("mode") == "solo"


def _is_career_skill(skill: Skill) -> bool:
    requirements = skill.requirements if isinstance(skill.requirements, dict) else {}
    return skill.category.lower() == "carreira" or requirements.get("is_career") is True


def _is_combat_encounter(encounter: Encounter) -> bool:
    return (
        isinstance(encounter.configuration, dict)
        and encounter.configuration.get("combat_engine") == "h4"
    )


def _positive_number(value: object, default: int = 0) -> int:
    return bounded_nonnegative_int(value, default)


def _position(value: object, fallback: dict[str, float]) -> dict[str, float]:
    if not isinstance(value, dict):
        return fallback
    x = value.get("x")
    y = value.get("y")
    if (
        isinstance(x, (int, float))
        and not isinstance(x, bool)
        and isinstance(y, (int, float))
        and not isinstance(y, bool)
        and 0 <= x <= 1
        and 0 <= y <= 1
    ):
        return {"x": float(x), "y": float(y)}
    return fallback


def _distance(first: dict[str, Any], second: dict[str, Any]) -> float:
    first_position = _position(first.get("position"), {"x": 0.5, "y": 0.5})
    second_position = _position(second.get("position"), {"x": 0.5, "y": 0.5})
    return (
        (first_position["x"] - second_position["x"]) ** 2
        + (first_position["y"] - second_position["y"]) ** 2
    ) ** 0.5


def _action_visual(
    actor: Combatant,
    target: Combatant,
    skill: dict[str, Any] | None,
) -> dict[str, Any]:
    actor_snapshot = actor.snapshot if isinstance(actor.snapshot, dict) else {}
    target_snapshot = target.snapshot if isinstance(target.snapshot, dict) else {}
    actor_assets = actor_snapshot.get("assets", {})
    actor_assets = actor_assets if isinstance(actor_assets, dict) else {}
    actor_animations = actor_snapshot.get("animations", {})
    actor_animations = actor_animations if isinstance(actor_animations, dict) else {}
    skill_assets = skill.get("assets", {}) if skill else {}
    skill_assets = skill_assets if isinstance(skill_assets, dict) else {}
    actor_animation = actor_animations.get("attack")
    skill_animation = None
    if skill is not None:
        skill_animation = skill.get("animation") or skill.get("impact_animation")
    equipment = actor_snapshot.get("equipment", [])
    equipped_weapons = (
        [item for item in equipment if isinstance(item, dict)]
        if isinstance(equipment, list)
        else []
    )
    equipped_weapons.sort(
        key=lambda item: _positive_number(item.get("attack")),
        reverse=True,
    )
    weapon = next(
        (
            item
            for item in equipped_weapons
            if isinstance(item.get("assets"), dict)
            and (
                item["assets"].get("attack")
                or item["assets"].get("impact")
                or item.get("animation")
            )
        ),
        {},
    )
    weapon_assets = weapon.get("assets", {})
    weapon_assets = weapon_assets if isinstance(weapon_assets, dict) else {}
    weapon_animation = weapon.get("animation")
    weapon_animation_asset = (
        weapon_animation.get("asset_id")
        if isinstance(weapon_animation, dict)
        else None
    )
    actor_animation_asset = (
        weapon_assets.get("attack")
        or weapon_animation_asset
        or actor_assets.get("attack")
        or (
            actor_animation.get("asset_id")
            if isinstance(actor_animation, dict)
            else None
        )
    )
    separated_skill_gifs = skill is not None and skill.get("combat_visual_mode") == "separated"
    skill_execution_asset = skill_assets.get("attack") if separated_skill_gifs else None
    skill_projectile_asset = (
        skill_assets.get("impact") if separated_skill_gifs else skill_assets.get("attack")
    ) or (
            skill_animation.get("impact_asset_id")
            if isinstance(skill_animation, dict)
            else None
        )
    skill_projectile_asset = skill_projectile_asset or (
            skill_animation.get("asset_id")
            if isinstance(skill_animation, dict)
            else None
        )
    attack_asset = (
        skill_projectile_asset
        or weapon_assets.get("impact")
        or actor_assets.get("impact")
    )
    if skill_execution_asset:
        actor_animation_asset = skill_execution_asset
    if skill and skill.get("projectile_only") is True:
        actor_animation_asset = None
    delay = (
        skill.get("attack_release_delay_ms")
        if skill
        else actor_snapshot.get("attack_release_delay_ms", 500)
    )
    duration = (
        skill.get("travel_duration_ms", skill.get("attack_animation_duration_ms"))
        if skill
        else actor_snapshot.get("attack_animation_duration_ms", 700)
    )
    return {
        "actor_id": str(actor.id),
        "target_id": str(target.id),
        "actor_asset_id": actor_assets.get("sprite"),
        "target_asset_id": target_snapshot.get("assets", {}).get("sprite"),
        "actor_animation_asset_id": actor_animation_asset,
        "attack_asset_id": attack_asset,
        "projectile_only": bool(skill and skill.get("projectile_only") is True),
        "release_delay_ms": min(30000, _positive_number(delay, 500)),
        "animation_duration_ms": max(1, min(30000, _positive_number(duration, 700))),
        "has_attack_animation": bool(attack_asset),
        "attack_speed": (
            skill.get("attack_speed")
            if actor.enemy_id is not None and skill is not None
            else actor_snapshot.get("default_attack_speed", 1)
            if actor.enemy_id is not None
            else 1
        ),
    }


async def _profile(
    db: AsyncSession,
    *,
    entity_column: Any,
    entity_id: UUID,
) -> EntityContentProfile | None:
    return await db.scalar(
        select(EntityContentProfile).where(entity_column == entity_id)
    )


async def _visual_bindings(
    db: AsyncSession,
    profile_id: UUID | None,
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    if profile_id is None:
        return {}, {}
    assets = {
        row.role: str(row.asset_id)
        for row in (
            await db.scalars(
                select(EntityContentAssetBinding).where(
                    EntityContentAssetBinding.profile_id == profile_id
                )
            )
        ).all()
    }
    animations: dict[str, dict[str, Any]] = {}
    bindings = (
        await db.scalars(
            select(EntityContentAnimationBinding).where(
                EntityContentAnimationBinding.profile_id == profile_id
            )
        )
    ).all()
    for binding in bindings:
        animation = await db.get(AnimationConfiguration, binding.animation_id)
        if animation is None:
            continue
        configuration = (
            animation.configuration if isinstance(animation.configuration, dict) else {}
        )
        animations[binding.role] = {
            "id": str(animation.id),
            "name": animation.name,
            "asset_id": str(animation.asset_id),
            "impact_asset_id": (
                str(animation.impact_asset_id) if animation.impact_asset_id else None
            ),
            **configuration,
        }
    return assets, animations


async def _skill_snapshot(db: AsyncSession, skill: Skill) -> dict[str, Any]:
    profile = await _profile(
        db,
        entity_column=EntityContentProfile.skill_id,
        entity_id=skill.id,
    )
    settings = profile.settings if profile and isinstance(profile.settings, dict) else {}
    assets, animations = await _visual_bindings(db, profile.id if profile else None)
    effects = skill.effects if isinstance(skill.effects, dict) else {}
    additional = settings.get("additional_effects", {})
    reach = settings.get("reach", 1)
    if not isinstance(reach, (int, float)) or isinstance(reach, bool) or reach < 0:
        reach = 1
    return {
        "id": str(skill.id),
        "name": skill.name,
        "category": skill.category,
        "target": skill.target,
        "mana_cost": _positive_number(skill.mana_cost),
        "cooldown_seconds": _positive_number(skill.cooldown_seconds),
        "skill_type": str(settings.get("skill_type") or skill.category).lower(),
        "target_type": str(settings.get("target_type") or skill.target).lower(),
        "reach": min(float(reach), 1000),
        "is_active": skill.is_active,
        "status": skill.status,
        "damage_base": _positive_number(
            settings.get("damage_base")
            if settings.get("damage_base") is not None
            else effects.get("power", 0)
        ),
        "attack_release_delay_ms": min(
            30000, _positive_number(settings.get("attack_release_delay_ms"), 500)
        ),
        "attack_animation_duration_ms": max(
            1,
            min(30000, _positive_number(settings.get("attack_animation_duration_ms"), 700)),
        ),
        "travel_duration_ms": min(30000, _positive_number(settings.get("travel_duration_ms"), 700)),
        "projectile_only": settings.get("projectile_only") is True,
        "combat_visual_mode": settings.get("combat_visual_mode", "legacy"),
        "assets": assets,
        "effects": effects,
        "additional_effects": additional if isinstance(additional, dict) else {},
        "animation": animations.get("ability") or animations.get("attack"),
        "impact_animation": animations.get("impact"),
    }


async def _character_snapshot(db: AsyncSession, character: Character) -> dict[str, Any]:
    attributes = character.attributes if isinstance(character.attributes, dict) else {}
    combat_attributes = normalize_combat_attributes(attributes)
    equipment: list[dict[str, Any]] = []
    equipment_modifiers: list[dict[str, Any]] = []
    equipped = (
        await db.scalars(
            select(CharacterItem)
            .where(
                CharacterItem.character_id == character.id,
                CharacterItem.is_equipped.is_(True),
            )
            .order_by(CharacterItem.id)
        )
    ).all()
    for character_item in equipped:
        item = await db.get(Item, character_item.item_id)
        if item is None:
            continue
        item_attributes = item.attributes if isinstance(item.attributes, dict) else {}
        item_effects = item.effects if isinstance(item.effects, dict) else {}
        item_profile = await _profile(
            db,
            entity_column=EntityContentProfile.item_id,
            entity_id=item.id,
        )
        item_settings = (
            item_profile.settings
            if item_profile and isinstance(item_profile.settings, dict)
            else {}
        )
        item_attack = _positive_number(
            item_settings.get(
                "attack",
                item_attributes.get("attack", item_effects.get("attack", 0)),
            )
        )
        item_reach = item_settings.get("reach", 0)
        weapon_reach = (
            float(item_reach)
            if isinstance(item_reach, (int, float)) and not isinstance(item_reach, bool)
            else 0
        )
        item_defense = _positive_number(
            item_settings.get(
                "defense",
                item_attributes.get("defense", item_effects.get("defense", 0)),
            )
        )
        equipment_modifiers.append(
            {
                "id": str(item.id),
                "settings": item_settings,
                "attributes": item_attributes,
                "effects": item_effects,
            }
        )
        item_assets, item_animations = await _visual_bindings(
            db, item_profile.id if item_profile else None
        )
        equipment.append(
            {
                "id": str(item.id),
                "name": item.name,
                "attack": item_attack,
                "defense": item_defense,
                "reach": weapon_reach,
                "animation_display": item_settings.get("animation_display", "with_character"),
                "assets": item_assets,
                "animation": item_animations.get("weapon_attack"),
            }
        )

    resolved = resolve_character_attributes(
        character,
        equipment_modifiers,
    )
    final_attributes = resolved.final
    attack = min(_MAX_ATTRIBUTE, final_attributes.get("attack", combat_attributes["attack"]))
    defense = min(_MAX_ATTRIBUTE, final_attributes.get("defense", combat_attributes["defense"]))
    profile = await _profile(
        db,
        entity_column=EntityContentProfile.character_id,
        entity_id=character.id,
    )
    profile_settings = (
        profile.settings if profile and isinstance(profile.settings, dict) else {}
    )
    assets, animations = await _visual_bindings(db, profile.id if profile else None)
    learned_rows = (
        await db.execute(
            select(CharacterSkill, Skill)
            .join(Skill, Skill.id == CharacterSkill.skill_id)
            .where(
                CharacterSkill.character_id == character.id
            )
        )
    ).all()
    skills: dict[str, dict[str, Any]] = {}
    for character_skill, skill in learned_rows:
        if skill and skill.is_active and skill.status in {"published", "publicado"}:
            if _is_career_skill(skill):
                if not _career_skill_origin_is_eligible(character_skill.origin):
                    continue
            skills[str(skill.id)] = await _skill_snapshot(db, skill)
    return {
        "name": character.name,
        "max_hp": character.max_hp,
        "max_mana": character.max_mana,
        "attack": attack,
        "defense": defense,
        "magic_attack": combat_attributes["magic_attack"],
        "magic_defense": combat_attributes["magic_defense"],
        "speed": combat_attributes["speed"],
        "critical_chance": final_attributes.get("critical_chance", 5),
        "critical_damage": final_attributes.get("critical_damage", 150),
        "accuracy": final_attributes.get("accuracy", combat_attributes["speed"] + 50),
        "evasion": final_attributes.get("evasion", combat_attributes["speed"]),
        "position": _position(
            profile.default_position if profile else None,
            {"x": 0.2, "y": 0.5},
        ),
        "reach": max(
            [1.0, *(item["reach"] for item in equipment if item["reach"] > 0)]
        ),
        "resistances": [],
        "weaknesses": [],
        "assets": assets,
        "animations": animations,
        "attack_release_delay_ms": min(
            30000, _positive_number(profile_settings.get("attack_release_delay_ms"), 500)
        ),
        "attack_animation_duration_ms": max(
            1,
            min(30000, _positive_number(profile_settings.get("attack_animation_duration_ms"), 700)),
        ),
        "equipment": equipment,
        "skills": skills,
    }


async def _enemy_snapshot(db: AsyncSession, enemy: Enemy) -> dict[str, Any]:
    profile = await _profile(
        db,
        entity_column=EntityContentProfile.enemy_id,
        entity_id=enemy.id,
    )
    if profile is None or profile.availability != "available" or not enemy.is_active:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"O inimigo {enemy.name} não está disponível para batalhas.",
        )
    settings = profile.settings if isinstance(profile.settings, dict) else {}
    profile_attributes = profile.attributes if isinstance(profile.attributes, dict) else {}
    combat_attributes = normalize_combat_attributes(
        profile_attributes,
        defaults={
            "attack": _positive_number(enemy.attack),
            "magic_attack": _positive_number(enemy.attack),
            "defense": _positive_number(enemy.defense),
            "magic_defense": _positive_number(enemy.defense),
            "speed": _positive_number(enemy.speed),
        },
    )
    assets, animations = await _visual_bindings(db, profile.id)
    skill_associations = (
        await db.scalars(
            select(EntityContentSkillAssociation)
            .where(EntityContentSkillAssociation.profile_id == profile.id)
            .order_by(EntityContentSkillAssociation.position, EntityContentSkillAssociation.id)
        )
    ).all()
    skills: dict[str, dict[str, Any]] = {}
    for association in skill_associations:
        skill = await db.get(Skill, association.skill_id)
        if skill and skill.is_active and skill.status in {"published", "publicado"}:
            skill_data = await _skill_snapshot(db, skill)
            skill_data["attack_speed_override"] = association.attack_speed_override
            skill_data["attack_speed"] = (
                association.attack_speed_override
                if association.attack_speed_override is not None
                else settings.get("default_attack_speed", 1)
            )
            skills[str(skill.id)] = skill_data

    legacy_xp, legacy_gold = _legacy_enemy_currency_rewards(enemy.rewards)
    gold_reward = min(
        _MAX_ATTRIBUTE,
        _positive_number(settings.get("gold_reward", 0)) + legacy_gold,
    )
    item_rewards: list[dict[str, Any]] = []
    raw_special_rewards = settings.get("special_rewards", [])
    if isinstance(raw_special_rewards, list):
        for reward in raw_special_rewards:
            if not isinstance(reward, dict):
                continue
            item_ids = reward.get("item_ids", [])
            if isinstance(item_ids, list):
                item_rewards.extend(
                    {"item_id": str(item_id), "quantity": 1}
                    for item_id in item_ids
                    if isinstance(item_id, str)
                )
    reward_items = [*item_rewards, *_legacy_enemy_item_rewards(enemy.rewards)]
    drop_rules = await _enemy_drop_snapshot(db, enemy.id)
    referenced_item_ids: set[UUID] = set()
    try:
        referenced_item_ids.update(UUID(reward["item_id"]) for reward in reward_items)
        referenced_item_ids.update(UUID(drop["item_id"]) for drop in drop_rules)
    except (KeyError, ValueError) as error:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Uma recompensa do inimigo contém uma referência inválida.",
        ) from error
    available_items: dict[UUID, Item] = {}
    for drop in drop_rules:
        if int(drop["max_quantity"]) < int(drop["min_quantity"]):
            raise _http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Uma regra de drop do inimigo contém quantidades inválidas.",
            )
    if referenced_item_ids:
        available_items = {
            item.id: item
            for item in (
                await db.scalars(
                    select(Item).where(
                        Item.id.in_(referenced_item_ids),
                        Item.is_active.is_(True),
                    )
                )
            ).all()
        }
        if set(available_items) != referenced_item_ids:
            raise _http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Uma recompensa do inimigo referencia um item indisponível.",
            )
        if any(
            not available_items[UUID(reward["item_id"])].is_stackable
            and _positive_number(reward.get("quantity", 1), 1) != 1
            for reward in reward_items
        ) or any(
            not available_items[UUID(drop["item_id"])].is_stackable
            and int(drop["max_quantity"]) != 1
            for drop in drop_rules
        ):
            raise _http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Uma recompensa excede a quantidade permitida pelo item.",
            )
    skill_rewards = _legacy_enemy_skill_rewards(enemy.rewards)
    for raw_skill_id in skill_rewards:
        try:
            reward_skill = await db.get(Skill, UUID(raw_skill_id))
        except ValueError:
            reward_skill = None
        if (
            reward_skill is None
            or not reward_skill.is_active
            or reward_skill.status not in {"published", "publicado"}
        ):
            raise _http_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Uma recompensa do inimigo referencia uma habilidade indisponível.",
            )
    return {
        "name": enemy.name,
        "max_hp": enemy.hp,
        "max_mana": max(
            (skill["mana_cost"] for skill in skills.values()),
            default=0,
        ),
        "attack": combat_attributes["attack"],
        "defense": combat_attributes["defense"],
        "magic_attack": combat_attributes["magic_attack"],
        "magic_defense": combat_attributes["magic_defense"],
        "speed": combat_attributes["speed"],
        "position": _position(profile.default_position, {"x": 0.8, "y": 0.5}),
        "reach": 1.0,
        "default_attack_speed": settings.get("default_attack_speed", 1),
        "boss_difficulty": (
            settings.get("boss_difficulty", "common")
            if settings.get("category") == "boss"
            else "common"
            if settings.get("category") == "common"
            else None
        ),
        "_balance_category": settings.get("category", "common"),
        "max_attacks_per_turn": (
            2
            if settings.get("category") == "boss"
            and settings.get("max_attacks_per_turn") == 2
            else 1
        ),
        "can_interrupt_turns": (
            settings.get("category") == "boss"
            and settings.get("can_interrupt_turns") is True
        ),
        "strategy": settings.get("strategy", "baseline"),
        "attack_release_delay_ms": min(
            30000, _positive_number(settings.get("attack_release_delay_ms"), 500)
        ),
        "attack_animation_duration_ms": max(
            1,
            min(30000, _positive_number(settings.get("attack_animation_duration_ms"), 700)),
        ),
        "resistances": [
            str(value).lower() for value in enemy.resistances if isinstance(value, str)
        ],
        "weaknesses": [
            str(value).lower() for value in enemy.weaknesses if isinstance(value, str)
        ],
        "assets": assets,
        "animations": animations,
        "skills": skills,
        "reward": {
            "xp": min(_MAX_ATTRIBUTE, _positive_number(enemy.xp_reward) + legacy_xp),
            "gold": gold_reward,
            "items": reward_items,
            "skill_ids": skill_rewards,
            "drop_rules": drop_rules,
        },
    }


def _legacy_enemy_item_rewards(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rewards: list[dict[str, Any]] = []
    for reward in value:
        if not isinstance(reward, dict):
            continue
        item_id = reward.get("item_id")
        kind = str(reward.get("type", "item")).lower()
        if kind == "item" and isinstance(item_id, str):
            rewards.append(
                {
                    "item_id": item_id,
                    "quantity": _positive_number(
                        reward.get("quantity", reward.get("amount", 1)), 1
                    )
                    or 1,
                }
            )
    return rewards


def _legacy_enemy_skill_rewards(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        skill_id
        for reward in value
        if isinstance(reward, dict)
        and str(reward.get("type", "")).lower() == "skill"
        and isinstance((skill_id := reward.get("skill_id")), str)
    ]


def _legacy_enemy_currency_rewards(value: object) -> tuple[int, int]:
    if not isinstance(value, list):
        return 0, 0
    xp = 0
    gold = 0
    for reward in value:
        if not isinstance(reward, dict):
            continue
        reward_type = str(reward.get("type", "")).lower()
        amount = _positive_number(reward.get("amount", reward.get("value", 0)))
        if reward_type == "xp":
            xp = min(_MAX_ATTRIBUTE, xp + amount)
        elif reward_type in {"gold", "coin", "currency"}:
            gold = min(_MAX_ATTRIBUTE, gold + amount)
    return xp, gold


async def _enemy_drop_snapshot(db: AsyncSession, enemy_id: UUID) -> list[dict[str, Any]]:
    rules = (
        await db.scalars(
            select(DropRule)
            .where(DropRule.enemy_id == enemy_id)
            .order_by(DropRule.item_id, DropRule.id)
        )
    ).all()
    return [
        {
            "id": str(rule.id),
            "item_id": str(rule.item_id),
            "chance_basis_points": rule.chance_basis_points,
            "min_quantity": rule.min_quantity,
            "max_quantity": rule.max_quantity,
        }
        for rule in rules
    ]


async def _active_member(
    db: AsyncSession,
    campaign_id: UUID,
    user_id: UUID,
) -> CampaignMember:
    member = await db.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == user_id,
            CampaignMember.status == "active",
        )
    )
    if member is None:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Você não participa desta campanha.")
    return member


async def _require_campaign_access(
    db: AsyncSession,
    campaign_id: UUID,
    user: User,
) -> tuple[Campaign, CampaignMember]:
    campaign = await db.get(Campaign, campaign_id)
    if campaign is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, "Campanha não encontrada.")
    member = await _active_member(db, campaign_id, user.id)
    return campaign, member


async def _encounter_response(
    db: AsyncSession,
    encounter: Encounter,
    *,
    after_sequence: int = 0,
) -> dict[str, Any]:
    combatants = (
        await db.scalars(
            select(Combatant)
            .where(Combatant.encounter_id == encounter.id)
            .order_by(Combatant.initiative.desc(), Combatant.id)
        )
    ).all()
    events = (
        await db.scalars(
            select(CombatActionEvent)
            .where(
                CombatActionEvent.encounter_id == encounter.id,
                CombatActionEvent.sequence_number > after_sequence,
            )
            .order_by(CombatActionEvent.sequence_number)
        )
    ).all()
    configuration = encounter.configuration if isinstance(encounter.configuration, dict) else {}
    return {
        "id": str(encounter.id),
        "title": encounter.title,
        "status": encounter.status,
        "version": encounter.version,
        "active_combatant_id": configuration.get("active_combatant_id"),
        "pending_action": configuration.get("pending_action"),
        "round": configuration.get("round", 1),
        "result": configuration.get("result"),
        "reward_status": configuration.get("reward_status"),
        "combatants": [
            {
                "id": str(combatant.id),
                "character_id": str(combatant.character_id) if combatant.character_id else None,
                "enemy_id": str(combatant.enemy_id) if combatant.enemy_id else None,
                "name": (combatant.snapshot or {}).get("name", "Participante"),
                "current_hp": combatant.current_hp,
                "max_hp": (combatant.snapshot or {}).get("max_hp", combatant.current_hp),
                "current_mana": combatant.current_mana,
                "max_mana": (combatant.snapshot or {}).get("max_mana", combatant.current_mana),
                "initiative": combatant.initiative,
                "is_active": configuration.get("active_combatant_id") == str(combatant.id),
                "is_enemy": combatant.enemy_id is not None,
                "snapshot": combatant.snapshot or {},
                "conditions": combatant.conditions or {},
            }
            for combatant in combatants
        ],
        "events": [
            {
                "sequence": event.sequence_number,
                "type": event.event_type,
                "payload": event.payload,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
        "last_sequence": (
            events[-1].sequence_number
            if events
            else await db.scalar(
                select(func.max(CombatActionEvent.sequence_number)).where(
                    CombatActionEvent.encounter_id == encounter.id
                )
            )
            or 0
        ),
    }


async def _append_event(
    db: AsyncSession,
    encounter: Encounter,
    *,
    event_type: str,
    payload: dict[str, Any],
    idempotency_key: str,
    actor_user_id: UUID | None = None,
) -> CombatActionEvent:
    last_sequence = await db.scalar(
        select(func.max(CombatActionEvent.sequence_number)).where(
            CombatActionEvent.encounter_id == encounter.id
        )
    )
    event = CombatActionEvent(
        encounter_id=encounter.id,
        sequence_number=(last_sequence or 0) + 1,
        actor_user_id=actor_user_id,
        event_type=event_type,
        payload=payload,
        idempotency_key=idempotency_key[:120],
    )
    db.add(event)
    await db.flush()
    return event


def _alive(combatant: Combatant) -> bool:
    return combatant.current_hp > 0


def _terminal_status(combatants: list[Combatant]) -> str | None:
    if not any(item.enemy_id is not None and _alive(item) for item in combatants):
        return "victory"
    if not any(item.character_id is not None and _alive(item) for item in combatants):
        return "defeat"
    return None


async def _set_terminal(
    db: AsyncSession,
    encounter: Encounter,
    combatants: list[Combatant],
    outcome: str,
) -> None:
    encounter.status = outcome
    configuration = dict(encounter.configuration or {})
    configuration["result"] = outcome
    configuration["active_combatant_id"] = None
    encounter.configuration = configuration
    await _append_event(
        db,
        encounter,
        event_type="battle_finished",
        payload={"result": outcome},
        idempotency_key=f"battle-finished:{encounter.id}",
    )
    if outcome != "victory" or configuration.get("reward_status") == "applied":
        return

    characters = sorted(
        (item for item in combatants if item.character_id is not None),
        key=lambda item: str(item.character_id),
    )
    if not characters:
        return
    total_xp = 0
    total_gold = 0
    rewards: list[dict[str, Any]] = []
    skill_rewards: list[str] = []
    for combatant in combatants:
        if combatant.enemy_id is None:
            continue
        reward = (combatant.snapshot or {}).get("reward", {})
        if not isinstance(reward, dict):
            continue
        total_xp = min(_MAX_ATTRIBUTE, total_xp + _positive_number(reward.get("xp")))
        total_gold = min(_MAX_ATTRIBUTE, total_gold + _positive_number(reward.get("gold")))
        items = reward.get("items", [])
        if isinstance(items, list):
            rewards.extend(item for item in items if isinstance(item, dict))
        skills = reward.get("skill_ids", [])
        if isinstance(skills, list):
            skill_rewards.extend(
                skill_id for skill_id in skills if isinstance(skill_id, str)
            )
        drop_rules = reward.get("drop_rules", [])
        if isinstance(drop_rules, list):
            for drop in drop_rules:
                if not isinstance(drop, dict):
                    continue
                try:
                    drop_id = str(drop["id"])
                    drop_item_id = str(drop["item_id"])
                    chance = min(10000, max(0, int(drop["chance_basis_points"])))
                    minimum = max(1, int(drop["min_quantity"]))
                    maximum = max(minimum, int(drop["max_quantity"]))
                except (KeyError, TypeError, ValueError):
                    continue
                entropy = hashlib.sha256(
                    f"{encounter.id}:{combatant.id}:{drop_id}".encode("ascii")
                ).digest()
                if int.from_bytes(entropy[:4], "big") % 10000 < chance:
                    quantity = minimum + int.from_bytes(entropy[4:8], "big") % (
                        maximum - minimum + 1
                    )
                    rewards.append({"item_id": drop_item_id, "quantity": quantity})
    item_specs: list[ItemReward] = []
    for item in rewards:
        try:
            item_specs.append(
                ItemReward(
                    item_id=UUID(str(item["item_id"])),
                    quantity=_positive_number(item.get("quantity", 1), 1) or 1,
                )
            )
        except (KeyError, ValueError):
            continue
    item_totals: dict[UUID, int] = {}
    for item in item_specs:
        item_totals[item.item_id] = item_totals.get(item.item_id, 0) + item.quantity
    item_specs = [
        ItemReward(item_id=item_id, quantity=min(1_000_000, quantity))
        for item_id, quantity in sorted(item_totals.items(), key=lambda entry: str(entry[0]))
    ]
    valid_skill_ids: list[UUID] = []
    for skill_id in sorted(set(skill_rewards)):
        try:
            valid_skill_ids.append(UUID(skill_id))
        except ValueError:
            continue

    for index, character_combatant in enumerate(characters):
        assigned_items = [
            item
            for item_index, item in enumerate(item_specs)
            if item_index % len(characters) == index
        ]
        assigned_skills = valid_skill_ids if index == 0 else []
        character = await db.get(Character, character_combatant.character_id)
        if character is None:
            continue
        character_xp = total_xp // len(characters) + int(index < total_xp % len(characters))
        character_gold = total_gold // len(characters) + int(index < total_gold % len(characters))
        if not (character_xp or character_gold or assigned_items or assigned_skills):
            continue
        await apply_character_reward(
            db,
            campaign_id=encounter.campaign_id,
            character_id=character.id,
            idempotency_key=f"combat:{encounter.id}:{character.id}",
            reward=CharacterRewardSpec(
                source_type="combat",
                xp=character_xp,
                gold=character_gold,
                items=assigned_items,
                skill_ids=assigned_skills,
            ),
            source_id=encounter.id,
            source_name=encounter.title,
        )
    configuration["reward_status"] = "applied"
    encounter.configuration = configuration
    await _append_event(
        db,
        encounter,
        event_type="rewards_applied",
        payload={
            "xp": total_xp,
            "gold": total_gold,
            "characters": [str(item.character_id) for item in characters],
        },
        idempotency_key=f"rewards-applied:{encounter.id}",
    )


def _is_enemy(combatant: Combatant) -> bool:
    return combatant.enemy_id is not None


async def _sync_character_resources(db: AsyncSession, combatant: Combatant) -> None:
    if combatant.character_id is None:
        return
    character = await db.scalar(
        select(Character)
        .where(Character.id == combatant.character_id)
        .with_for_update()
    )
    if character is not None:
        character.hp = max(0, min(character.max_hp, combatant.current_hp))
        character.mana = max(0, min(character.max_mana, combatant.current_mana))


def _same_side(first: Combatant, second: Combatant) -> bool:
    return (first.character_id is not None) == (second.character_id is not None)


def _skill_effect_type(skill: dict[str, Any]) -> str:
    additional = skill.get("additional_effects", {})
    explicit = additional.get("effect_type") if isinstance(additional, dict) else None
    if isinstance(explicit, str):
        return explicit.lower()
    skill_type = str(skill.get("skill_type", "")).lower()
    if skill_type in {"cura", "curar", "healing", "heal"}:
        return "heal"
    return "damage"


def request_payload_matches(
    stored: dict[str, Any],
    request: CombatActionRequest,
) -> bool:
    if request.action == "end_turn":
        return (
            stored.get("action") == "end_turn"
            and request.target_id is None
            and request.skill_id is None
        )
    return (
        stored.get("action") == request.action
        and stored.get("target_id") == str(request.target_id)
        and stored.get("skill_id") == (str(request.skill_id) if request.skill_id else None)
    )


def _validate_player_action_selection(
    actor: Combatant,
    combatants: list[Combatant],
    request: CombatActionRequest,
) -> tuple[Combatant, dict[str, Any] | None]:
    by_id = {item.id: item for item in combatants}
    if request.target_id is None or request.target_id not in by_id:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Selecione um alvo válido.")
    target = by_id[request.target_id]
    skill: dict[str, Any] | None = None
    if request.action == "skill":
        if request.skill_id is None:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Selecione uma habilidade.")
        snapshot = actor.snapshot if isinstance(actor.snapshot, dict) else {}
        skills = snapshot.get("skills", {})
        skill = skills.get(str(request.skill_id)) if isinstance(skills, dict) else None
        if not isinstance(skill, dict):
            raise _http_error(status.HTTP_403_FORBIDDEN, "O personagem não conhece essa habilidade.")
        if actor.current_mana < _positive_number(skill.get("mana_cost")):
            raise _http_error(status.HTTP_409_CONFLICT, "Mana insuficiente.")
        conditions = actor.conditions if isinstance(actor.conditions, dict) else {}
        cooldowns = conditions.get("cooldowns", {})
        until = cooldowns.get(str(request.skill_id)) if isinstance(cooldowns, dict) else None
        if isinstance(until, str) and _cooldown_is_active(until, datetime.now(UTC)):
            raise _http_error(status.HTTP_409_CONFLICT, "A habilidade ainda está em recarga.")
    elif request.skill_id is not None:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "A ação está inválida.")
    effect_type = _skill_effect_type(skill) if skill is not None else "damage"
    target_type = str(skill.get("target_type", "single")).lower() if skill else "enemy"
    if skill and target_type not in {"single", "enemy", "ally", "friendly", "self"}:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Este tipo de alvo ainda não é suportado pelo combate.",
        )
    wants_same_side = effect_type == "heal" or target_type in {"ally", "friendly", "self"}
    if (
        not _alive(target)
        or (_same_side(actor, target) != wants_same_side)
        or (target_type == "self" and target.id != actor.id)
    ):
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "O alvo selecionado é inválido.")
    raw_reach = (actor.snapshot or {}).get("reach", 1)
    reach = (
        float(raw_reach)
        if isinstance(raw_reach, (int, float)) and not isinstance(raw_reach, bool)
        else 1
    )
    if skill is not None:
        skill_reach = skill.get("reach", 1)
        reach = float(skill_reach) if isinstance(skill_reach, (int, float)) else 1
    if _distance(actor.snapshot or {}, target.snapshot or {}) > reach:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "O alvo está fora de alcance.")
    return target, skill


async def _stage_action(
    db: AsyncSession,
    encounter: Encounter,
    actor: Combatant,
    target: Combatant,
    request: CombatActionRequest,
    *,
    skill: dict[str, Any] | None,
    actor_user_id: UUID | None,
    is_interrupt: bool = False,
    now_provider: Callable[[], datetime] | None = None,
) -> None:
    configuration = dict(encounter.configuration or {})
    if configuration.get("pending_action") is not None:
        raise _http_error(status.HTTP_409_CONFLICT, "Já existe uma ação em andamento.")
    visual = _action_visual(actor, target, skill)
    pending = {
        "action_id": str(request.action_id),
        "actor_id": str(actor.id),
        "target_id": str(target.id),
        "action": request.action,
        "skill_id": str(request.skill_id) if request.skill_id else None,
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "started_at": (now_provider() if now_provider else datetime.now(UTC)).isoformat(),
        "is_interrupt": is_interrupt,
        "visual": visual,
    }
    configuration["pending_action"] = pending
    if is_interrupt:
        configuration["active_combatant_id"] = str(actor.id)
        configuration["enemy_attacks_completed"] = 0
    encounter.configuration = configuration
    await _append_event(
        db,
        encounter,
        event_type="action_started",
        payload={
            **pending,
            "actor_name": (actor.snapshot or {}).get("name", "Participante"),
            "target_name": (target.snapshot or {}).get("name", "Alvo"),
        },
        idempotency_key=f"action-started:{request.action_id}",
        actor_user_id=actor_user_id,
    )


async def _resolve_player_action(
    db: AsyncSession,
    encounter: Encounter,
    combatants: list[Combatant],
    actor: Combatant,
    request: CombatActionRequest,
    user: User,
    *,
    enemy_strategy: str = "baseline",
    now_provider: Callable[[], datetime] | None = None,
    turn_limit: int | None = None,
    action_id_factory: Callable[[], UUID] | None = None,
) -> None:
    by_id = {item.id: item for item in combatants}
    configuration = dict(encounter.configuration or {})
    current_time = now_provider() if now_provider else datetime.now(UTC)
    if configuration.get("active_combatant_id") != str(actor.id):
        raise _http_error(status.HTTP_409_CONFLICT, "Não é o turno deste personagem.")
    if not _alive(actor):
        raise _http_error(status.HTTP_409_CONFLICT, "Este personagem foi derrotado.")

    if request.action == "end_turn":
        if request.target_id or request.skill_id:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "A ação está inválida.")
        await _append_event(
            db,
            encounter,
            event_type="turn_ended",
            payload={"action": "end_turn", "actor_id": str(actor.id)},
            idempotency_key=str(request.action_id),
            actor_user_id=user.id,
        )
        await _advance_turn(
            db, encounter, combatants, user.id,
            enemy_strategy=enemy_strategy,
            now_provider=now_provider,
            turn_limit=turn_limit,
            action_id_factory=action_id_factory,
        )
        return

    if request.target_id is None or request.target_id not in by_id:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Selecione um alvo válido.")
    target = by_id[request.target_id]

    skill: dict[str, Any] | None = None
    damage_type = "physical"
    base_damage = 0
    if request.action == "skill":
        if request.skill_id is None:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Selecione uma habilidade.")
        snapshot = actor.snapshot if isinstance(actor.snapshot, dict) else {}
        skills = snapshot.get("skills", {})
        skill = skills.get(str(request.skill_id)) if isinstance(skills, dict) else None
        if not isinstance(skill, dict):
            raise _http_error(status.HTTP_403_FORBIDDEN, "O personagem não conhece essa habilidade.")
        if actor.current_mana < _positive_number(skill.get("mana_cost")):
            raise _http_error(status.HTTP_409_CONFLICT, "Mana insuficiente.")
        conditions = dict(actor.conditions or {})
        cooldowns = dict(conditions.get("cooldowns", {}))
        until = cooldowns.get(str(request.skill_id))
        if isinstance(until, str):
            try:
                if datetime.fromisoformat(until) > current_time:
                    raise _http_error(status.HTTP_409_CONFLICT, "A habilidade ainda está em recarga.")
            except ValueError:
                cooldowns.pop(str(request.skill_id), None)
        actor.current_mana -= _positive_number(skill.get("mana_cost"))
        cooldown = _positive_number(skill.get("cooldown_seconds"))
        if cooldown:
            cooldowns[str(request.skill_id)] = (
                current_time + timedelta(seconds=cooldown)
            ).isoformat()
        conditions["cooldowns"] = cooldowns
        actor.conditions = conditions
        await _sync_character_resources(db, actor)
        damage_type = str(skill.get("skill_type", "magic")).lower()
        base_damage = _positive_number(skill.get("damage_base"))
        if request.skill_id is None:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Habilidade inválida.")
    elif request.skill_id is not None:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "A ação está inválida.")

    damage = 0
    healing = 0
    effect_type = _skill_effect_type(skill) if skill is not None else "damage"
    target_type = str(skill.get("target_type", "single")).lower() if skill else "enemy"
    if skill and target_type not in {"single", "enemy", "ally", "friendly", "self"}:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Este tipo de alvo ainda não é suportado pelo combate.",
        )
    wants_same_side = effect_type == "heal" or target_type in {"ally", "friendly", "self"}
    if (
        not _alive(target)
        or (_same_side(actor, target) != wants_same_side)
        or (target_type == "self" and target.id != actor.id)
    ):
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "O alvo selecionado é inválido.")
    raw_reach = (actor.snapshot or {}).get("reach", 1)
    reach = (
        float(raw_reach)
        if isinstance(raw_reach, (int, float)) and not isinstance(raw_reach, bool)
        else 1
    )
    if skill is not None:
        skill_reach = skill.get("reach", 1)
        reach = float(skill_reach) if isinstance(skill_reach, (int, float)) else 1
    if _distance(actor.snapshot or {}, target.snapshot or {}) > reach:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "O alvo está fora de alcance.")
    if skill is not None and effect_type == "heal":
        healing = min(
            base_damage,
            max(0, int((target.snapshot or {}).get("max_hp", target.current_hp)) - target.current_hp),
        )
        target.current_hp += healing
        await _sync_character_resources(db, target)
    else:
        actor_snapshot = actor.snapshot if isinstance(actor.snapshot, dict) else {}
        target_snapshot = target.snapshot if isinstance(target.snapshot, dict) else {}
        magic_attack = uses_magic_power(skill)
        damage = calculate_damage(
            attack_power=actor_snapshot.get("magic_attack" if magic_attack else "attack"),
            ability_power=base_damage,
            defense=target_snapshot.get("magic_defense" if magic_attack else "defense"),
            damage_type=damage_type,
            resistances=target_snapshot.get("resistances", []),
            weaknesses=target_snapshot.get("weaknesses", []),
        )
        target.current_hp = max(0, target.current_hp - damage)
        await _sync_character_resources(db, target)
        await _apply_limited_effect(db, encounter, actor, target, skill, user.id)

    await _append_event(
        db,
        encounter,
        event_type="action_resolved",
        payload={
            "action": request.action,
            "actor_id": str(actor.id),
            "target_id": str(target.id),
            "skill_id": str(request.skill_id) if request.skill_id else None,
            "damage": damage,
            "healing": healing,
            "target_hp": target.current_hp,
            "actor_mana": actor.current_mana,
            "visual": {
                **_action_visual(actor, target, skill),
                "damage": damage,
            },
        },
        idempotency_key=str(request.action_id),
        actor_user_id=user.id,
    )
    terminal = _terminal_status(combatants)
    if terminal:
        await _set_terminal(db, encounter, combatants, terminal)
        return
    if await _maybe_interrupt_with_boss(
        db, encounter, combatants, user.id, action_id_factory=action_id_factory
    ):
        return
    await _advance_turn(
        db, encounter, combatants, user.id,
        enemy_strategy=enemy_strategy,
        now_provider=now_provider,
        turn_limit=turn_limit,
        action_id_factory=action_id_factory,
    )


async def _maybe_interrupt_with_boss(
    db: AsyncSession,
    encounter: Encounter,
    combatants: list[Combatant],
    actor_user_id: UUID,
    *,
    action_id_factory: Callable[[], UUID] | None = None,
) -> bool:
    for enemy in combatants:
        snapshot = enemy.snapshot if isinstance(enemy.snapshot, dict) else {}
        if (
            enemy.enemy_id is None
            or not _alive(enemy)
            or snapshot.get("can_interrupt_turns") is not True
            or snapshot.get("boss_difficulty") not in {"difficult", "hard", "impossible"}
        ):
            continue
        configuration = dict(encounter.configuration or {})
        if configuration.get("pending_action") is not None:
            return True
        await _run_enemy_turn(
            db,
            encounter,
            enemy,
            combatants,
            strategy=str(snapshot.get("strategy", "baseline")),
            is_interrupt=True,
            action_id_factory=action_id_factory,
        )
        return (encounter.configuration or {}).get("pending_action") is not None
    return False


async def _apply_limited_effect(
    db: AsyncSession,
    encounter: Encounter,
    actor: Combatant,
    target: Combatant,
    skill: dict[str, Any] | None,
    user_id: UUID | None,
) -> None:
    if skill is None:
        return
    effect_type = _skill_effect_type(skill)
    additional = skill.get("additional_effects", {})
    if effect_type != "damage_over_time" or not isinstance(additional, dict):
        return
    damage_per_turn = _positive_number(additional.get("damage_per_turn"))
    duration = min(10, _positive_number(additional.get("duration")))
    if not damage_per_turn or not duration:
        return
    conditions = dict(target.conditions or {})
    effects = list(conditions.get("effects", []))
    effect_id = str(skill.get("id", ""))
    if any(isinstance(item, dict) and item.get("id") == effect_id for item in effects):
        return
    effects.append(
        {
            "id": effect_id,
            "type": "damage_over_time",
            "damage_per_turn": damage_per_turn,
            "damage_type": str(skill.get("skill_type", "magic")).lower(),
            "remaining_turns": duration,
        }
    )
    conditions["effects"] = effects
    target.conditions = conditions
    await _append_event(
        db,
        encounter,
        event_type="effect_applied",
        payload={
            "target_id": str(target.id),
            "skill_id": effect_id,
            "duration": duration,
        },
        idempotency_key=f"effect:{encounter.id}:{uuid4()}",
        actor_user_id=user_id,
    )


async def _advance_turn(
    db: AsyncSession,
    encounter: Encounter,
    combatants: list[Combatant],
    actor_user_id: UUID | None,
    *,
    enemy_strategy: str = "baseline",
    now_provider: Callable[[], datetime] | None = None,
    turn_limit: int | None = None,
    action_id_factory: Callable[[], UUID] | None = None,
) -> None:
    terminal = _terminal_status(combatants)
    if terminal:
        await _set_terminal(db, encounter, combatants, terminal)
        return
    configuration = dict(encounter.configuration or {})
    turn_order = configuration.get("turn_order", [])
    if not isinstance(turn_order, list) or not turn_order:
        raise _http_error(status.HTTP_409_CONFLICT, "A ordem de turnos está inválida.")
    index = int(configuration.get("turn_index", 0))
    round_number = int(configuration.get("round", 1))
    by_id = {str(item.id): item for item in combatants}
    for _ in range(len(turn_order) * 2):
        index += 1
        if index >= len(turn_order):
            index = 0
            round_number += 1
        candidate = by_id.get(str(turn_order[index]))
        if candidate is None or not _alive(candidate):
            continue
        simulation_turn_count = int(configuration.get("simulation_turn_count", 0))
        if turn_limit is not None and simulation_turn_count >= turn_limit:
            configuration = {
                **configuration,
                "result": "turn_limit",
                "active_combatant_id": None,
            }
            encounter.configuration = configuration
            encounter.status = "turn_limit"
            await _append_event(
                db,
                encounter,
                event_type="simulation_limit_reached",
                payload={"limit": turn_limit},
                idempotency_key=f"simulation-limit:{encounter.id}",
                actor_user_id=actor_user_id,
            )
            return
        configuration = {
            **configuration,
            "turn_index": index,
            "round": round_number,
            "active_combatant_id": str(candidate.id),
        }
        if _is_enemy(candidate):
            configuration["enemy_attacks_completed"] = 0
        if turn_limit is not None:
            configuration["simulation_turn_count"] = simulation_turn_count + 1
        encounter.configuration = configuration
        await _append_event(
            db,
            encounter,
            event_type="turn_started",
            payload={
                "combatant_id": str(candidate.id),
                "round": round_number,
            },
            idempotency_key=f"turn:{encounter.id}:{round_number}:{candidate.id}",
            actor_user_id=actor_user_id,
        )
        if not _is_enemy(candidate):
            await _tick_effects(db, encounter, candidate, combatants)
            terminal = _terminal_status(combatants)
            if terminal:
                await _set_terminal(db, encounter, combatants, terminal)
                return
            if not _alive(candidate):
                continue
            return
        await _run_enemy_turn(
            db,
            encounter,
            candidate,
            combatants,
            strategy=enemy_strategy,
            now_provider=now_provider,
            action_id_factory=action_id_factory,
        )
        if (encounter.configuration or {}).get("pending_action") is not None:
            return
        terminal = _terminal_status(combatants)
        if terminal:
            await _set_terminal(db, encounter, combatants, terminal)
            return
    raise _http_error(status.HTTP_409_CONFLICT, "Não foi possível determinar o próximo turno.")


async def _tick_effects(
    db: AsyncSession,
    encounter: Encounter,
    combatant: Combatant,
    combatants: list[Combatant],
) -> None:
    conditions = dict(combatant.conditions or {})
    effects = conditions.get("effects", [])
    if not isinstance(effects, list) or not effects:
        return
    updated: list[dict[str, Any]] = []
    for effect in effects:
        if not isinstance(effect, dict):
            continue
        effect_type = str(effect.get("type", ""))
        remaining = _positive_number(effect.get("remaining_turns")) - 1
        if effect_type == "damage_over_time":
            damage = _positive_number(effect.get("damage_per_turn"))
            damage_type = str(effect.get("damage_type", "magic")).lower()
            resistances = {
                str(value).lower() for value in (combatant.snapshot or {}).get("resistances", [])
            }
            weaknesses = {
                str(value).lower() for value in (combatant.snapshot or {}).get("weaknesses", [])
            }
            if damage_type in resistances:
                damage = max(1, damage // 2)
            elif damage_type in weaknesses:
                damage = min(_MAX_ATTRIBUTE, damage * 2)
            combatant.current_hp = max(0, combatant.current_hp - damage)
            await _append_event(
                db,
                encounter,
                event_type="effect_tick",
                payload={
                    "combatant_id": str(combatant.id),
                    "effect_type": effect_type,
                    "damage": damage,
                    "remaining_turns": max(0, remaining),
                    "current_hp": combatant.current_hp,
                },
                idempotency_key=f"effect-tick:{encounter.id}:{uuid4()}",
            )
        elif effect_type == "heal_over_time":
            healing = _positive_number(effect.get("healing_per_turn"))
            snapshot = combatant.snapshot if isinstance(combatant.snapshot, dict) else {}
            combatant.current_hp = min(
                _positive_number(snapshot.get("max_hp"), combatant.current_hp),
                combatant.current_hp + healing,
            )
            await _append_event(
                db,
                encounter,
                event_type="effect_tick",
                payload={
                    "combatant_id": str(combatant.id),
                    "effect_type": effect_type,
                    "healing": healing,
                    "remaining_turns": max(0, remaining),
                    "current_hp": combatant.current_hp,
                },
                idempotency_key=f"effect-tick:{encounter.id}:{uuid4()}",
            )
        elif effect_type in {"shield", "silence", "stun"} and remaining > 0:
            updated.append({**effect, "remaining_turns": remaining})
            continue
        if remaining > 0 and combatant.current_hp > 0 and effect_type in {"damage_over_time", "heal_over_time"}:
            updated.append({**effect, "remaining_turns": remaining})
    conditions["effects"] = updated
    combatant.conditions = conditions
    await _sync_character_resources(db, combatant)


async def _run_enemy_turn(
    db: AsyncSession,
    encounter: Encounter,
    actor: Combatant,
    combatants: list[Combatant],
    *,
    strategy: str = "baseline",
    now_provider: Callable[[], datetime] | None = None,
    tick_effects: bool = True,
    is_interrupt: bool = False,
    action_id_factory: Callable[[], UUID] | None = None,
) -> None:
    if tick_effects:
        await _tick_effects(db, encounter, actor, combatants)
    if not _alive(actor) or _terminal_status(combatants):
        return
    snapshot = actor.snapshot if isinstance(actor.snapshot, dict) else {}
    skills = snapshot.get("skills", {})
    conditions = dict(actor.conditions or {})
    cooldowns = conditions.get("cooldowns", {})
    current_time = now_provider() if now_provider else datetime.now(UTC)
    possible_targets = [
        item
        for item in combatants
        if item.character_id is not None and _alive(item)
    ]
    available = []
    if isinstance(skills, dict):
        available = [
            skill
            for skill in skills.values()
            if isinstance(skill, dict)
            and actor.current_mana >= _positive_number(skill.get("mana_cost"))
            and _skill_effect_type(skill) != "heal"
            and not (
                isinstance(cooldowns, dict)
                and isinstance(cooldowns.get(str(skill.get("id"))), str)
                and _cooldown_is_active(cooldowns[str(skill.get("id"))], current_time)
            )
        ]
    candidates: list[
        tuple[tuple[int, int, int, int, int, str, str], dict[str, Any] | None, Combatant]
    ] = []
    for candidate_skill in [None, *available]:
        if candidate_skill is None:
            reach_value = snapshot.get("reach", 1)
            ability_power = 0
            damage_type = "physical"
            mana_cost = 0
        else:
            reach_value = candidate_skill.get("reach", 1)
            ability_power = candidate_skill.get("damage_base", 0)
            damage_type = str(candidate_skill.get("skill_type", "magic")).lower()
            mana_cost = _positive_number(candidate_skill.get("mana_cost"))
        reach = (
            float(reach_value)
            if isinstance(reach_value, (int, float)) and not isinstance(reach_value, bool)
            else 1
        )
        magic_attack = uses_magic_power(candidate_skill)
        for target in possible_targets:
            if _distance(snapshot, target.snapshot or {}) > reach:
                continue
            target_snapshot = target.snapshot if isinstance(target.snapshot, dict) else {}
            damage = calculate_damage(
                attack_power=snapshot.get("magic_attack" if magic_attack else "attack"),
                ability_power=ability_power,
                defense=target_snapshot.get(
                    "magic_defense" if magic_attack else "defense"
                ),
                damage_type=damage_type,
                resistances=target_snapshot.get("resistances", []),
                weaknesses=target_snapshot.get("weaknesses", []),
            )
            applied_damage = min(damage, target.current_hp)
            kills_target = damage >= target.current_hp
            tie_breaker = str(candidate_skill.get("id", "")) if candidate_skill else ""
            normalized_type = damage_type.strip().casefold()
            resistances = {
                str(value).strip().casefold()
                for value in target_snapshot.get("resistances", [])
            }
            weaknesses = {
                str(value).strip().casefold()
                for value in target_snapshot.get("weaknesses", [])
            }
            configured_strategy = str(snapshot.get("strategy", strategy))
            actor_strategy = (
                configured_strategy if configured_strategy in COMBAT_STRATEGIES else strategy
            )
            score = candidate_sort_key(
                actor_strategy,
                kills_target=kills_target,
                effective_damage=applied_damage,
                mana_cost=mana_cost,
                raw_damage=damage,
                target_hp=target.current_hp,
                elemental_weakness=(
                    normalized_type in weaknesses and normalized_type not in resistances
                ),
                skill_id=tie_breaker,
                target_id=str(target.id),
                current_mana=actor.current_mana,
                max_mana=_positive_number(snapshot.get("max_mana")),
                target_threat=(
                    _positive_number(target_snapshot.get("attack"))
                    + _positive_number(target_snapshot.get("magic_attack"))
                    + _positive_number(target_snapshot.get("speed"))
                ),
                applies_new_effect=(
                    candidate_skill is not None
                    and _skill_effect_type(candidate_skill) == "damage_over_time"
                    and not any(
                        isinstance(effect, dict)
                        and effect.get("id") == str(candidate_skill.get("id", ""))
                        for effect in (
                            (target.conditions or {}).get("effects", [])
                            if isinstance((target.conditions or {}).get("effects", []), list)
                            else []
                        )
                    )
                ),
            )
            candidates.append((score, candidate_skill, target))
    if not candidates:
        await _append_event(
            db,
            encounter,
            event_type="turn_ended",
            payload={"actor_id": str(actor.id), "reason": "no_target_in_range"},
            idempotency_key=f"ai-no-target:{encounter.id}:{uuid4()}",
        )
        return
    difficulty = snapshot.get("boss_difficulty")
    if difficulty == "common":
        available_skill_ids = {str(item.get("id")) for item in available[:1]}
        simple_candidates = [
            item
            for item in candidates
            if item[1] is None or str(item[1].get("id")) in available_skill_ids
        ]
        _, skill, target = min(simple_candidates, key=lambda candidate: candidate[0])
    elif difficulty == "medium":
        _, skill, target = random.choice(candidates)
    else:
        _, skill, target = min(candidates, key=lambda candidate: candidate[0])
    skill_id = UUID(skill["id"]) if skill and isinstance(skill.get("id"), str) else None
    request = CombatActionRequest(
        action_id=action_id_factory() if action_id_factory else uuid4(),
        action="skill" if skill else "attack",
        target_id=target.id,
        skill_id=skill_id,
    )
    await _stage_action(
        db,
        encounter,
        actor,
        target,
        request,
        skill=skill,
        actor_user_id=None,
        is_interrupt=is_interrupt,
        now_provider=now_provider,
    )


async def _resolve_enemy_action(
    db: AsyncSession,
    encounter: Encounter,
    actor: Combatant,
    target: Combatant,
    request: CombatActionRequest,
    skill: dict[str, Any] | None,
) -> None:
    skill_cost = _positive_number(skill.get("mana_cost")) if skill else 0
    if skill:
        actor.current_mana -= skill_cost
        cooldown = _positive_number(skill.get("cooldown_seconds"))
        if cooldown:
            conditions = dict(actor.conditions or {})
            cooldowns = dict(conditions.get("cooldowns", {}))
            cooldowns[str(skill["id"])] = (
                datetime.now(UTC) + timedelta(seconds=cooldown)
            ).isoformat()
            conditions["cooldowns"] = cooldowns
            actor.conditions = conditions
    damage_type = str(skill.get("skill_type", "magic")).lower() if skill else "physical"
    base_damage = _positive_number(skill.get("damage_base")) if skill else 0
    actor_snapshot = actor.snapshot if isinstance(actor.snapshot, dict) else {}
    target_snapshot = target.snapshot if isinstance(target.snapshot, dict) else {}
    magic_attack = uses_magic_power(skill)
    damage = calculate_damage(
        attack_power=actor_snapshot.get("magic_attack" if magic_attack else "attack"),
        ability_power=base_damage,
        defense=target_snapshot.get("magic_defense" if magic_attack else "defense"),
        damage_type=damage_type,
        resistances=target_snapshot.get("resistances", []),
        weaknesses=target_snapshot.get("weaknesses", []),
    )
    target.current_hp = max(0, target.current_hp - damage)
    await _sync_character_resources(db, target)
    await _append_event(
        db,
        encounter,
        event_type="action_resolved",
        payload={
            "action": request.action,
            "actor_id": str(actor.id),
            "target_id": str(target.id),
            "skill_id": str(request.skill_id) if request.skill_id else None,
            "damage": damage,
            "healing": 0,
            "target_hp": target.current_hp,
            "actor_mana": actor.current_mana,
            "visual": {
                **_action_visual(actor, target, skill),
                "damage": damage,
                "attack_speed": (
                    skill.get("attack_speed")
                    if skill
                    else (actor.snapshot or {}).get("default_attack_speed", 1)
                ),
            },
        },
        idempotency_key=str(request.action_id),
    )
    await _apply_limited_effect(db, encounter, actor, target, skill, None)


def _cooldown_is_active(value: str, now: datetime) -> bool:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed > now


async def _load_encounter(
    db: AsyncSession,
    encounter_id: UUID,
    campaign_id: UUID,
) -> Encounter:
    encounter = await db.scalar(
        select(Encounter)
        .where(Encounter.id == encounter_id, Encounter.campaign_id == campaign_id)
        .with_for_update()
    )
    if encounter is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, "Batalha não encontrada.")
    if not _is_combat_encounter(encounter):
        raise _http_error(status.HTTP_404_NOT_FOUND, "Batalha não encontrada.")
    return encounter


@router.get("")
async def latest_battle(
    campaign_id: UUID,
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _require_campaign_access(db, campaign_id, user)
    encounters = (
        await db.scalars(
            select(Encounter)
            .where(Encounter.campaign_id == campaign_id)
            .order_by(Encounter.created_at.desc(), Encounter.id.desc())
        )
    ).all()
    encounter = next((item for item in encounters if _is_combat_encounter(item)), None)
    return {
        "encounter": (
            await _encounter_response(db, encounter) if encounter is not None else None
        )
    }


@router.get("/enemies")
async def available_battle_enemies(
    campaign_id: UUID,
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    await _require_campaign_access(db, campaign_id, user)
    enemies = (
        await db.scalars(
            select(Enemy)
            .join(
                EntityContentProfile,
                EntityContentProfile.enemy_id == Enemy.id,
            )
            .where(
                Enemy.is_active.is_(True),
                EntityContentProfile.availability == "available",
            )
            .order_by(Enemy.name, Enemy.id)
        )
    ).all()
    return [
        {"id": str(enemy.id), "name": enemy.name, "hp": enemy.hp}
        for enemy in enemies
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def start_battle(
    campaign_id: UUID,
    payload: CombatStartRequest,
    request: Request,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    campaign = await db.scalar(
        select(Campaign).where(Campaign.id == campaign_id).with_for_update()
    )
    if campaign is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, "Campanha não encontrada.")
    if campaign.owner_id != user.id:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Somente o proprietário pode iniciar batalhas.")
    if campaign.status != "in_progress":
        raise _http_error(status.HTTP_409_CONFLICT, "A campanha precisa estar em andamento.")
    await _active_member(db, campaign_id, user.id)
    active_encounters = (
        await db.scalars(
            select(Encounter).where(
                Encounter.campaign_id == campaign_id,
                Encounter.status.in_(_ACTIVE_ENCOUNTER_STATUSES),
            )
        )
    ).all()
    if any(_is_combat_encounter(item) for item in active_encounters):
        raise _http_error(status.HTTP_409_CONFLICT, "Já existe uma batalha em andamento.")
    members = (
        await db.scalars(
            select(CampaignMember)
            .where(
                CampaignMember.campaign_id == campaign_id,
                CampaignMember.status == "active",
            )
            .order_by(CampaignMember.user_id)
        )
    ).all()
    if any(member.character_id is None for member in members):
        raise _http_error(
            status.HTTP_409_CONFLICT,
            "Todos os participantes ativos precisam ter um personagem vinculado.",
        )
    character_combatants: list[Combatant] = []
    for member in members:
        character = await db.scalar(
            select(Character)
            .where(
                Character.id == member.character_id,
                Character.campaign_id == campaign_id,
                Character.status == "active",
            )
            .with_for_update()
        )
        if character is None or character.hp <= 0:
            raise _http_error(
                status.HTTP_409_CONFLICT,
                "Todos os personagens ativos precisam estar disponíveis e com HP.",
            )
        existing_encounters = (
            await db.scalars(
                select(Encounter).join(
                    Combatant,
                    Combatant.encounter_id == Encounter.id,
                )
                .where(
                    Combatant.character_id == character.id,
                    Encounter.campaign_id == campaign_id,
                    Encounter.status.in_(_ACTIVE_ENCOUNTER_STATUSES),
                )
            )
        ).all()
        if any(_is_combat_encounter(item) for item in existing_encounters):
            raise _http_error(status.HTTP_409_CONFLICT, "Um personagem já está em outra batalha.")
        snapshot = await _character_snapshot(db, character)
        character_combatants.append(
            Combatant(
                character_id=character.id,
                current_hp=character.hp,
                current_mana=character.mana,
                snapshot=snapshot,
                initiative=snapshot["speed"],
                conditions={},
            )
        )
    if not character_combatants:
        raise _http_error(status.HTTP_409_CONFLICT, "Não há personagens ativos para combater.")

    enemies = (
        await db.scalars(select(Enemy).where(Enemy.id.in_(payload.enemies)))
    ).all()
    enemy_by_id = {enemy.id: enemy for enemy in enemies}
    if set(enemy_by_id) != set(payload.enemies):
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Um inimigo selecionado não existe.")
    snapshots = {enemy.id: await _enemy_snapshot(db, enemy) for enemy in enemies}
    campaign_settings = campaign.settings if isinstance(campaign.settings, dict) else {}
    if campaign_settings.get("game_mode") == "solo":
        difficulty = campaign_settings.get("difficulty", "normal")
        enemy_multiplier = {"normal": 1.0, "hard": 1.25, "legendary": 1.5}.get(difficulty, 1.0)
        reward_multiplier = {"normal": 1.0, "hard": 1.1, "legendary": 1.25}.get(difficulty, 1.0)
        for enemy_id, snapshot in list(snapshots.items()):
            scaled = dict(snapshot)
            for attribute in ("max_hp", "attack", "magic_attack", "defense", "magic_defense", "speed"):
                if attribute in scaled:
                    scaled[attribute] = max(1, round(_positive_number(scaled[attribute]) * enemy_multiplier))
            reward = scaled.get("reward")
            if isinstance(reward, dict):
                scaled_reward = dict(reward)
                for currency in ("xp", "gold"):
                    if currency in scaled_reward:
                        scaled_reward[currency] = max(
                            0,
                            round(_positive_number(scaled_reward[currency]) * reward_multiplier),
                        )
                scaled["reward"] = scaled_reward
            snapshots[enemy_id] = scaled
    balance_settings = await load_combat_balance_settings(db)
    party_balance = balance_for_party_size(balance_settings, len(character_combatants))
    for enemy_id, snapshot in list(snapshots.items()):
        multipliers = (
            party_balance.bosses
            if snapshot.get("_balance_category") in {"boss", "miniboss"}
            else party_balance.enemies
        )
        snapshots[enemy_id] = scale_enemy_snapshot(snapshot, multipliers)
    title = "Batalha: " + " + ".join(
        enemy_by_id[enemy_id].name for enemy_id in payload.enemies
    )
    encounter = Encounter(
        campaign_id=campaign_id,
        chapter_id=campaign.current_chapter_id,
        title=title[:160],
        status="in_progress",
        configuration={
            "combat_engine": "h4",
            "round": 1,
            "turn_index": 0,
            "reward_status": "pending",
        },
        version=0,
    )
    db.add(encounter)
    await db.flush()
    for combatant in character_combatants:
        combatant.encounter_id = encounter.id
        db.add(combatant)
    occurrences: dict[UUID, int] = {}
    enemy_combatants: list[Combatant] = []
    for enemy_id in payload.enemies:
        enemy = enemy_by_id[enemy_id]
        snapshot = snapshots[enemy_id]
        index = occurrences.get(enemy_id, 0)
        occurrences[enemy_id] = index + 1
        enemy_combatant = Combatant(
            encounter_id=encounter.id,
            enemy_id=enemy.id,
            instance_index=index,
            current_hp=snapshot["max_hp"],
            current_mana=snapshot["max_mana"],
            snapshot=snapshot,
            initiative=snapshot["speed"],
            conditions={},
        )
        db.add(enemy_combatant)
        enemy_combatants.append(enemy_combatant)
    combatants = [*character_combatants, *enemy_combatants]
    await db.flush()
    combatants.sort(key=lambda item: (-item.initiative, str(item.id)))
    turn_order = [str(item.id) for item in combatants]
    encounter.configuration = {
        "combat_engine": "h4",
        "round": 1,
        "turn_index": 0,
        "turn_order": turn_order,
        "active_combatant_id": turn_order[0],
        "reward_status": "pending",
        "result": None,
    }
    await _append_event(
        db,
        encounter,
        event_type="battle_started",
        payload={
            "turn_order": turn_order,
            "combatant_ids": turn_order,
            "enemy_count": len(enemy_combatants),
        },
        idempotency_key=f"battle-started:{encounter.id}",
        actor_user_id=user.id,
    )
    await _append_event(
        db,
        encounter,
        event_type="turn_started",
        payload={"combatant_id": turn_order[0], "round": 1},
        idempotency_key=f"turn:{encounter.id}:1:{turn_order[0]}",
        actor_user_id=user.id,
    )
    if _is_enemy(combatants[0]):
        await _run_enemy_turn(db, encounter, combatants[0], combatants)
        terminal = _terminal_status(combatants)
        if terminal:
            await _set_terminal(db, encounter, combatants, terminal)
        elif (
            encounter.status == "in_progress"
            and (encounter.configuration or {}).get("pending_action") is None
        ):
            await _advance_turn(db, encounter, combatants, user.id)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise _http_error(status.HTTP_409_CONFLICT, "A batalha foi iniciada em outra solicitação.") from error
    return await _encounter_response(db, encounter)


@router.get("/{encounter_id}")
async def get_battle(
    campaign_id: UUID,
    encounter_id: UUID,
    after_sequence: int = 0,
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await _require_campaign_access(db, campaign_id, user)
    if after_sequence < 0:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "O cursor de eventos é inválido.")
    encounter = await db.scalar(
        select(Encounter).where(
            Encounter.id == encounter_id,
            Encounter.campaign_id == campaign_id,
        )
    )
    if encounter is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, "Batalha não encontrada.")
    if not _is_combat_encounter(encounter):
        raise _http_error(status.HTTP_404_NOT_FOUND, "Batalha não encontrada.")
    return await _encounter_response(db, encounter, after_sequence=after_sequence)


@router.post("/{encounter_id}/actions")
async def submit_action(
    campaign_id: UUID,
    encounter_id: UUID,
    payload: CombatActionRequest,
    request: Request,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    _, member = await _require_campaign_access(db, campaign_id, user)
    encounter = await _load_encounter(db, encounter_id, campaign_id)
    configuration = dict(encounter.configuration or {})
    pending = configuration.get("pending_action")
    duplicate = await db.scalar(
        select(CombatActionEvent).where(
            CombatActionEvent.encounter_id == encounter.id,
            CombatActionEvent.idempotency_key == str(payload.action_id),
        )
    )
    if duplicate is not None:
        if duplicate.actor_user_id != user.id:
            raise _http_error(status.HTTP_409_CONFLICT, "O identificador da ação já foi utilizado.")
        stored = duplicate.payload
        matches = request_payload_matches(stored, payload)
        if not matches:
            raise _http_error(status.HTTP_409_CONFLICT, "O identificador foi usado com outra ação.")
        return await _encounter_response(db, encounter)
    if isinstance(pending, dict):
        if (
            pending.get("action_id") == str(payload.action_id)
            and pending.get("actor_user_id") == str(user.id)
            and request_payload_matches(pending, payload)
        ):
            return await _encounter_response(db, encounter)
        raise _http_error(status.HTTP_409_CONFLICT, "Uma ação anterior ainda está em andamento.")
    if encounter.status != "in_progress":
        raise _http_error(status.HTTP_409_CONFLICT, "A batalha já foi encerrada.")

    combatants = (
        await db.scalars(
            select(Combatant)
            .where(Combatant.encounter_id == encounter.id)
            .with_for_update()
        )
    ).all()
    active_id = (encounter.configuration or {}).get("active_combatant_id")
    actor = next((item for item in combatants if str(item.id) == active_id), None)
    if actor is None:
        raise _http_error(status.HTTP_409_CONFLICT, "O participante ativo não foi encontrado.")
    if actor.character_id is None:
        raise _http_error(status.HTTP_409_CONFLICT, "O turno ativo pertence a um inimigo.")
    if actor.character_id != member.character_id:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Você não controla o participante ativo.")
    original_version = encounter.version
    if payload.action == "end_turn":
        await _resolve_player_action(db, encounter, combatants, actor, payload, user)
    else:
        target, skill = _validate_player_action_selection(actor, combatants, payload)
        await _stage_action(
            db,
            encounter,
            actor,
            target,
            payload,
            skill=skill,
            actor_user_id=user.id,
        )
    result = await db.execute(
        update(Encounter)
        .where(
            Encounter.id == encounter.id,
            Encounter.version == original_version,
        )
        .values(version=original_version + 1)
        .execution_options(synchronize_session=False)
    )
    try:
        if result.rowcount != 1:
            await db.rollback()
            raise _http_error(status.HTTP_409_CONFLICT, "A batalha mudou; atualize e tente novamente.")
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise _http_error(status.HTTP_409_CONFLICT, "A ação já foi processada.") from error
    except SQLAlchemyError:
        await db.rollback()
        raise
    encounter.version = original_version + 1
    return await _encounter_response(db, encounter)


@router.post("/{encounter_id}/actions/{action_id}/resolve")
async def resolve_action(
    campaign_id: UUID,
    encounter_id: UUID,
    action_id: UUID,
    request: Request,
    _: None = Depends(require_same_origin),
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    await _require_campaign_access(db, campaign_id, user)
    encounter = await _load_encounter(db, encounter_id, campaign_id)
    resolved = await db.scalar(
        select(CombatActionEvent).where(
            CombatActionEvent.encounter_id == encounter.id,
            CombatActionEvent.idempotency_key == str(action_id),
            CombatActionEvent.event_type == "action_resolved",
        )
    )
    if resolved is not None:
        if resolved.actor_user_id is not None and resolved.actor_user_id != user.id:
            raise _http_error(status.HTTP_403_FORBIDDEN, "Você não controla esta ação.")
        return await _encounter_response(db, encounter)
    configuration = dict(encounter.configuration or {})
    pending = configuration.get("pending_action")
    if not isinstance(pending, dict):
        raise _http_error(status.HTTP_409_CONFLICT, "Não há ação pendente para resolver.")
    if pending.get("action_id") != str(action_id):
        raise _http_error(status.HTTP_409_CONFLICT, "A ação pendente não corresponde ao identificador.")
    if pending.get("actor_user_id") not in {None, str(user.id)}:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Você não controla esta ação.")
    try:
        started_at = datetime.fromisoformat(str(pending["started_at"]))
    except (KeyError, ValueError) as error:
        raise _http_error(status.HTTP_409_CONFLICT, "O horário da ação pendente é inválido.") from error
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    visual = pending.get("visual", {})
    required_ms = (
        _positive_number(visual.get("release_delay_ms"))
        + _positive_number(visual.get("animation_duration_ms"))
        if isinstance(visual, dict)
        else 0
    )
    if datetime.now(UTC) < started_at + timedelta(milliseconds=required_ms):
        raise _http_error(
            status.HTTP_409_CONFLICT,
            "A animação configurada ainda não terminou.",
        )
    if encounter.status != "in_progress":
        raise _http_error(status.HTTP_409_CONFLICT, "A batalha já foi encerrada.")

    combatants = (
        await db.scalars(
            select(Combatant)
            .where(Combatant.encounter_id == encounter.id)
            .with_for_update()
        )
    ).all()
    by_id = {str(item.id): item for item in combatants}
    actor = by_id.get(str(pending.get("actor_id")))
    target = by_id.get(str(pending.get("target_id")))
    if actor is None or target is None:
        raise _http_error(status.HTTP_409_CONFLICT, "O ator ou alvo da ação não está disponível.")
    original_version = encounter.version
    configuration["pending_action"] = None
    encounter.configuration = configuration

    if actor.character_id is not None:
        member = await _active_member(db, campaign_id, user.id)
        if actor.character_id != member.character_id:
            raise _http_error(status.HTTP_403_FORBIDDEN, "Você não controla o participante ativo.")
        player_action = CombatActionRequest(
            action_id=action_id,
            action=str(pending.get("action")),
            target_id=target.id,
            skill_id=UUID(str(pending["skill_id"])) if pending.get("skill_id") else None,
        )
        await _resolve_player_action(db, encounter, combatants, actor, player_action, user)
    else:
        actor_snapshot = actor.snapshot if isinstance(actor.snapshot, dict) else {}
        skills = actor_snapshot.get("skills", {})
        raw_skill_id = pending.get("skill_id")
        skill = skills.get(str(raw_skill_id)) if isinstance(skills, dict) and raw_skill_id else None
        enemy_action = CombatActionRequest(
            action_id=action_id,
            action=str(pending.get("action")),
            target_id=target.id,
            skill_id=UUID(str(raw_skill_id)) if raw_skill_id else None,
        )
        await _resolve_enemy_action(db, encounter, actor, target, enemy_action, skill)
        if _terminal_status(combatants):
            await _set_terminal(db, encounter, combatants, _terminal_status(combatants) or "defeat")
        else:
            configuration = dict(encounter.configuration or {})
            attacks_completed = _positive_number(configuration.get("enemy_attacks_completed")) + 1
            configuration["enemy_attacks_completed"] = attacks_completed
            encounter.configuration = configuration
            max_attacks = min(
                2,
                max(1, _positive_number(actor_snapshot.get("max_attacks_per_turn"), 1)),
            )
            if attacks_completed < max_attacks and any(
                item.character_id is not None and _alive(item) for item in combatants
            ):
                await _run_enemy_turn(
                    db,
                    encounter,
                    actor,
                    combatants,
                    strategy=str(actor_snapshot.get("strategy", "baseline")),
                    tick_effects=False,
                    is_interrupt=bool(pending.get("is_interrupt")),
                )
            if (encounter.configuration or {}).get("pending_action") is None:
                await _advance_turn(db, encounter, combatants, user.id)

    result = await db.execute(
        update(Encounter)
        .where(
            Encounter.id == encounter.id,
            Encounter.version == original_version,
        )
        .values(version=original_version + 1)
        .execution_options(synchronize_session=False)
    )
    try:
        if result.rowcount != 1:
            await db.rollback()
            raise _http_error(status.HTTP_409_CONFLICT, "A batalha mudou; atualize e tente novamente.")
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise _http_error(status.HTTP_409_CONFLICT, "A ação já foi processada.") from error
    except SQLAlchemyError:
        await db.rollback()
        raise
    encounter.version = original_version + 1
    return await _encounter_response(db, encounter)


def _snapshot_asset_ids(value: Any, key: str = "") -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for child_key, child in value.items():
            if key == "assets" and isinstance(child, str):
                found.add(child)
            if child_key in {"asset_id", "actor_asset_id", "target_asset_id"} and isinstance(
                child, str
            ):
                found.add(child)
            elif child_key in {"assets", "visual"} or child_key.endswith("animation"):
                found.update(_snapshot_asset_ids(child, child_key))
            else:
                found.update(_snapshot_asset_ids(child, child_key))
    elif isinstance(value, list):
        for child in value:
            found.update(_snapshot_asset_ids(child, key))
    return found


@router.get("/assets/{asset_id}")
async def get_battle_asset(
    campaign_id: UUID,
    asset_id: UUID,
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    await _require_campaign_access(db, campaign_id, user)
    encounters = (
        await db.scalars(
            select(Encounter).where(Encounter.campaign_id == campaign_id)
        )
    ).all()
    encounters = [item for item in encounters if _is_combat_encounter(item)]
    combatant_rows = (
        await db.scalars(
            select(Combatant)
            .where(Combatant.encounter_id.in_([item.id for item in encounters]))
        )
    ).all() if encounters else []
    asset_id_text = str(asset_id)
    if not any(asset_id_text in _snapshot_asset_ids(item.snapshot or {}) for item in combatant_rows):
        raise _http_error(status.HTTP_404_NOT_FOUND, "Asset não encontrado.")
    from app.models import Asset

    asset = await db.get(Asset, asset_id)
    if asset is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, "Asset não encontrado.")
    try:
        asset_file: BinaryIO = await run_in_threadpool(storage.open, asset.storage_key)
    except (FileNotFoundError, OSError, ValueError):
        raise _http_error(status.HTTP_404_NOT_FOUND, "Arquivo do asset não encontrado.")

    def chunks() -> Iterator[bytes]:
        try:
            while True:
                chunk = asset_file.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            asset_file.close()

    return StreamingResponse(
        chunks(),
        media_type=asset.content_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
