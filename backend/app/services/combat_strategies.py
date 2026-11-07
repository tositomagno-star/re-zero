from __future__ import annotations

from typing import Literal

CombatStrategyName = Literal[
    "baseline",
    "effective_damage",
    "mana_conservation",
    "focus_low_hp",
    "elemental_weakness",
    "aggressive",
    "conservative",
    "economic",
    "tactical",
    "adaptive",
]

COMBAT_STRATEGIES: tuple[CombatStrategyName, ...] = (
    "baseline",
    "effective_damage",
    "mana_conservation",
    "focus_low_hp",
    "elemental_weakness",
    "survival",
    "aggressive",
    "conservative",
    "economic",
    "tactical",
    "adaptive",
)


def candidate_sort_key(
    strategy: str,
    *,
    kills_target: bool,
    effective_damage: int,
    mana_cost: int,
    raw_damage: int,
    target_hp: int,
    elemental_weakness: bool,
    skill_id: str,
    target_id: str,
    current_mana: int | None = None,
    max_mana: int | None = None,
    target_threat: int = 0,
    applies_new_effect: bool = False,
) -> tuple[int, int, int, int, int, str, str]:
    if strategy not in COMBAT_STRATEGIES:
        raise ValueError(f"Unknown combat strategy: {strategy}")
    kill_rank = -int(kills_target)
    if strategy == "aggressive":
        return (kill_rank, -effective_damage, -raw_damage, mana_cost, 0, skill_id, target_id)
    if strategy == "conservative":
        return (-int(kills_target), -target_threat, mana_cost, -effective_damage, 0, skill_id, target_id)
    if strategy == "economic":
        return (mana_cost, kill_rank, -effective_damage, -raw_damage, 0, skill_id, target_id)
    if strategy == "tactical":
        return (
            -int(elemental_weakness),
            -int(applies_new_effect),
            kill_rank,
            -effective_damage,
            mana_cost,
            skill_id,
            target_id,
        )
    if strategy == "adaptive":
        mana_ratio = (
            current_mana / max_mana
            if current_mana is not None and max_mana
            else 1.0
        )
        if mana_ratio <= 0.25:
            return (1, mana_cost, kill_rank, -effective_damage, -raw_damage, skill_id, target_id)
        return (
            0,
            -int(elemental_weakness),
            -int(applies_new_effect),
            kill_rank,
            -effective_damage,
            mana_cost,
            target_id or skill_id,
        )
    if strategy == "mana_conservation":
        return (mana_cost, kill_rank, -effective_damage, -raw_damage, 0, skill_id, target_id)
    if strategy == "focus_low_hp":
        return (kill_rank, target_hp, -effective_damage, mana_cost, 0, skill_id, target_id)
    if strategy == "elemental_weakness":
        return (
            -int(elemental_weakness),
            kill_rank,
            -effective_damage,
            mana_cost,
            -raw_damage,
            skill_id,
            target_id,
        )
    if strategy == "effective_damage":
        return (kill_rank, -effective_damage, mana_cost, -raw_damage, 0, skill_id, target_id)
    if strategy == "survival":
        return (kill_rank, -effective_damage, mana_cost, -raw_damage, 0, skill_id, target_id)
    return (kill_rank, -effective_damage, mana_cost, -raw_damage, 0, skill_id, target_id)
