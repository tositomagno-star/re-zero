from __future__ import annotations

import asyncio
import csv
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
import io
import json
import math
import statistics
from typing import Any, Callable, Iterable, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.combat import (
    _advance_turn,
    _append_event,
    _resolve_enemy_action,
    _resolve_player_action,
    _run_enemy_turn,
    _set_terminal,
    _terminal_status,
)
from app.db.base import Base
from app.models import Campaign, Character, CombatActionEvent, Combatant, Encounter, Enemy, User
from app.schemas.combat import CombatActionRequest
from app.services.combat_rules import calculate_damage, uses_magic_power
from app.services.combat_strategies import COMBAT_STRATEGIES, candidate_sort_key

SIMULATOR_VERSION = "1.0.0"
RULES_VERSION = "h4-authoritative+h7-combat-rules"
MAX_BATCH_SIZE = 10_000
MAX_TURNS = 10_000
MAX_BATCH_WORK_UNITS = 1_000_000
BATTLE_TIMEOUT_SECONDS = 30
Side = Literal["player", "enemy"]


@dataclass(frozen=True)
class SkillSpec:
    name: str
    category: str
    damage_base: int = 0
    mana_cost: int = 0
    skill_type: str = "physical"
    target_type: str = "enemy"
    cooldown_seconds: int = 0
    additional_effects: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CombatantSpec:
    name: str
    side: Side
    level: int
    hp: int
    mana: int
    attack: int
    magic_attack: int = 0
    defense: int = 0
    magic_defense: int = 0
    speed: int = 0
    skills: tuple[SkillSpec, ...] = ()
    resistances: tuple[str, ...] = ()
    weaknesses: tuple[str, ...] = ()
    is_boss: bool = False
    current_hp: int | None = None
    current_mana: int | None = None


@dataclass(frozen=True)
class BattleScenario:
    scenario_id: str
    name: str
    participants: tuple[CombatantSpec, ...]
    max_turns: int = 100


@dataclass
class _Candidate:
    action: Literal["attack", "skill"]
    target: Combatant
    skill: dict[str, Any] | None
    damage: int
    effective_damage: int
    healing: int
    healing_waste: int
    mana_cost: int
    elemental_weakness: bool


class _LogicalClock:
    def __init__(self) -> None:
        self._time = datetime(2026, 1, 1, tzinfo=UTC)

    def peek(self) -> datetime:
        return self._time

    def __call__(self) -> datetime:
        now = self._time
        self._time += timedelta(seconds=1)
        return now


def _stable_id(scenario_id: str, suffix: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"cronicas-do-reino-simulator:{scenario_id}:{suffix}")


def _skill_snapshot(spec: SkillSpec, entity_key: str, index: int) -> dict[str, Any]:
    skill_id = _stable_id(entity_key, f"skill:{index}:{spec.name}")
    return {
        "id": str(skill_id),
        "name": spec.name,
        "category": spec.category,
        "target": spec.target_type,
        "target_type": spec.target_type,
        "mana_cost": spec.mana_cost,
        "cooldown_seconds": spec.cooldown_seconds,
        "skill_type": spec.skill_type,
        "reach": 1,
        "damage_base": spec.damage_base,
        "additional_effects": dict(spec.additional_effects),
    }


def _validate_scenario(scenario: BattleScenario) -> None:
    if not scenario.scenario_id or len(scenario.scenario_id) > 80:
        raise ValueError("scenario_id must contain 1 to 80 characters.")
    if not scenario.name.strip():
        raise ValueError("Scenario name cannot be empty.")
    if not 1 <= scenario.max_turns <= MAX_TURNS:
        raise ValueError(f"max_turns must be between 1 and {MAX_TURNS}.")
    players = [item for item in scenario.participants if item.side == "player"]
    enemies = [item for item in scenario.participants if item.side == "enemy"]
    if not 1 <= len(players) <= 7 or not 1 <= len(enemies) <= 12:
        raise ValueError("A scenario requires 1-7 players and 1-12 enemies.")
    names: set[tuple[Side, str]] = set()
    for participant in scenario.participants:
        if participant.side not in {"player", "enemy"}:
            raise ValueError(f"Unsupported combatant side: {participant.side}.")
        if not participant.name.strip() or (participant.side, participant.name) in names:
            raise ValueError("Combatant names must be non-empty and unique per side.")
        names.add((participant.side, participant.name))
        if participant.level < 1 or participant.hp < 1 or participant.mana < 0:
            raise ValueError("Level and HP must be positive; mana cannot be negative.")
        if (
            participant.current_hp is not None
            and not 1 <= participant.current_hp <= participant.hp
        ):
            raise ValueError("current_hp must be between zero and maximum HP.")
        if (
            participant.current_mana is not None
            and not 0 <= participant.current_mana <= participant.mana
        ):
            raise ValueError("current_mana must be between zero and maximum mana.")
        values = (
            participant.attack,
            participant.magic_attack,
            participant.defense,
            participant.magic_defense,
            participant.speed,
        )
        if any(value < 0 or value > 2_000_000_000 for value in values):
            raise ValueError("Combat attributes must be between 0 and 2,000,000,000.")
        skill_names: set[str] = set()
        for skill in participant.skills:
            if skill.name in skill_names:
                raise ValueError("Skill names must be unique for each combatant.")
            skill_names.add(skill.name)
            if (
                skill.mana_cost < 0
                or skill.damage_base < 0
                or skill.cooldown_seconds < 0
                or skill.mana_cost > 2_000_000_000
                or skill.damage_base > 2_000_000_000
                or skill.cooldown_seconds > 2_000_000_000
                or skill.target_type
                not in {"single", "enemy", "ally", "friendly", "self"}
            ):
                raise ValueError(f"Invalid skill definition: {skill.name}.")


def scenario_to_dict(scenario: BattleScenario) -> dict[str, Any]:
    return asdict(scenario)


def scenario_from_dict(data: dict[str, Any]) -> BattleScenario:
    try:
        participants = tuple(
            CombatantSpec(
                **{
                    **raw,
                    "skills": tuple(SkillSpec(**skill) for skill in raw.get("skills", [])),
                    "resistances": tuple(raw.get("resistances", [])),
                    "weaknesses": tuple(raw.get("weaknesses", [])),
                }
            )
            for raw in data["participants"]
        )
        scenario = BattleScenario(
            scenario_id=str(data["scenario_id"]),
            name=str(data["name"]),
            participants=participants,
            max_turns=int(data.get("max_turns", 100)),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Invalid battle scenario document.") from error
    _validate_scenario(scenario)
    return scenario


def _build_candidates(
    actor: Combatant,
    combatants: list[Combatant],
    *,
    now: datetime,
) -> list[_Candidate]:
    from app.api.combat import (
        _cooldown_is_active,
        _distance,
        _positive_number,
        _skill_effect_type,
    )

    actor_snapshot = actor.snapshot if isinstance(actor.snapshot, dict) else {}
    is_player = actor.character_id is not None
    skills = actor_snapshot.get("skills", {})
    conditions = actor.conditions if isinstance(actor.conditions, dict) else {}
    cooldowns = conditions.get("cooldowns", {})
    candidates: list[_Candidate] = []
    for target in combatants:
        target_is_player = target.character_id is not None
        if target.current_hp <= 0 or target_is_player == is_player:
            continue
        if _distance(actor_snapshot, target.snapshot or {}) > float(actor_snapshot.get("reach", 1)):
            continue
        damage = calculate_damage(
            attack_power=actor_snapshot.get("attack", 0),
            ability_power=0,
            defense=(target.snapshot or {}).get("defense", 0),
            damage_type="physical",
            resistances=(target.snapshot or {}).get("resistances", []),
            weaknesses=(target.snapshot or {}).get("weaknesses", []),
        )
        candidates.append(
            _Candidate(
                action="attack",
                target=target,
                skill=None,
                damage=damage,
                effective_damage=min(damage, target.current_hp),
                healing=0,
                healing_waste=0,
                mana_cost=0,
                elemental_weakness=(
                    "physical"
                    in {
                        str(value).casefold()
                        for value in (target.snapshot or {}).get("weaknesses", [])
                    }
                ),
            )
        )
    if not isinstance(skills, dict):
        return candidates
    for skill in skills.values():
        if not isinstance(skill, dict):
            continue
        skill_id = str(skill.get("id", ""))
        cost = _positive_number(skill.get("mana_cost"))
        if actor.current_mana < cost or (
            isinstance(cooldowns, dict)
            and isinstance(cooldowns.get(skill_id), str)
            and _cooldown_is_active(cooldowns[skill_id], now)
        ):
            continue
        effect_type = _skill_effect_type(skill)
        if not is_player and effect_type == "heal":
            continue
        target_type = str(skill.get("target_type", "single")).lower()
        targets = [
            item
            for item in combatants
            if item.current_hp > 0
            and (
                (item.character_id is not None) == is_player
                if effect_type == "heal" or target_type in {"ally", "friendly", "self"}
                else (item.character_id is not None) != is_player
            )
            and (target_type != "self" or item.id == actor.id)
            and _distance(actor_snapshot, item.snapshot or {})
            <= float(skill.get("reach", 1))
        ]
        for target in targets:
            if effect_type == "heal":
                max_hp = int((target.snapshot or {}).get("max_hp", target.current_hp))
                effective_healing = min(
                    _positive_number(skill.get("damage_base")),
                    max(0, max_hp - target.current_hp),
                )
                candidates.append(
                    _Candidate(
                        action="skill",
                        target=target,
                        skill=skill,
                        damage=0,
                        effective_damage=0,
                        healing=effective_healing,
                        healing_waste=max(
                            0,
                            _positive_number(skill.get("damage_base")) - effective_healing,
                        ),
                        mana_cost=cost,
                        elemental_weakness=False,
                    )
                )
                continue
            magic = uses_magic_power(skill)
            damage_type = str(skill.get("skill_type", "magic")).casefold()
            target_snapshot = target.snapshot if isinstance(target.snapshot, dict) else {}
            damage = calculate_damage(
                attack_power=actor_snapshot.get("magic_attack" if magic else "attack", 0),
                ability_power=skill.get("damage_base", 0),
                defense=target_snapshot.get(
                    "magic_defense" if magic else "defense", 0
                ),
                damage_type=damage_type,
                resistances=target_snapshot.get("resistances", []),
                weaknesses=target_snapshot.get("weaknesses", []),
            )
            resistances = {
                str(value).casefold() for value in target_snapshot.get("resistances", [])
            }
            weaknesses = {
                str(value).casefold() for value in target_snapshot.get("weaknesses", [])
            }
            candidates.append(
                _Candidate(
                    action="skill",
                    target=target,
                    skill=skill,
                    damage=damage,
                    effective_damage=min(damage, target.current_hp),
                    healing=0,
                    healing_waste=0,
                    mana_cost=cost,
                    elemental_weakness=(
                        damage_type in weaknesses and damage_type not in resistances
                    ),
                )
            )
    return candidates


def _choose_party_candidate(
    candidates: list[_Candidate],
    strategy: str,
) -> _Candidate | None:
    if not candidates:
        return None

    def score(candidate: _Candidate) -> tuple[Any, ...]:
        target_hp = candidate.target.current_hp
        if strategy == "survival":
            max_hp = max(1, int((candidate.target.snapshot or {}).get("max_hp", target_hp)))
            critical_heal = candidate.healing > 0 and target_hp / max_hp <= 0.5
            if critical_heal:
                return (0, -candidate.healing, candidate.mana_cost, str(candidate.target.id))
            return (1, -candidate.effective_damage, candidate.mana_cost, str(candidate.target.id))
        if strategy not in COMBAT_STRATEGIES:
            raise ValueError(f"Unknown combat strategy: {strategy}")
        return candidate_sort_key(
            strategy,
            kills_target=candidate.damage >= target_hp and candidate.damage > 0,
            effective_damage=candidate.effective_damage,
            mana_cost=candidate.mana_cost,
            raw_damage=candidate.damage,
            target_hp=target_hp,
            elemental_weakness=candidate.elemental_weakness,
            skill_id=str((candidate.skill or {}).get("id", "")),
            target_id=str(candidate.target.id),
        )

    return min(candidates, key=score)


async def _prepare_battle(
    db: AsyncSession,
    scenario: BattleScenario,
) -> tuple[User, Encounter, list[Combatant]]:
    namespace = scenario.scenario_id
    user_id = _stable_id(namespace, "synthetic-user")
    campaign_id = _stable_id(namespace, "synthetic-campaign")
    user = User(
        id=user_id,
        username="Simulator",
        username_key="simulator",
        email=None,
        password_hash="not-a-login-credential",
        display_name="Synthetic Simulator",
        is_admin=False,
        status="active",
    )
    campaign = Campaign(
        id=campaign_id,
        owner_id=user_id,
        title=scenario.name[:160],
        status="in_progress",
        join_code=f"sim-{namespace[:24]}",
        settings={},
    )
    encounter = Encounter(
        id=_stable_id(namespace, "synthetic-encounter"),
        campaign_id=campaign_id,
        title=scenario.name[:160],
        status="in_progress",
        configuration={"combat_engine": "h4", "round": 1, "turn_index": 0},
        version=0,
    )
    db.add_all([user, campaign, encounter])
    await db.flush()

    combatants: list[Combatant] = []
    player_index = 0
    enemy_index = 0
    for index, spec in enumerate(scenario.participants):
        entity_key = f"{spec.side}:{index}:{spec.name}"
        skills = {
            str(skill["id"]): skill
            for skill in (
                _skill_snapshot(item, entity_key, skill_index)
                for skill_index, item in enumerate(spec.skills)
            )
        }
        snapshot = {
            "name": spec.name,
            "level": spec.level,
            "max_hp": spec.hp,
            "max_mana": spec.mana,
            "attack": spec.attack,
            "magic_attack": spec.magic_attack or spec.attack,
            "defense": spec.defense,
            "magic_defense": spec.magic_defense or spec.defense,
            "speed": spec.speed,
            "reach": 1,
            "position": {"x": 0.5, "y": 0.5},
            "resistances": list(spec.resistances),
            "weaknesses": list(spec.weaknesses),
            "skills": skills,
            "reward": {"xp": 0, "gold": 0, "items": [], "skill_ids": []},
        }
        if spec.side == "player":
            character_id = _stable_id(namespace, f"character:{player_index}:{spec.name}")
            snapshot["synthetic_entity_id"] = str(character_id)
            character = Character(
                id=character_id,
                owner_id=user_id,
                campaign_id=campaign_id,
                name=spec.name[:100],
                level=spec.level,
                hp=spec.current_hp if spec.current_hp is not None else spec.hp,
                max_hp=spec.hp,
                mana=spec.current_mana if spec.current_mana is not None else spec.mana,
                max_mana=spec.mana,
                attributes={
                    "attack": spec.attack,
                    "magic_attack": spec.magic_attack or spec.attack,
                    "defense": spec.defense,
                    "magic_defense": spec.magic_defense or spec.defense,
                    "speed": spec.speed,
                },
                status="active",
            )
            db.add(character)
            combatant = Combatant(
                id=_stable_id(namespace, f"combatant:player:{player_index}"),
                encounter_id=encounter.id,
                character_id=character_id,
                current_hp=spec.current_hp if spec.current_hp is not None else spec.hp,
                current_mana=spec.current_mana if spec.current_mana is not None else spec.mana,
                initiative=spec.speed,
                snapshot=snapshot,
                conditions={},
            )
            player_index += 1
        else:
            enemy_id = _stable_id(namespace, f"enemy:{enemy_index}:{spec.name}")
            snapshot["synthetic_entity_id"] = str(enemy_id)
            enemy = Enemy(
                id=enemy_id,
                name=spec.name[:120],
                level=spec.level,
                hp=spec.hp,
                attack=spec.attack,
                defense=spec.defense,
                speed=spec.speed,
                abilities=[],
                resistances=list(spec.resistances),
                weaknesses=list(spec.weaknesses),
                xp_reward=0,
                rewards=[],
                difficulty="boss" if spec.is_boss else "normal",
                appearance_chance=10000,
                is_active=True,
            )
            db.add(enemy)
            combatant = Combatant(
                id=_stable_id(namespace, f"combatant:enemy:{enemy_index}"),
                encounter_id=encounter.id,
                enemy_id=enemy_id,
                current_hp=spec.current_hp if spec.current_hp is not None else spec.hp,
                current_mana=spec.current_mana if spec.current_mana is not None else spec.mana,
                initiative=spec.speed,
                instance_index=enemy_index,
                snapshot=snapshot,
                conditions={},
            )
            enemy_index += 1
        db.add(combatant)
        combatants.append(combatant)
    await db.flush()
    combatants.sort(key=lambda item: (-item.initiative, str(item.id)))
    turn_order = [str(item.id) for item in combatants]
    encounter.configuration = {
        "combat_engine": "h4",
        "round": 1,
        "turn_index": 0,
        "turn_order": turn_order,
        "active_combatant_id": turn_order[0],
        "simulation_turn_count": 1,
        "reward_status": "pending",
        "result": None,
    }
    await _append_event(
        db,
        encounter,
        event_type="battle_started",
        payload={"turn_order": turn_order, "enemy_count": enemy_index},
        idempotency_key=f"sim-start:{encounter.id}",
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
    return user, encounter, combatants


def _metrics(
    scenario: BattleScenario,
    encounter: Encounter,
    combatants: list[Combatant],
    events: list[CombatActionEvent],
    *,
    seed: int,
    party_strategy: str,
    enemy_strategy: str,
    limited: bool,
    initial_hp: dict[str, int],
    initial_mana: dict[str, int],
) -> dict[str, Any]:
    current_hp = initial_hp.copy()
    damage_by_actor: dict[str, int] = {}
    effective_damage_by_actor: dict[str, int] = {}
    damage_received_raw: dict[str, int] = {}
    received_damage: dict[str, int] = {}
    skill_metrics: dict[str, dict[str, Any]] = {}
    healing_by_actor: dict[str, int] = {}
    wasted_healing_by_actor: dict[str, int] = {}
    action_count = 0
    damage_action_count = 0
    ineffective_damage_action_count = 0
    all_damage_effective = 0
    rounds = 1
    turns_started = 0
    first_defeat_round: int | None = None
    defeat_rounds: dict[str, int] = {}
    target_selections: dict[str, dict[str, int]] = {"player": {}, "enemy": {}}
    action_selections: dict[str, dict[str, int]] = {"player": {}, "enemy": {}}
    no_action_turns = 0
    round_number = 1
    character_ids = {str(item.id) for item in combatants if item.character_id is not None}
    skill_definitions = {
        str(skill_id): skill
        for combatant in combatants
        for skill_id, skill in (
            (combatant.snapshot or {}).get("skills", {}).items()
            if isinstance((combatant.snapshot or {}).get("skills", {}), dict)
            else ()
        )
    }
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        if event.event_type == "turn_started":
            turns_started += 1
            round_number = int(payload.get("round", round_number))
            rounds = max(rounds, round_number)
        elif event.event_type == "action_resolved":
            action_count += 1
            actor_id = str(payload.get("actor_id", ""))
            target_id = str(payload.get("target_id", ""))
            damage = int(payload.get("damage", 0))
            before_hp = current_hp.get(target_id, 0)
            effective = min(damage, before_hp)
            damage_by_actor[actor_id] = damage_by_actor.get(actor_id, 0) + damage
            effective_damage_by_actor[actor_id] = (
                effective_damage_by_actor.get(actor_id, 0) + effective
            )
            received_damage[target_id] = received_damage.get(target_id, 0) + effective
            damage_received_raw[target_id] = damage_received_raw.get(target_id, 0) + damage
            all_damage_effective += effective
            if damage > 0:
                damage_action_count += 1
                ineffective_damage_action_count += int(effective == 0)
            if "target_hp" in payload:
                current_hp[target_id] = int(payload["target_hp"])
                if before_hp > 0 and current_hp[target_id] <= 0:
                    defeat_rounds[target_id] = round_number
            healing = int(payload.get("healing", 0))
            healing_by_actor[actor_id] = healing_by_actor.get(actor_id, 0) + healing
            skill_id = payload.get("skill_id")
            actor = next(
                (item for item in combatants if str(item.id) == actor_id), None
            )
            target = next(
                (item for item in combatants if str(item.id) == target_id), None
            )
            if actor is not None and target is not None:
                actor_side = "player" if actor.character_id is not None else "enemy"
                target_name = str((target.snapshot or {}).get("name", target_id))
                target_selections[actor_side][target_name] = (
                    target_selections[actor_side].get(target_name, 0) + 1
                )
                action_type = "skill" if skill_id else "attack"
                action_selections[actor_side][action_type] = (
                    action_selections[actor_side].get(action_type, 0) + 1
                )
            if skill_id:
                skill = (
                    (actor.snapshot or {}).get("skills", {}).get(str(skill_id), {})
                    if actor is not None
                    else {}
                )
                skill_name = str(skill.get("name", skill_id))
                item = skill_metrics.setdefault(
                    skill_name,
                    {
                        "skill_id": str(skill_id),
                        "category": str(skill.get("category", "")),
                        "skill_type": str(skill.get("skill_type", "")),
                        "target_type": str(skill.get("target_type", "")),
                        "damage_base": int(skill.get("damage_base", 0)),
                        "mana_cost_per_use": int(skill.get("mana_cost", 0)),
                        "uses": 0,
                        "raw_damage": 0,
                        "effective_damage": 0,
                        "healing": 0,
                        "healing_wasted": 0,
                        "mana_cost": 0,
                        "usage_samples": [],
                        "target_ids": [],
                        "effect_application_count": 0,
                        "effect_target_ids": [],
                    },
                )
                item["uses"] += 1
                item["raw_damage"] += damage
                item["effective_damage"] += effective
                item["healing"] += healing
                item["mana_cost"] += int(skill.get("mana_cost", 0))
                item["usage_samples"].append(
                    {
                        "round": round_number,
                        "raw_damage": damage,
                        "effective_damage": effective,
                        "healing": healing,
                        "mana_cost": int(skill.get("mana_cost", 0)),
                    }
                )
                if target_id and target_id not in item["target_ids"]:
                    item["target_ids"].append(target_id)
                if healing:
                    wasted = max(0, int(skill.get("damage_base", 0)) - healing)
                    item["healing_wasted"] += wasted
                    wasted_healing_by_actor[actor_id] = (
                        wasted_healing_by_actor.get(actor_id, 0) + wasted
                    )
        elif event.event_type == "effect_applied":
            payload_skill_id = str(payload.get("skill_id", ""))
            skill = skill_definitions.get(payload_skill_id)
            if skill is not None:
                skill_name = str(skill.get("name", payload_skill_id))
                item = skill_metrics.setdefault(
                    skill_name,
                    {
                        "skill_id": payload_skill_id,
                        "category": str(skill.get("category", "")),
                        "skill_type": str(skill.get("skill_type", "")),
                        "target_type": str(skill.get("target_type", "")),
                        "damage_base": int(skill.get("damage_base", 0)),
                        "mana_cost_per_use": int(skill.get("mana_cost", 0)),
                        "uses": 0,
                        "raw_damage": 0,
                        "effective_damage": 0,
                        "healing": 0,
                        "healing_wasted": 0,
                        "mana_cost": 0,
                        "usage_samples": [],
                        "target_ids": [],
                        "effect_application_count": 0,
                        "effect_target_ids": [],
                    },
                )
                item["effect_application_count"] += 1
                target_id = str(payload.get("target_id", ""))
                if target_id and target_id not in item["effect_target_ids"]:
                    item["effect_target_ids"].append(target_id)
        elif event.event_type == "effect_tick":
            target_id = str(payload.get("combatant_id", ""))
            damage = int(payload.get("damage", 0))
            effective = min(damage, current_hp.get(target_id, 0))
            received_damage[target_id] = received_damage.get(target_id, 0) + effective
            damage_received_raw[target_id] = damage_received_raw.get(target_id, 0) + damage
            all_damage_effective += effective
            if "current_hp" in payload:
                current_hp[target_id] = int(payload["current_hp"])
                if effective > 0 and current_hp[target_id] <= 0:
                    defeat_rounds[target_id] = round_number
        elif event.event_type == "turn_ended":
            no_action_turns += int(
                payload.get("reason") == "no_target_in_range"
                or payload.get("action") == "end_turn"
            )
            if payload.get("action") == "end_turn":
                action_count += 1

        for entity_id, hp in current_hp.items():
            if hp <= 0 and entity_id in character_ids and first_defeat_round is None:
                first_defeat_round = round_number

    participants: list[dict[str, Any]] = []
    for combatant in combatants:
        entity_id = str(combatant.id)
        hp_start = initial_hp[entity_id]
        hp_end = combatant.current_hp
        mana_spent = max(0, initial_mana[entity_id] - combatant.current_mana)
        participants.append(
            {
                "combatant_id": entity_id,
                "entity_id": (combatant.snapshot or {}).get("synthetic_entity_id"),
                "name": (combatant.snapshot or {}).get("name", "Synthetic combatant"),
                "side": "player" if combatant.character_id is not None else "enemy",
                "level": (combatant.snapshot or {}).get("level", 1),
                "hp_initial": hp_start,
                "hp_final": hp_end,
                "mana_initial": initial_mana[entity_id],
                "mana_consumed": mana_spent,
                "mana_remaining": combatant.current_mana,
                "damage_raw": damage_by_actor.get(entity_id, 0),
                "damage_effective": effective_damage_by_actor.get(entity_id, 0),
                "damage_received_effective": received_damage.get(entity_id, 0),
                "damage_received_raw": damage_received_raw.get(entity_id, 0),
                "healing_effective": healing_by_actor.get(entity_id, 0),
                "healing_wasted": wasted_healing_by_actor.get(entity_id, 0),
                "survived": hp_end > 0,
                "rounds_until_defeat": defeat_rounds.get(entity_id),
            }
        )

    outcome = encounter.status if encounter.status in {"victory", "defeat"} else "turn_limit" if limited else "draw"
    party = [item for item in participants if item["side"] == "player"]
    enemy_side = [item for item in participants if item["side"] == "enemy"]
    for metric in skill_metrics.values():
        uses = metric["uses"]
        mana_cost = metric["mana_cost"]
        metric["unique_target_count"] = len(metric.pop("target_ids"))
        metric["unique_effect_target_count"] = len(metric.pop("effect_target_ids"))
        metric["damage_per_use"] = metric["effective_damage"] / uses if uses else 0
        metric["damage_per_mana"] = (
            metric["effective_damage"] / mana_cost if mana_cost else None
        )
        metric["healing_per_mana"] = metric["healing"] / mana_cost if mana_cost else None
    logical_rounds = rounds
    total_effective_damage = all_damage_effective
    total_received_effective = sum(item["damage_received_effective"] for item in participants)
    total_healing_effective = sum(item["healing_effective"] for item in participants)
    total_healing_wasted = sum(item["healing_wasted"] for item in participants)
    total_mana_consumed = sum(item["mana_consumed"] for item in participants)
    total_raw_damage = sum(
        int((event.payload or {}).get("damage", 0))
        for event in events
        if event.event_type in {"action_resolved", "effect_tick"}
    )
    target_focus_share = {}
    for side, selections in target_selections.items():
        total_selections = sum(selections.values())
        target_focus_share[side] = (
            max(selections.values()) / total_selections if total_selections else None
        )
    return {
        "scenario_id": scenario.scenario_id,
        "scenario": scenario_to_dict(scenario),
        "seed": seed,
        "simulator_version": SIMULATOR_VERSION,
        "rules_version": RULES_VERSION,
        "party_strategy": party_strategy,
        "enemy_strategy": enemy_strategy,
        "result": outcome,
        "turns": turns_started,
        "logical_duration_rounds": logical_rounds,
        "actions_executed": action_count,
        "participants": participants,
        "damage_actions": damage_action_count,
        "ineffective_damage_actions": ineffective_damage_action_count,
        "total_damage_raw": total_raw_damage,
        "total_damage_overkill": max(0, total_raw_damage - all_damage_effective),
        "total_damage_effective": total_effective_damage,
        "average_effective_damage_per_action": (
            total_effective_damage / action_count if action_count else 0
        ),
        "total_damage_received_raw": sum(damage_received_raw.values()),
        "total_damage_received_effective": total_received_effective,
        "total_healing_effective": total_healing_effective,
        "total_healing_wasted": total_healing_wasted,
        "total_mana_consumed": total_mana_consumed,
        "mana_consumed_per_action": (
            total_mana_consumed / action_count if action_count else 0
        ),
        "damage_per_mana": (
            total_effective_damage / total_mana_consumed
            if total_mana_consumed
            else None
        ),
        "healing_per_mana": (
            total_healing_effective / total_mana_consumed
            if total_mana_consumed
            else None
        ),
        "first_player_defeat_round": first_defeat_round,
        "players_surviving": sum(item["survived"] for item in party),
        "enemies_surviving": sum(item["survived"] for item in enemy_side),
        "players_defeated": sum(not item["survived"] for item in party),
        "enemies_defeated": sum(not item["survived"] for item in enemy_side),
        "target_selections": target_selections,
        "target_focus_share": target_focus_share,
        "action_selections": action_selections,
        "no_action_turns": no_action_turns,
        "invalid_action_count": None,
        "skills": skill_metrics,
        "events": [
            {
                "sequence": event.sequence_number,
                "type": event.event_type,
                "payload": event.payload,
            }
            for event in events
        ],
    }


async def _simulate_in_session(
    session_factory: async_sessionmaker[AsyncSession],
    scenario: BattleScenario,
    *,
    seed: int,
    party_strategy: str,
    enemy_strategy: str,
) -> dict[str, Any]:
    if party_strategy not in (*COMBAT_STRATEGIES, "survival"):
        raise ValueError(f"Unknown party strategy: {party_strategy}")
    if enemy_strategy not in COMBAT_STRATEGIES:
        raise ValueError(f"Unknown enemy strategy: {enemy_strategy}")
    _validate_scenario(scenario)
    clock = _LogicalClock()
    async with session_factory() as session:
        try:
            user, encounter, combatants = await _prepare_battle(session, scenario)
            initial_hp = {str(item.id): item.current_hp for item in combatants}
            initial_mana = {str(item.id): item.current_mana for item in combatants}
            action_index = 0

            def next_action_id() -> UUID:
                nonlocal action_index
                action_index += 1
                return _stable_id(
                    scenario.scenario_id, f"action:{seed}:{action_index}"
                )

            while encounter.status == "in_progress":
                configuration = encounter.configuration or {}
                active_id = str(configuration.get("active_combatant_id"))
                actor = next((item for item in combatants if str(item.id) == active_id), None)
                if actor is None:
                    raise RuntimeError("The simulation turn references an unknown combatant.")
                if actor.enemy_id is not None:
                    if (encounter.configuration or {}).get("pending_action") is None:
                        await _run_enemy_turn(
                            session,
                            encounter,
                            actor,
                            combatants,
                            strategy=enemy_strategy,
                            now_provider=clock,
                            action_id_factory=next_action_id,
                        )
                    await _resolve_simulated_enemy_actions(
                        session,
                        encounter,
                        combatants,
                        enemy_strategy=enemy_strategy,
                        now_provider=clock,
                        action_id_factory=next_action_id,
                    )
                    terminal = _terminal_status(combatants)
                    if terminal:
                        await _set_terminal(session, encounter, combatants, terminal)
                    else:
                        await _advance_turn(
                            session,
                            encounter,
                            combatants,
                            user.id,
                            enemy_strategy=enemy_strategy,
                            now_provider=clock,
                            turn_limit=scenario.max_turns,
                            action_id_factory=next_action_id,
                        )
                else:
                    selected = _choose_party_candidate(
                        _build_candidates(actor, combatants, now=clock.peek()),
                        party_strategy,
                    )
                    request = CombatActionRequest(
                        action_id=next_action_id(),
                        action=selected.action if selected else "end_turn",
                        target_id=selected.target.id if selected else None,
                        skill_id=(
                            UUID(selected.skill["id"])
                            if selected is not None and selected.skill is not None
                            else None
                        ),
                    )
                    await _resolve_player_action(
                        session,
                        encounter,
                        combatants,
                        actor,
                        request,
                        user,
                        enemy_strategy=enemy_strategy,
                        now_provider=clock,
                        turn_limit=scenario.max_turns,
                        action_id_factory=next_action_id,
                    )
            limited = encounter.status == "turn_limit"
            await session.flush()
            events = (
                await session.scalars(
                    select(CombatActionEvent)
                    .where(CombatActionEvent.encounter_id == encounter.id)
                    .order_by(CombatActionEvent.sequence_number)
                )
            ).all()
            return _metrics(
                scenario,
                encounter,
                combatants,
                list(events),
                seed=seed,
                party_strategy=party_strategy,
                enemy_strategy=enemy_strategy,
                limited=limited,
                initial_hp=initial_hp,
                initial_mana=initial_mana,
            )
        finally:
            await session.rollback()


async def _resolve_simulated_enemy_actions(
    session: AsyncSession,
    encounter: Encounter,
    combatants: list[Combatant],
    *,
    enemy_strategy: str,
    now_provider: Callable[[], datetime],
    action_id_factory: Callable[[], UUID],
) -> None:
    by_id = {str(item.id): item for item in combatants}
    while True:
        configuration = dict(encounter.configuration or {})
        pending = configuration.get("pending_action")
        if not isinstance(pending, dict):
            return
        actor = by_id.get(str(pending.get("actor_id")))
        target = by_id.get(str(pending.get("target_id")))
        if actor is None or target is None:
            raise RuntimeError(
                "A staged simulated enemy action references an unknown combatant."
            )
        if actor.enemy_id is None:
            raise RuntimeError(
                "A player action cannot be resolved as a simulated enemy action."
            )

        actor_snapshot = actor.snapshot if isinstance(actor.snapshot, dict) else {}
        skills = actor_snapshot.get("skills", {})
        raw_skill_id = pending.get("skill_id")
        skill = (
            skills.get(str(raw_skill_id))
            if isinstance(skills, dict) and raw_skill_id
            else None
        )
        request = CombatActionRequest(
            action_id=UUID(str(pending["action_id"])),
            action=str(pending.get("action")),
            target_id=target.id,
            skill_id=UUID(str(raw_skill_id)) if raw_skill_id else None,
        )
        configuration["pending_action"] = None
        encounter.configuration = configuration
        await _resolve_enemy_action(session, encounter, actor, target, request, skill)
        if _terminal_status(combatants):
            return

        configuration = dict(encounter.configuration or {})
        attacks_completed = int(configuration.get("enemy_attacks_completed", 0)) + 1
        configuration["enemy_attacks_completed"] = attacks_completed
        encounter.configuration = configuration
        max_attacks = min(
            2,
            max(1, int(actor_snapshot.get("max_attacks_per_turn", 1))),
        )
        if attacks_completed >= max_attacks or not any(
            item.character_id is not None and item.current_hp > 0
            for item in combatants
        ):
            return
        await _run_enemy_turn(
            session,
            encounter,
            actor,
            combatants,
            strategy=str(actor_snapshot.get("strategy", enemy_strategy)),
            now_provider=now_provider,
            tick_effects=False,
            is_interrupt=bool(pending.get("is_interrupt")),
            action_id_factory=action_id_factory,
        )


async def _new_memory_session_factory() -> tuple[Any, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def simulate_battle(
    scenario: BattleScenario,
    *,
    seed: int,
    party_strategy: str = "effective_damage",
    enemy_strategy: str = "baseline",
) -> dict[str, Any]:
    _validate_scenario(scenario)
    if isinstance(seed, bool) or not 0 <= seed <= 2**64 - 1:
        raise ValueError("seed must be an unsigned 64-bit integer.")
    engine, session_factory = await _new_memory_session_factory()
    try:
        async with asyncio.timeout(BATTLE_TIMEOUT_SECONDS):
            return await _simulate_in_session(
                session_factory,
                scenario,
                seed=seed,
                party_strategy=party_strategy,
                enemy_strategy=enemy_strategy,
            )
    finally:
        await engine.dispose()


def _numeric_summary(values: Iterable[float]) -> dict[str, float | int | None]:
    data = sorted(values)
    if not data:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "population_stddev": None,
            "min": None,
            "max": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p90": None,
        }

    def percentile(fraction: float) -> float:
        return data[max(0, math.ceil(fraction * len(data)) - 1)]

    return {
        "count": len(data),
        "mean": statistics.fmean(data),
        "median": statistics.median(data),
        "population_stddev": statistics.pstdev(data),
        "min": data[0],
        "max": data[-1],
        "p25": percentile(0.25),
        "p50": percentile(0.5),
        "p75": percentile(0.75),
        "p90": percentile(0.9),
    }


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    wins = sum(item["result"] == "victory" for item in results)
    participant_groups: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    skill_groups: dict[str, dict[str, Any]] = {}
    for battle in results:
        for participant in battle.get("participants", []):
            key = (
                str(participant.get("side", "")),
                str(participant.get("name", "")),
                int(participant.get("level", 0)),
            )
            participant_groups.setdefault(key, []).append(participant)
        for name, skill in battle.get("skills", {}).items():
            total = skill_groups.setdefault(
                name,
                {
                    "uses": 0,
                    "raw_damage": 0,
                    "effective_damage": 0,
                    "healing": 0,
                    "healing_wasted": 0,
                    "mana_cost": 0,
                },
            )
            for field_name in total:
                total[field_name] += int(skill.get(field_name, 0))

    participant_metrics = []
    for (side, name, level), group in sorted(participant_groups.items()):
        participant_metrics.append(
            {
                "side": side,
                "name": name,
                "level": level,
                "appearances": len(group),
                "survival_rate": sum(item["survived"] for item in group) / len(group),
                "damage_effective": sum(item["damage_effective"] for item in group),
                "damage_received_effective": sum(
                    item["damage_received_effective"] for item in group
                ),
                "healing_effective": sum(item["healing_effective"] for item in group),
                "healing_wasted": sum(item["healing_wasted"] for item in group),
                "mana_consumed": sum(item["mana_consumed"] for item in group),
            }
        )
    skill_metrics = {}
    for name, values in skill_groups.items():
        uses = values["uses"]
        mana_cost = values["mana_cost"]
        skill_metrics[name] = {
            **values,
            "damage_per_use": values["effective_damage"] / uses if uses else 0,
            "damage_per_mana": (
                values["effective_damage"] / mana_cost if mana_cost else None
            ),
            "healing_per_mana": values["healing"] / mana_cost if mana_cost else None,
        }
    return {
        "sample_size": len(results),
        "sample_sufficient_for_exploratory_comparison": len(results) >= 30,
        "win_rate": wins / len(results) if results else None,
        "result_counts": {
            result: sum(item["result"] == result for item in results)
            for result in ("victory", "defeat", "draw", "turn_limit")
        },
        "turns": _numeric_summary(item["turns"] for item in results),
        "logical_duration_rounds": _numeric_summary(
            item["logical_duration_rounds"] for item in results
        ),
        "actions_executed": _numeric_summary(item["actions_executed"] for item in results),
        "damage_effective": _numeric_summary(
            item["total_damage_effective"] for item in results
        ),
        "healing_effective": _numeric_summary(
            item["total_healing_effective"] for item in results
        ),
        "mana_consumed": _numeric_summary(item["total_mana_consumed"] for item in results),
        "average_effective_damage_per_action": _numeric_summary(
            item.get("average_effective_damage_per_action", 0) for item in results
        ),
        "damage_per_mana": _numeric_summary(
            item["damage_per_mana"]
            for item in results
            if item.get("damage_per_mana") is not None
        ),
        "participant_metrics": participant_metrics,
        "skill_metrics": skill_metrics,
    }


async def run_batch(
    scenario: BattleScenario,
    seeds: Iterable[int],
    *,
    party_strategy: str = "effective_damage",
    enemy_strategy: str = "baseline",
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    _validate_scenario(scenario)
    if party_strategy not in (*COMBAT_STRATEGIES, "survival"):
        raise ValueError(f"Unknown party strategy: {party_strategy}")
    if enemy_strategy not in COMBAT_STRATEGIES:
        raise ValueError(f"Unknown enemy strategy: {enemy_strategy}")
    seed_list = list(seeds)
    if not seed_list or len(seed_list) > MAX_BATCH_SIZE:
        raise ValueError(f"Batch size must be between 1 and {MAX_BATCH_SIZE}.")
    if any(isinstance(seed, bool) or not 0 <= seed <= 2**64 - 1 for seed in seed_list):
        raise ValueError("Every seed must be an unsigned 64-bit integer.")
    work_units = len(seed_list) * scenario.max_turns * len(scenario.participants)
    if work_units > MAX_BATCH_WORK_UNITS:
        raise ValueError(
            "The requested batch exceeds the local simulation work limit; split it into smaller batches."
        )
    engine, session_factory = await _new_memory_session_factory()
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    try:
        for index, seed in enumerate(seed_list, start=1):
            try:
                async with asyncio.timeout(BATTLE_TIMEOUT_SECONDS):
                    results.append(
                        await _simulate_in_session(
                            session_factory,
                            scenario,
                            seed=seed,
                            party_strategy=party_strategy,
                            enemy_strategy=enemy_strategy,
                        )
                    )
            except Exception as error:
                failures.append(
                    {
                        "scenario_id": scenario.scenario_id,
                        "seed": seed,
                        "error_type": type(error).__name__,
                        "message": str(error),
                    }
                )
            if progress is not None:
                progress(index, len(seed_list))
    finally:
        await engine.dispose()
    return {
        "scenario_id": scenario.scenario_id,
        "party_strategy": party_strategy,
        "enemy_strategy": enemy_strategy,
        "requested": len(seed_list),
        "results": results,
        "failures": failures,
        "aggregate": aggregate_results(results),
    }


async def compare_strategies(
    scenario: BattleScenario,
    seeds: Iterable[int],
    strategies: Iterable[str] = COMBAT_STRATEGIES,
) -> dict[str, Any]:
    seed_list = list(seeds)
    if not seed_list or len(seed_list) > MAX_BATCH_SIZE:
        raise ValueError(f"Batch size must be between 1 and {MAX_BATCH_SIZE}.")
    outputs = {}
    for strategy in strategies:
        if strategy not in COMBAT_STRATEGIES:
            raise ValueError(f"Unknown combat strategy: {strategy}")
        outputs[strategy] = await run_batch(
            scenario,
            seed_list,
            party_strategy=strategy,
            enemy_strategy=strategy,
        )
    return {
        "scenario_id": scenario.scenario_id,
        "seeds": seed_list,
        "simulator_version": SIMULATOR_VERSION,
        "rules_version": RULES_VERSION,
        "strategies": outputs,
    }


async def replay_battle(report: dict[str, Any]) -> dict[str, Any]:
    scenario = scenario_from_dict(report["scenario"])
    return await simulate_battle(
        scenario,
        seed=int(report["seed"]),
        party_strategy=str(report.get("party_strategy", "effective_damage")),
        enemy_strategy=str(report.get("enemy_strategy", "baseline")),
    )


def export_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def export_csv(report: dict[str, Any]) -> str:
    results = report.get("results", [report])
    output = io.StringIO(newline="")
    columns = (
        "scenario_id",
        "seed",
        "simulator_version",
        "rules_version",
        "party_strategy",
        "enemy_strategy",
        "result",
        "turns",
        "logical_duration_rounds",
        "actions_executed",
        "total_damage_raw",
        "total_damage_effective",
        "total_damage_received_effective",
        "total_healing_effective",
        "total_healing_wasted",
        "total_mana_consumed",
        "average_effective_damage_per_action",
        "mana_consumed_per_action",
        "damage_per_mana",
        "healing_per_mana",
        "participants_json",
        "skills_json",
        "events_json",
    )
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for result in results:
        writer.writerow(
            {
                **result,
                "participants_json": json.dumps(result.get("participants", []), ensure_ascii=False),
                "skills_json": json.dumps(result.get("skills", {}), ensure_ascii=False),
                "events_json": json.dumps(result.get("events", []), ensure_ascii=False),
            }
        )
    return output.getvalue()


SYNTHETIC_SCENARIOS: dict[str, BattleScenario] = {
    "low-vs-basic": BattleScenario(
        "low-vs-basic", "Nível baixo contra inimigo básico",
        (CombatantSpec("Aprendiz", "player", 1, 24, 6, 5, defense=2, speed=8),
         CombatantSpec("Lobo", "enemy", 1, 16, 0, 3, defense=1, speed=5)),
    ),
    "mid-vs-basic": BattleScenario(
        "mid-vs-basic", "Nível intermediário contra inimigo básico",
        (CombatantSpec("Aventureiro", "player", 5, 65, 20, 12, 14, 6, 5, 10),
         CombatantSpec("Saqueador", "enemy", 4, 42, 0, 8, defense=3, speed=7)),
    ),
    "high-vs-basic": BattleScenario(
        "high-vs-basic", "Nível alto contra inimigo básico",
        (CombatantSpec("Veterano", "player", 15, 150, 45, 28, 30, 18, 15, 16),
         CombatantSpec("Goblin", "enemy", 2, 26, 0, 5, defense=2, speed=6)),
    ),
    "player-vs-group": BattleScenario(
        "player-vs-group", "Personagem contra grupo de inimigos",
        (CombatantSpec("Guardião", "player", 7, 85, 10, 15, defense=12, speed=10),
         CombatantSpec("Lobo A", "enemy", 4, 24, 0, 7, speed=7),
         CombatantSpec("Lobo B", "enemy", 4, 24, 0, 7, speed=6),
         CombatantSpec("Lobo C", "enemy", 4, 24, 0, 7, speed=5)),
    ),
    "player-vs-boss": BattleScenario(
        "player-vs-boss", "Personagem contra boss",
        (CombatantSpec("Duelista", "player", 10, 120, 25, 20, 18, 10, 10, 14),
         CombatantSpec("Ossário", "enemy", 10, 180, 15, 16, 14, 12, 10, 8, is_boss=True)),
    ),
    "party-vs-boss": BattleScenario(
        "party-vs-boss", "Grupo de jogadores contra boss",
        (CombatantSpec("Vanguarda", "player", 9, 100, 8, 18, defense=14, speed=11),
         CombatantSpec("Arcanista", "player", 9, 70, 32, 9, 22, 6, 12, 10,
                       skills=(SkillSpec("Raio", "magic", 16, 5, "lightning", "enemy"),)),
         CombatantSpec("Curandeira", "player", 8, 75, 30, 8, 16, 7, 11, 9,
                       skills=(SkillSpec("Cura", "healing", 18, 6, "heal", "ally",
                                         additional_effects={"effect_type": "heal"}),)),
         CombatantSpec("Titã", "enemy", 12, 280, 20, 20, 18, 14, 12, 8, is_boss=True)),
    ),
    "mixed-party": BattleScenario(
        "mixed-party", "Grupo com níveis diferentes",
        (CombatantSpec("Novata", "player", 2, 30, 8, 7, speed=9),
         CombatantSpec("Veterano", "player", 12, 125, 22, 23, defense=12, speed=8),
         CombatantSpec("Bandido", "enemy", 7, 70, 0, 11, defense=5, speed=7)),
    ),
    "high-resistance": BattleScenario(
        "high-resistance", "Combate com alta resistência elemental",
        (CombatantSpec("Piromante", "player", 6, 65, 30, 8, 18, speed=10,
                       skills=(SkillSpec("Chama", "magic", 18, 5, "fire", "enemy"),)),
         CombatantSpec("Golem ígneo", "enemy", 7, 110, 0, 12, defense=8, speed=4,
                       resistances=("fire",))),
    ),
    "elemental-weakness": BattleScenario(
        "elemental-weakness", "Combate com fraqueza elemental",
        (CombatantSpec("Geada", "player", 6, 65, 30, 8, 18, speed=10,
                       skills=(SkillSpec("Chama", "magic", 12, 5, "fire", "enemy"),)),
         CombatantSpec("Elemental de gelo", "enemy", 6, 90, 0, 10, defense=6, speed=6,
                       weaknesses=("fire",))),
    ),
    "magic-resource": BattleScenario(
        "magic-resource", "Magia intensiva e consumo de mana",
        (CombatantSpec("Feiticeiro", "player", 8, 75, 18, 8, 20, 5, 8, 11,
                       skills=(SkillSpec("Explosão", "magic", 20, 7, "arcane", "enemy"),)),
         CombatantSpec("Sentinela", "enemy", 8, 100, 0, 12, defense=8, speed=7)),
    ),
    "defense-and-healing": BattleScenario(
        "defense-and-healing", "Defesa e cura",
        (CombatantSpec("Protetor", "player", 8, 110, 18, 11, defense=18, speed=8,
                       skills=(SkillSpec("Cura", "healing", 24, 6, "heal", "ally",
                                         additional_effects={"effect_type": "heal"}),)),
         CombatantSpec("Aliada", "player", 7, 62, 16, 10, defense=8, speed=7),
         CombatantSpec("Ogro", "enemy", 8, 145, 0, 15, defense=9, speed=6)),
    ),
    "special-effects": BattleScenario(
        "special-effects", "Habilidade especial com dano contínuo",
        (CombatantSpec("Druida", "player", 7, 75, 22, 10, 17, 7, 10, 11,
                       skills=(SkillSpec("Esporos", "magic", 5, 4, "poison", "enemy",
                                         additional_effects={"effect_type": "damage_over_time",
                                                             "damage_per_turn": 3, "duration": 3}),)),
         CombatantSpec("Quimera", "enemy", 9, 140, 0, 14, defense=8, speed=7)),
    ),
    "limit-draw": BattleScenario(
        "limit-draw", "Cenário limitado de longa duração",
        (CombatantSpec("Defensor", "player", 1, 200, 0, 1, defense=50, speed=4),
         CombatantSpec("Guardião de pedra", "enemy", 1, 200, 0, 1, defense=50, speed=3)),
        max_turns=4,
    ),
}


def main() -> None:
    import argparse
    from pathlib import Path
    import sys

    parser = argparse.ArgumentParser(description="Isolated H.4 combat simulator")
    scenario_options = parser.add_mutually_exclusive_group()
    scenario_options.add_argument(
        "--scenario",
        choices=sorted(SYNTHETIC_SCENARIOS),
    )
    scenario_options.add_argument("--scenario-file", type=Path)
    parser.add_argument("--battles", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--party-strategy", choices=COMBAT_STRATEGIES, default="effective_damage")
    parser.add_argument("--enemy-strategy", choices=COMBAT_STRATEGIES, default="baseline")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if not 1 <= arguments.battles <= MAX_BATCH_SIZE:
        parser.error(f"--battles must be between 1 and {MAX_BATCH_SIZE}")
    if arguments.scenario_file:
        try:
            scenario_document = json.loads(
                arguments.scenario_file.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            parser.error(f"Cannot read the scenario JSON file: {type(error).__name__}")
        if not isinstance(scenario_document, dict):
            parser.error("The scenario JSON file must contain one object.")
        try:
            scenario = scenario_from_dict(scenario_document)
        except ValueError as error:
            parser.error(str(error))
    else:
        scenario = SYNTHETIC_SCENARIOS[arguments.scenario or "low-vs-basic"]

    def show_progress(done: int, total: int) -> None:
        if total > 1:
            print(f"\rSimulações: {done}/{total}", end="", file=sys.stderr, flush=True)

    batch = asyncio.run(
        run_batch(
            scenario,
            range(arguments.seed, arguments.seed + arguments.battles),
            party_strategy=arguments.party_strategy,
            enemy_strategy=arguments.enemy_strategy,
            progress=show_progress,
        )
    )
    if arguments.battles > 1:
        print(file=sys.stderr)
    rendered = export_json(batch) if arguments.format == "json" else export_csv(batch)
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
